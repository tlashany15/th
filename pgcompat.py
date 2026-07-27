"""
pgcompat.py — طبقة توافق تخلي التطبيق يشتغل على ملف SQLite بدل PostgreSQL
بدون ما نغيّر كود app.py ولا نفقد أي بيانات.

الاستخدام في app.py:
    import pgcompat as psycopg2
    import pgcompat.extras            # psycopg2.extras.RealDictCursor موجودة

مكان ملف البيانات: متغير البيئة DB_FILE (افتراضي: data.db جنب الملف ده)
"""
import os
import re
import json
import sqlite3
import threading
from datetime import date, datetime

__version__ = "sqlite-compat 1.0"

DB_FILE = os.environ.get("DB_FILE") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data.db"
)

# أخطاء متوافقة مع psycopg2
Error = sqlite3.Error
DatabaseError = sqlite3.DatabaseError
IntegrityError = sqlite3.IntegrityError
OperationalError = sqlite3.OperationalError
ProgrammingError = sqlite3.ProgrammingError
InterfaceError = sqlite3.InterfaceError
DataError = sqlite3.DataError


class _Extras:
    """psycopg2.extras.RealDictCursor — مجرد علامة، الصفوف بترجع dict دايمًا."""
    class RealDictCursor:
        pass

    class DictCursor:
        pass


extras = _Extras()

AGG_TAG = "@@AGG@@"

# ---------- محوّلات التاريخ ----------
sqlite3.register_adapter(date, lambda d: d.isoformat())
sqlite3.register_adapter(datetime, lambda d: d.isoformat(sep=" "))


