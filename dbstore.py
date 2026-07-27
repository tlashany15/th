"""
dbstore.py — طبقة أمان لقاعدة البيانات.

الفكرة:
  * التطبيق بيشتغل عادي على PostgreSQL زي ما هو (DATABASE_URL).
  * كل فترة بناخد نسخة كاملة من القاعدة في ملف محلي data.db (بدون أي تعديل في البيانات).
  * لو القاعدة وقفت أو انتهى اشتراكها → التطبيق **مايقفش**، بيكمل شغل على الملف المحلي
    وبيعرض كل البيانات المسجّلة ويقدر يسجّل جديد كمان.
  * الأدمن بيفتح صفحة /admin/database ويحط لينك قاعدة بيانات جديدة →
    بننقل كل حاجة (القديم + اللي اتسجّل وقت التوقف) للقاعدة الجديدة بدون ما يضيع أي شيء.

الاستخدام في app.py:
    import dbstore as psycopg2
    from dbstore import extras
"""
import os
import json
import time
import sqlite3
import threading
import datetime as _dt

import pgcompat

try:
    import psycopg2 as _pg
    import psycopg2.extras as _pg_extras
except Exception:  # لو المكتبة مش متثبتة نشتغل ملفات على طول
    _pg = None
    _pg_extras = None

__version__ = "dbstore 1.0"

# ---------- توافق أسماء الأخطاء مع psycopg2 ----------
if _pg is not None:
    IntegrityError = (_pg.IntegrityError, sqlite3.IntegrityError)
    OperationalError = (_pg.OperationalError, sqlite3.OperationalError)
    ProgrammingError = (_pg.ProgrammingError, sqlite3.ProgrammingError)
    DatabaseError = (_pg.DatabaseError, sqlite3.DatabaseError)
    Error = (_pg.Error, sqlite3.Error)
    DataError = (_pg.DataError, sqlite3.DataError)
    InterfaceError = (_pg.InterfaceError, sqlite3.InterfaceError)
else:
    IntegrityError = sqlite3.IntegrityError
    OperationalError = sqlite3.OperationalError
    ProgrammingError = sqlite3.ProgrammingError
    DatabaseError = sqlite3.DatabaseError
    Error = sqlite3.Error
    DataError = sqlite3.DataError
    InterfaceError = sqlite3.InterfaceError

extras = _pg_extras if _pg_extras is not None else pgcompat.extras

# ---------- مكان ملفات الحالة ----------
_BASE = os.path.dirname(os.path.abspath(__file__))


def _pick_dir():
    d = os.environ.get("DB_STATE_DIR") or _BASE
    try:
        os.makedirs(d, exist_ok=True)
        probe = os.path.join(d, ".w")
        with open(probe, "w") as f:
            f.write("1")
        os.remove(probe)
        return d
    except Exception:
        d = "/tmp/thdata"
        os.makedirs(d, exist_ok=True)
        return d


STATE_DIR = _pick_dir()
STATE_FILE = os.path.join(STATE_DIR, "db_state.json")
if not os.environ.get("DB_FILE"):
    pgcompat.DB_FILE = os.path.join(STATE_DIR, "data.db")

SYNC_INTERVAL = int(os.environ.get("DB_SYNC_SECONDS", "300"))   # كل 5 دقايق
RETRY_INTERVAL = int(os.environ.get("DB_RETRY_SECONDS", "60"))  # نجرب القاعدة كل دقيقة وهي واقعة
CONNECT_TIMEOUT = int(os.environ.get("DB_CONNECT_TIMEOUT", "5"))

_lock = threading.RLock()
_local = threading.local()
_init_db_fn = None          # بيتسجّل من app.py
_local_schema_ready = False


# ---------- حالة النظام ----------
def _load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(**kw):
    with _lock:
        st = _load_state()
        st.update(kw)
        tmp = STATE_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(st, f, ensure_ascii=False)
            os.replace(tmp, STATE_FILE)
        except Exception:
            pass
        return st


def current_url():
    """اللينك المستخدم حاليًا: اللي الأدمن حطه، وإلا متغير البيئة."""
    return (_load_state().get("database_url") or "").strip() \
        or os.environ.get("DATABASE_URL", "").strip()


def register_init(fn):
    """app.py بيسجّل دالة init_db عشان نقدر نبني الجداول في أي مكان."""
    global _init_db_fn
    _init_db_fn = fn


def register_url(url, activate=True):
    _save_state(database_url=(url or "").strip(),
                offline=False if activate else _load_state().get("offline", False))


def status():
    st = _load_state()
    mode = "offline" if st.get("offline") else "online"
    if not current_url():
        mode = "offline"
    return {
        "mode": mode,
        "online": mode == "online",
        "url_set": bool(current_url()),
        "last_sync": st.get("last_sync"),
        "last_sync_rows": st.get("last_sync_rows"),
        "offline_since": st.get("offline_since"),
        "last_error": st.get("last_error"),
        "db_file": pgcompat.DB_FILE,
        "local_rows": _local_counts(),
    }