def _to_date(b):
    s = b.decode() if isinstance(b, bytes) else str(b)
    s = s.strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _to_datetime(b):
    s = b.decode() if isinstance(b, bytes) else str(b)
    s = s.strip().replace("T", " ")
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1]
    for fmt in ("%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return s


for _n in ("date",):
    sqlite3.register_converter(_n, _to_date)
for _n in ("timestamp", "timestamptz", "datetime", "timestamp with time zone"):
    sqlite3.register_converter(_n, _to_datetime)


# ---------- دوال SQL إضافية ----------
class _ArrayAgg:
    """array_agg(value, sort_key) -> نص JSON متعلّم عشان يرجع list في بايثون."""

    def __init__(self):
        self.rows = []

    def step(self, value, key=None):
        if value is None:
            return
        self.rows.append((key if key is not None else value, value))

    def finalize(self):
        try:
            ordered = sorted(self.rows, key=lambda t: (t[0] is None, t[0]))
        except TypeError:
            ordered = sorted(self.rows, key=lambda t: (t[0] is None, str(t[0])))
        return AGG_TAG + json.dumps([v for _, v in ordered], ensure_ascii=False)


def _register_functions(conn):
    conn.create_aggregate("array_agg", 2, _ArrayAgg)
    conn.create_function(
        "pg_regex", 2,
        lambda v, p: 1 if (v is not None and re.search(p, str(v))) else 0)
    conn.create_function("greatest", 2, lambda a, b: a if b is None else (b if a is None else max(a, b)))
    conn.create_function("least", 2, lambda a, b: a if b is None else (b if a is None else min(a, b)))
    conn.create_function("current_database", 0, lambda: "local")

    # حجم الجداول/الملف — تقدير من حجم ملف SQLite نفسه
    def _file_size():
        try:
            return os.path.getsize(DB_FILE)
        except Exception:
            return 0

    def _table_size(name):
        try:
            row = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()
            n = row[0] if row else 0
        except Exception:
            n = 0
        total = _file_size()
        try:
            allrows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'").fetchall()
            tot = 0
            for (t,) in allrows:
                try:
                    tot += conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                except Exception:
                    pass
        except Exception:
            tot = 0
        return int(total * n / tot) if tot else 0

    conn.create_function("pg_total_relation_size", 1, _table_size)
    conn.create_function("pg_relation_size", 1, _table_size)
    conn.create_function("pg_database_size", 1, lambda _d=None: _file_size())

    def _pretty(b):
        try:
            b = float(b or 0)
        except Exception:
            return "0 B"
        for u in ("B", "kB", "MB", "GB"):
            if b < 1024:
                return f"{b:.0f} {u}"
            b /= 1024
        return f"{b:.1f} TB"

    conn.create_function("pg_size_pretty", 1, _pretty)


# ---------- ترجمة SQL من Postgres إلى SQLite ----------
_DO_BLOCK = re.compile(r"DO\s+\$\$.*?\$\$\s*;", re.S | re.I)


def _split_cols(txt):
    parts, depth, buf = [], 0, []
    q = None
    for ch in txt:
        if q:
            buf.append(ch)
            if ch == q:
                q = None
            continue
        if ch in ("'", '"'):
            q = ch
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


_ROW_TO_JSON = re.compile(
    r"row_to_json\s*\(\s*\w+\s*\)\s*FROM\s*\(\s*SELECT\s+(.*?)\s+FROM\s", re.I | re.S)


def _row_to_json(s):
    """(SELECT row_to_json(t) FROM (SELECT a,b FROM ...) t) -> json_object('a',a,'b',b)"""
    def rep(m):
        cols = _split_cols(m.group(1))
        pairs = []
        for c in cols:
            name = re.split(r"\s+AS\s+|\s+", c, flags=re.I)[-1].split(".")[-1].strip('"')
            pairs.append(f"'{name}', {c}")
        return ("('" + AGG_TAG + "' || json_object(" + ", ".join(pairs) + ")) FROM (SELECT "
                + m.group(1) + " FROM ")
    return _ROW_TO_JSON.sub(rep, s)


def _translate(sql: str) -> str:
    s = sql

    # 1) placeholders
    s = s.replace("%s", "?")

    # 2) امسح بلوكات DO $$ ... $$ (خاصة بـ Postgres بس)
    s = _DO_BLOCK.sub(" ", s)

    # 3) الأنواع في CREATE TABLE
    s = re.sub(r"\b(BIG)?SERIAL\s+PRIMARY\s+KEY\b", "INTEGER PRIMARY KEY AUTOINCREMENT", s, flags=re.I)
    s = re.sub(r"\b(BIG)?SERIAL\b", "INTEGER", s, flags=re.I)
    s = re.sub(r"\bDOUBLE\s+PRECISION\b", "REAL", s, flags=re.I)
    s = re.sub(r"\bJSONB\b", "TEXT", s, flags=re.I)
    s = re.sub(r"\bDEFAULT\s+NOW\(\)", "DEFAULT (datetime('now'))", s, flags=re.I)
    s = re.sub(r"\bDEFAULT\s+CURRENT_DATE\b", "DEFAULT (date('now'))", s, flags=re.I)

    # 4) EXTRACT(...)
    def _extract(m):
        part, expr = m.group(1).upper(), m.group(2)
        fmt = {"YEAR": "%Y", "MONTH": "%m", "DAY": "%d",
               "HOUR": "%H", "MINUTE": "%M", "SECOND": "%S"}.get(part, "%Y")
        return f"CAST(strftime('{fmt}', {expr}) AS INTEGER)"

    s = re.sub(r"EXTRACT\s*\(\s*(\w+)\s+FROM\s+([^)]+?)\s*\)", _extract, s, flags=re.I)

    # 5) NOW() ± INTERVAL 'N days'
    def _interval(m):
        sign = "-" if m.group(1) == "-" else "+"
        return f"datetime('now','{sign}{m.group(2)} {m.group(3)}')"

    s = re.sub(r"NOW\(\)\s*([+-])\s*INTERVAL\s+'(\d+)\s*(\w+)'", _interval, s, flags=re.I)
    s = re.sub(r"CURRENT_TIMESTAMP\s*([+-])\s*INTERVAL\s+'(\d+)\s*(\w+)'", _interval, s, flags=re.I)
    s = re.sub(r"\bNOW\(\)", "datetime('now')", s, flags=re.I)
    s = re.sub(r"\bCURRENT_DATE\b", "date('now')", s, flags=re.I)

    # 6) casts  x::int / x::float
    s = re.sub(r"::\s*(int|integer|bigint|smallint)\b", "__CAST_INT__", s, flags=re.I)
    s = re.sub(r"::\s*(float|numeric|real|decimal)\b", "__CAST_REAL__", s, flags=re.I)
    s = re.sub(r"::\s*(text|varchar)\b", "__CAST_TEXT__", s, flags=re.I)
    for tag, typ in (("__CAST_INT__", "INTEGER"), ("__CAST_REAL__", "REAL"), ("__CAST_TEXT__", "TEXT")):
        while tag in s:
            s = _apply_cast(s, tag, typ)

    # 7) ARRAY_AGG(expr ORDER BY key)  /  ARRAY_AGG(expr)
    s = re.sub(r"ARRAY_AGG\s*\(\s*(.+?)\s+ORDER\s+BY\s+(.+?)\s*\)",
               lambda m: f"array_agg({m.group(1)}, {m.group(2)})", s, flags=re.I)
    s = re.sub(r"ARRAY_AGG\s*\(\s*([^(),]+?)\s*\)",
               lambda m: f"array_agg({m.group(1)}, {m.group(1)})", s, flags=re.I)
    s = s.replace("'{}'", "'" + AGG_TAG + "[]'")

    # 8) متفرقات
    s = re.sub(r"([\w\.\"]+)\s*!~\s*('[^']*')", r"NOT pg_regex(\1, \2)", s)
    s = re.sub(r"([\w\.\"]+)\s*~\*?\s*('[^']*')", r"pg_regex(\1, \2)", s)
    s = _row_to_json(s)
    s = re.sub(r"\bILIKE\b", "LIKE", s, flags=re.I)
    s = re.sub(r"\bGREATEST\s*\(", "greatest(", s, flags=re.I)
    s = re.sub(r"\bLEAST\s*\(", "least(", s, flags=re.I)
    s = re.sub(r"\bFOR\s+UPDATE\b", "", s, flags=re.I)
    return s


def _apply_cast(s, tag, typ):
    """يحوّل  expr__CAST_INT__  إلى  CAST(expr AS INTEGER)"""
    i = s.index(tag)
    j = i - 1
    while j >= 0 and s[j] == " ":
        j -= 1
    end = j + 1
    if j >= 0 and s[j] == ")":
        depth = 0
        while j >= 0:
            if s[j] == ")":
                depth += 1
            elif s[j] == "(":
                depth -= 1
                if depth == 0:
                    break
            j -= 1
        # اسحب اسم الدالة قبل القوس
        k = j - 1
        while k >= 0 and (s[k].isalnum() or s[k] in "_."):
            k -= 1
        start = k + 1
    else:
        while j >= 0 and (s[j].isalnum() or s[j] in "_.\"'"):
            j -= 1
        start = j + 1
    expr = s[start:end]
    return s[:start] + f"CAST({expr} AS {typ})" + s[i + len(tag):]


def _split_statements(sql: str):
    out, buf, i, n = [], [], 0, len(sql)
    q = None
    while i < n:
        c = sql[i]
        if q:
            buf.append(c)
            if c == q:
                q = None
        elif c in ("'", '"'):
            q = c
            buf.append(c)
        elif c == "-" and sql[i:i + 2] == "--":
            while i < n and sql[i] != "\n":
                i += 1
            continue
        elif c == ";":
            out.append("".join(buf))
            buf = []
        else:
            buf.append(c)
        i += 1
    if "".join(buf).strip():
        out.append("".join(buf))
    return [x for x in (y.strip() for y in out) if x]


_ADD_COL = re.compile(
    r"ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+(\w+)(.*)$", re.I | re.S)
_ANY_RE = re.compile(r"=\s*ANY\s*\(\s*\?\s*\)", re.I)


class Row(dict):
    """صف نتيجة: يشتغل بالاسم r["x"] وبالرقم r[0] زي psycopg2."""

    def __init__(self, cols, values):
        super().__init__(zip(cols, values))
        self._cols = cols

    def __getitem__(self, k):
        if isinstance(k, int):
            return dict.__getitem__(self, self._cols[k])
        if isinstance(k, slice):
            return [dict.__getitem__(self, c) for c in self._cols[k]]
        return dict.__getitem__(self, k)


def _decode(v):
    if isinstance(v, str) and v.startswith(AGG_TAG):
        try:
            return json.loads(v[len(AGG_TAG):])
        except Exception:
            return []
    return v


class Cursor:
    def __init__(self, conn):
        self._conn = conn
        self._cur = conn._raw.cursor()

    # -- خصائص متوافقة --
    @property
    def description(self):
        return self._cur.description

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    def _run(self, sql, params):
        params = list(params or [])
        # = ANY(?) -> IN (?,?,...)
        if params and _ANY_RE.search(sql):
            new_params, idx = [], 0
            def repl_q(match):
                return match.group(0)
            # وسّع كل ANY حسب مكان الباراميتر
            parts = re.split(r"(\?)", sql)
            # نبني SQL جديد مع توسيع القوائم
            rebuilt, pi = [], 0
            for token in parts:
                if token == "?":
                    val = params[pi] if pi < len(params) else None
                    pi += 1
                    if isinstance(val, (list, tuple, set)):
                        vals = list(val)
                        rebuilt.append("(" + ",".join("?" * len(vals)) + ")" if vals else "(NULL)")
                        new_params.extend(vals)
                    else:
                        rebuilt.append("?")
                        new_params.append(val)
                else:
                    rebuilt.append(token)
            sql = "".join(rebuilt)
            sql = re.sub(r"=\s*ANY\s*", " IN ", sql, flags=re.I)
            params = new_params
        else:
            params = [json.dumps(p) if isinstance(p, dict) else p for p in params]
        try:
            self._cur.execute(sql, params)
        except sqlite3.OperationalError as e:
            if "RETURNING" in sql.upper() and "returning" in str(e).lower():
                self._cur.execute(re.sub(r"\bRETURNING\b.*$", "", sql, flags=re.I | re.S), params)
            else:
                raise

    def execute(self, sql, params=None):
        sql = _translate(sql)
        stmts = _split_statements(sql)
        if len(stmts) > 1:
            for st in stmts:
                self._exec_one(st, None)
            return self
        if stmts:
            self._exec_one(stmts[0], params)
        return self

    def _exec_one(self, sql, params):
        m = _ADD_COL.match(sql.strip())
        if m:
            table, col, rest = m.group(1), m.group(2), m.group(3)
            cols = [r[1] for r in self._cur.execute(f"PRAGMA table_info({table})").fetchall()]
            if col in cols:
                return
            rest = re.sub(r"\bDEFAULT\s+\(datetime\('now'\)\)", "DEFAULT CURRENT_TIMESTAMP", rest, flags=re.I)
            try:
                self._cur.execute(f"ALTER TABLE {table} ADD COLUMN {col}{rest}")
            except sqlite3.OperationalError:
                pass
            return
        self._run(sql, params)

    def executemany(self, sql, seq):
        sql = _translate(sql)
        self._cur.executemany(sql, [list(p) for p in seq])
        return self

    # -- جلب النتائج كـ dict --
    def _row(self, row):
        if row is None:
            return None
        cols = [d[0] for d in self._cur.description]
        return Row(cols, [_decode(v) for v in row])

    def fetchone(self):
        return self._row(self._cur.fetchone())

    def fetchall(self):
        rows = self._cur.fetchall()
        if not rows:
            return []
        cols = [d[0] for d in self._cur.description]
        return [Row(cols, [_decode(v) for v in r]) for r in rows]

    def fetchmany(self, size=1):
        return [self._row(r) for r in self._cur.fetchmany(size)]

    def __iter__(self):
        return iter(self.fetchall())

    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


_lock = threading.Lock()
_initialized = False


class Connection:
    def __init__(self, path):
        first = not os.path.exists(path)
        d = os.path.dirname(os.path.abspath(path))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        self._raw = sqlite3.connect(
            path, check_same_thread=False, timeout=30,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            isolation_level=None,
        )
        self._raw.execute("PRAGMA journal_mode=WAL")
        self._raw.execute("PRAGMA busy_timeout=30000")
        self._raw.execute("PRAGMA foreign_keys=ON")
        _register_functions(self._raw)
        self._autocommit = True
        self._first = first

    # psycopg2 API
    @property
    def autocommit(self):
        return self._autocommit

    @autocommit.setter
    def autocommit(self, v):
        self._autocommit = bool(v)

    def cursor(self, *a, **kw):
        return Cursor(self)

    def commit(self):
        try:
            self._raw.commit()
        except Exception:
            pass

    def rollback(self):
        try:
            self._raw.rollback()
        except Exception:
            pass

    def close(self):
        try:
            self._raw.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def connect(dsn=None, cursor_factory=None, **kw):
    """نفس توقيع psycopg2.connect لكن بيفتح ملف SQLite."""
    return Connection(kw.get("database") or DB_FILE)