def _local_counts():
    try:
        raw = sqlite3.connect(pgcompat.DB_FILE, timeout=5)
        out = {}
        for (t,) in raw.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
            try:
                out[t] = raw.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except Exception:
                pass
        raw.close()
        return out
    except Exception:
        return {}


# ---------- إجبار الاتصال المحلي ----------
class force_local:
    """with force_local(): ... → أي connect جوه البلوك ده يفتح الملف المحلي."""

    def __enter__(self):
        _local.force = True

    def __exit__(self, *a):
        _local.force = False
        return False


class force_url:
    """with force_url(u): ... → أي connect جوه البلوك ده يروح للقاعدة دي بالذات."""

    def __init__(self, url):
        self.url = url

    def __enter__(self):
        _local.url = self.url

    def __exit__(self, *a):
        _local.url = None
        return False


def ensure_local_schema():
    """يتأكد إن الجداول موجودة في الملف المحلي (مرة واحدة)."""
    global _local_schema_ready
    if _local_schema_ready or _init_db_fn is None:
        return
    try:
        with force_local():
            _init_db_fn()
        _local_schema_ready = True
    except Exception as e:
        print("dbstore: local schema error:", e)


# ---------- الاتصال ----------
def connect(dsn=None, cursor_factory=None, **kw):
    """نفس توقيع psycopg2.connect، بس بيرجع للملف المحلي لو القاعدة واقعة."""
    if getattr(_local, "force", False):
        return pgcompat.connect()

    forced = getattr(_local, "url", None)
    url = forced or current_url()
    if not url or _pg is None:
        ensure_local_schema()
        return pgcompat.connect()

    if forced:
        # نقل/فحص لقاعدة معيّنة — من غير أي فلترة ولا رجوع للملف
        return _pg.connect(
            url,
            cursor_factory=cursor_factory or (_pg_extras.RealDictCursor if _pg_extras else None),
            connect_timeout=max(CONNECT_TIMEOUT, 15),
        )

    st = _load_state()
    if st.get("offline"):
        # القاعدة واقعة — نجرب تاني كل شوية بس مش على كل ريكويست
        if time.time() - float(st.get("last_try") or 0) < RETRY_INTERVAL:
            ensure_local_schema()
            return pgcompat.connect()
        _save_state(last_try=time.time())

    try:
        conn = _pg.connect(
            url,
            cursor_factory=cursor_factory or (_pg_extras.RealDictCursor if _pg_extras else None),
            connect_timeout=CONNECT_TIMEOUT,
        )
        if st.get("offline"):
            _save_state(offline=False, offline_since=None, last_error=None)
        _maybe_sync()
        return conn
    except Exception as e:
        _save_state(offline=True,
                    offline_since=st.get("offline_since") or _dt.datetime.now().isoformat(" ", "seconds"),
                    last_error=str(e)[:300],
                    last_try=time.time())
        print("dbstore: القاعدة مش شغالة، بنكمل على الملف المحلي:", str(e)[:150])
        ensure_local_schema()
        return pgcompat.connect()


# ---------- تحويل القيم ----------
def _norm_for_sqlite(v):
    if isinstance(v, (list, tuple)):
        return json.dumps(list(v), ensure_ascii=False)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, _dt.datetime):
        return v.isoformat(sep=" ")
    if isinstance(v, _dt.date):
        return v.isoformat()
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, memoryview):
        return bytes(v)
    return v


def _norm_for_pg(v, coltype):
    t = (coltype or "").lower()
    if v is None:
        return None
    if t == "boolean":
        if isinstance(v, str):
            return v.strip().lower() in ("1", "t", "true", "yes")
        return bool(v)
    if t == "array":
        if isinstance(v, (list, tuple)):
            return list(v)
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                try:
                    return json.loads(s)
                except Exception:
                    pass
            return [x for x in s.split(",") if x != ""] if s else []
        return []
    if t in ("json", "jsonb"):
        if isinstance(v, (dict, list)):
            return json.dumps(v, ensure_ascii=False)
        return v
    return v


# ---------- النسخ الاحتياطي: من القاعدة إلى الملف ----------
_syncing = False


def _maybe_sync():
    global _syncing
    st = _load_state()
    if _syncing or time.time() - float(st.get("last_sync_ts") or 0) < SYNC_INTERVAL:
        return
    _syncing = True
    threading.Thread(target=_sync_worker, daemon=True).start()


def _sync_worker():
    global _syncing
    try:
        n = sync_now()
        print(f"dbstore: نسخة احتياطية تمت ({n} صف)")
    except Exception as e:
        print("dbstore: فشل النسخ الاحتياطي:", str(e)[:200])
    finally:
        _syncing = False


def sync_now(url=None):
    """ينسخ كل جداول القاعدة إلى الملف المحلي (بدون تغيير في البيانات)."""
    url = url or current_url()
    if not url or _pg is None:
        raise RuntimeError("مفيش لينك قاعدة بيانات شغال")
    ensure_local_schema()
    pg = _pg.connect(url, cursor_factory=_pg_extras.RealDictCursor,
                     connect_timeout=CONNECT_TIMEOUT)
    cur = pg.cursor()
    cur.execute("""SELECT table_name FROM information_schema.tables
                   WHERE table_schema='public' AND table_type='BASE TABLE'
                   ORDER BY table_name""")
    tables = [r["table_name"] for r in cur.fetchall()]
    raw = sqlite3.connect(pgcompat.DB_FILE, timeout=30)
    raw.execute("PRAGMA journal_mode=WAL")
    total = 0
    for t in tables:
        existing = [r[1] for r in raw.execute(f"PRAGMA table_info({t})").fetchall()]
        if not existing:
            continue
        cur.execute(f'SELECT * FROM "{t}"')
        rows = cur.fetchall()
        if not rows:
            continue
        cols = [c for c in rows[0].keys() if c in existing]
        q = (f'INSERT OR REPLACE INTO {t} ({",".join(cols)}) '
             f'VALUES ({",".join("?" * len(cols))})')
        raw.executemany(q, [[_norm_for_sqlite(r[c]) for c in cols] for r in rows])
        total += len(rows)
    for t in tables:
        try:
            raw.execute("INSERT OR REPLACE INTO sqlite_sequence(name, seq) "
                        f"SELECT '{t}', COALESCE(MAX(id),0) FROM {t}")
        except Exception:
            pass
    raw.commit()
    raw.close()
    cur.close()
    pg.close()
    _save_state(last_sync=_dt.datetime.now().isoformat(" ", "seconds"),
                last_sync_ts=time.time(), last_sync_rows=total)
    return total


# ---------- النقل: من الملف إلى قاعدة بيانات جديدة ----------
def migrate_to(new_url, wipe=False):
    """ينقل كل اللي في الملف المحلي إلى القاعدة الجديدة ويفعّلها.
    بيرجع تقرير بعدد الصفوف لكل جدول."""
    if _pg is None:
        raise RuntimeError("مكتبة psycopg2 مش متثبتة على السيرفر")
    new_url = (new_url or "").strip()
    if not new_url:
        raise ValueError("اكتب لينك قاعدة البيانات الجديدة")

    # 1) نتأكد إن اللينك شغال
    test = _pg.connect(new_url, connect_timeout=10)
    test.close()

    # 2) ننشئ الجداول في القاعدة الجديدة
    if _init_db_fn is not None:
        with force_url(new_url):
            _init_db_fn()

    # 3) ننقل الصفوف
    pg = _pg.connect(new_url, connect_timeout=30)
    pg.autocommit = False
    cur = pg.cursor()
    raw = sqlite3.connect(pgcompat.DB_FILE, timeout=30)
    raw.row_factory = sqlite3.Row

    tables = [r[0] for r in raw.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()]

    report = {}
    for t in tables:
        cur.execute("""SELECT column_name, data_type FROM information_schema.columns
                       WHERE table_schema='public' AND table_name=%s""", (t,))
        types = {r[0]: r[1] for r in cur.fetchall()}
        if not types:
            continue
        rows = raw.execute(f"SELECT * FROM {t}").fetchall()
        if not rows:
            report[t] = 0
            continue
        cols = [c for c in rows[0].keys() if c in types]
        if not cols:
            continue
        if wipe:
            cur.execute(f'TRUNCATE TABLE "{t}" CASCADE')
        collist = ",".join(f'"{c}"' for c in cols)
        ph = ",".join(["%s"] * len(cols))
        conflict = ' ON CONFLICT DO NOTHING'
        q = f'INSERT INTO "{t}" ({collist}) VALUES ({ph}){conflict}'
        data = [[_norm_for_pg(r[c], types[c]) for c in cols] for r in rows]
        _pg_extras.execute_batch(cur, q, data, page_size=200)
        report[t] = len(rows)
    pg.commit()

    # 4) نظبط عدادات الـ id
    for t in report:
        try:
            cur.execute(f"""SELECT setval(pg_get_serial_sequence('"{t}"','id'),
                            GREATEST(COALESCE((SELECT MAX(id) FROM "{t}"),0),1))""")
        except Exception:
            pg.rollback()
    pg.commit()
    cur.close()
    pg.close()
    raw.close()

    # 5) نفعّل القاعدة الجديدة
    register_url(new_url, activate=True)
    _save_state(offline=False, offline_since=None, last_error=None,
                last_migration=_dt.datetime.now().isoformat(" ", "seconds"))
    try:
        sync_now(new_url)
    except Exception:
        pass
    return report
