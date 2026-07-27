"""
تطبيق فريق تحصين الكتاكيت
Flask + PostgreSQL — يعمل على Vercel
"""
import os
import re
import base64
import json as _json
import urllib.request
import urllib.error
import psycopg2
import psycopg2.extras
from datetime import date, datetime, timedelta, timezone
from functools import wraps

from flask import (Flask, g, redirect, render_template, request, session,
                   url_for, flash, jsonify, Response, abort, make_response)
from werkzeug.security import check_password_hash, generate_password_hash
from urllib.parse import quote as _urlquote


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-please-very-secret")
# رفعنا الحد عشان الصوت ميتقطعش
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB upload cap

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_SCHEMA_READY = False
def _ensure_schema():
    global _SCHEMA_READY
    if _SCHEMA_READY: return
    try:
        init_db()
        _SCHEMA_READY = True
    except Exception as e:
        print("init_db error:", e)


# ---------- قاعدة البيانات ----------
def get_db():
    if "db" not in g:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        conn.autocommit = False
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """يُستدعى مرة واحدة لإنشاء الجداول"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'worker',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            day DATE NOT NULL,
            checked_in_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, day)
        );
        CREATE TABLE IF NOT EXISTS vaccinations (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            day DATE NOT NULL,
            count INTEGER NOT NULL CHECK(count >= 0),
            note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS day_closures (
            day DATE PRIMARY KEY,
            closed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            closed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            total_count INTEGER NOT NULL DEFAULT 0
        );
        ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS total_count INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS tasmeen_after INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS bayad_after INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS extra_tasmeen INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS extra_bayad INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS no_deduct_total INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS reopened BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE attendance ADD COLUMN IF NOT EXISTS farm TEXT NOT NULL DEFAULT 'tasmeen';
        ALTER TABLE attendance ADD COLUMN IF NOT EXISTS extra BOOLEAN NOT NULL DEFAULT FALSE;
        CREATE INDEX IF NOT EXISTS idx_attendance_day_farm ON attendance(day, farm);

        -- ملاحظات المسؤول (سلف / تنويهات)
        CREATE TABLE IF NOT EXISTS admin_notes (
            id SERIAL PRIMARY KEY,
            admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            title TEXT,
            body TEXT NOT NULL,
            color TEXT NOT NULL DEFAULT 'gold',
            pinned BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_admin_notes_created ON admin_notes(created_at DESC);

        -- مكالمات صوتية (جروب أو خاص)
        CREATE TABLE IF NOT EXISTS voice_calls (
            id SERIAL PRIMARY KEY,
            scope TEXT NOT NULL,            -- 'group' | 'dm'
            dm_a INTEGER REFERENCES users(id) ON DELETE CASCADE,
            dm_b INTEGER REFERENCES users(id) ON DELETE CASCADE,
            started_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ended_at TIMESTAMPTZ,
            active BOOLEAN NOT NULL DEFAULT TRUE
        );
        CREATE INDEX IF NOT EXISTS idx_voice_calls_scope_active ON voice_calls(scope, active);
        CREATE INDEX IF NOT EXISTS idx_voice_calls_dm ON voice_calls(dm_a, dm_b, active);

        CREATE TABLE IF NOT EXISTS voice_participants (
            id SERIAL PRIMARY KEY,
            call_id INTEGER NOT NULL REFERENCES voice_calls(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            left_at TIMESTAMPTZ,
            last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(call_id, user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_voice_participants_call ON voice_participants(call_id);

        CREATE TABLE IF NOT EXISTS voice_signals (
            id SERIAL PRIMARY KEY,
            call_id INTEGER NOT NULL REFERENCES voice_calls(id) ON DELETE CASCADE,
            from_user INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            to_user INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            payload TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_voice_signals_recv ON voice_signals(call_id, to_user, id);

        ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar TEXT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS cover TEXT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ;

        -- جدول رسايل الشات الفردي
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind TEXT NOT NULL DEFAULT 'text',
            body TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            read_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS idx_chat_pair_a ON chat_messages(sender_id, receiver_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_chat_pair_b ON chat_messages(receiver_id, sender_id, created_at);

        -- نخلي عمود الوقت timestamptz (لو قديم بدون tz)
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name='chat_messages' AND column_name='created_at' AND data_type='timestamp without time zone') THEN
                ALTER TABLE chat_messages ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';
                ALTER TABLE chat_messages ALTER COLUMN read_at TYPE TIMESTAMPTZ USING read_at AT TIME ZONE 'UTC';
            END IF;
        EXCEPTION WHEN OTHERS THEN NULL; END $$;

        -- جدول إعدادات المجموعة
        CREATE TABLE IF NOT EXISTS group_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            name TEXT NOT NULL DEFAULT 'دردشة العمال',
            avatar TEXT,
            is_locked BOOLEAN NOT NULL DEFAULT FALSE,
            CHECK (id = 1)
        );
        ALTER TABLE group_settings ADD COLUMN IF NOT EXISTS is_locked BOOLEAN NOT NULL DEFAULT FALSE;
        INSERT INTO group_settings (id, name) VALUES (1, 'دردشة العمال') ON CONFLICT DO NOTHING;

        -- جدول رسايل المجموعة
        CREATE TABLE IF NOT EXISTS group_messages (
            id SERIAL PRIMARY KEY,
            sender_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            kind TEXT NOT NULL DEFAULT 'text',
            body TEXT,
            pinned BOOLEAN NOT NULL DEFAULT FALSE,
            deleted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_group_created ON group_messages(created_at DESC);

        -- آخر قراءة لكل مستخدم للمجموعة
        -- ملخص الفترة (نصف شهر) — عشان مانبعتش نفس الرسالة تاني
        CREATE TABLE IF NOT EXISTS period_summaries (
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            half INTEGER NOT NULL CHECK (half IN (1,2)),
            total INTEGER NOT NULL DEFAULT 0,
            posted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (year, month, half)
        );
        -- تقارير فترة مخصّصة (المسؤول يحدد من/إلى)
        CREATE TABLE IF NOT EXISTS range_reports (
            id SERIAL PRIMARY KEY,
            admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            start_day DATE NOT NULL,
            end_day DATE NOT NULL,
            total INTEGER NOT NULL DEFAULT 0,
            days_count INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS group_reads (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            last_read_id INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        -- ==== إشعارات (داخل التطبيق + FCM لاحقًا) ====
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            body  TEXT,
            url   TEXT,
            type  TEXT NOT NULL DEFAULT 'general',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            read_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS idx_notif_user_created ON notifications(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_notif_user_unread ON notifications(user_id) WHERE read_at IS NULL;

        -- توكنات FCM لكل مستخدم (لدفع الإشعارات لتطبيق Sketchware)
        CREATE TABLE IF NOT EXISTS fcm_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token TEXT NOT NULL UNIQUE,
            platform TEXT NOT NULL DEFAULT 'android',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        -- ==== دعم الرد + المنشن ====
        ALTER TABLE chat_messages  ADD COLUMN IF NOT EXISTS reply_to_id INTEGER;
        ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS reply_to_id INTEGER;
        ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS mentions    TEXT;  -- JSON list of user ids
        ALTER TABLE chat_messages  ADD COLUMN IF NOT EXISTS edited_at   TIMESTAMPTZ;
        ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS edited_at   TIMESTAMPTZ;

        -- ==== تفاعلات (Reactions) على الرسائل ====
        CREATE TABLE IF NOT EXISTS chat_reactions (
            id SERIAL PRIMARY KEY,
            message_id INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            emoji TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(message_id, user_id, emoji)
        );
        CREATE INDEX IF NOT EXISTS idx_chat_reactions_msg ON chat_reactions(message_id);

        CREATE TABLE IF NOT EXISTS group_reactions (
            id SERIAL PRIMARY KEY,
            message_id INTEGER NOT NULL REFERENCES group_messages(id) ON DELETE CASCADE,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            emoji TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(message_id, user_id, emoji)
        );
        CREATE INDEX IF NOT EXISTS idx_group_reactions_msg ON group_reactions(message_id);

        -- ==== صلاحيات إضافية داخل الجروب ====
        CREATE TABLE IF NOT EXISTS group_perms (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            can_delete BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        -- ==== تعديلات (إضافي / خصم) لكل عامل في يوم معيّن ====
        CREATE TABLE IF NOT EXISTS worker_adjustments (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            day DATE NOT NULL,
            amount INTEGER NOT NULL,       -- + إضافي / - خصم (بالجنيه)
            reason TEXT,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, day)
        );
        CREATE INDEX IF NOT EXISTS idx_wadj_user ON worker_adjustments(user_id, day DESC);

        -- ==== إعدادات النظام (وضع الإيقاف الكامل من المسؤول الرئيسي) ====
        CREATE TABLE IF NOT EXISTS system_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            maintenance_mode BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CHECK (id = 1)
        );
        INSERT INTO system_settings (id) VALUES (1) ON CONFLICT DO NOTHING;
    """)
    # نتأكد إن فيه مسؤول برقم "1"
    cur.execute("SELECT id, username FROM users WHERE role='admin' ORDER BY id ASC LIMIT 1")
    admin_row = cur.fetchone()
    if not admin_row:
        # نشوف لو فيه مستخدم قديم اسمه admin نحوّل رقمه لـ 1
        cur.execute("SELECT id FROM users WHERE username='admin'")
        legacy = cur.fetchone()
        if legacy:
            cur.execute("UPDATE users SET username='1', role='admin' WHERE id=%s", (legacy[0],))
        else:
            cur.execute(
                "INSERT INTO users(username, full_name, password_hash, role) VALUES(%s,%s,%s,%s)",
                ("1", "المسؤول", generate_password_hash("admin123"), "admin"),
            )
    else:
        # لو المسؤول موجود لكن اسم المستخدم مش رقم — نخليه "1"
        uname = (admin_row[1] or "").strip()
        if not uname.isdigit():
            # نتأكد إن "1" فاضية قبل ما نستخدمها
            cur.execute("SELECT 1 FROM users WHERE username='1'")
            if not cur.fetchone():
                cur.execute("UPDATE users SET username='1' WHERE id=%s", (admin_row[0],))
    conn.commit()
    cur.close()
    conn.close()


def _next_free_userid(cur):
    """يرجّع أصغر رقم موجب مش مستخدم كـ username — عشان لو حد اتحذف يستخدم رقمه"""
    cur.execute(
        "SELECT username FROM users WHERE username ~ '^[0-9]+$'"
    )
    taken = set()
    for r in cur.fetchall():
        try:
            v = r["username"] if isinstance(r, dict) or hasattr(r, "get") else r[0]
            taken.add(int(v))
        except (ValueError, TypeError):
            pass
    n = 1
    while n in taken:
        n += 1
    return str(n)


# ---------- مساعدات ----------
def _load_user(uid):
    if not uid:
        return None
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (uid,))
    row = cur.fetchone()
    cur.close()
    return row


def current_user():
    # المسؤول الرئيسي ممكن ينتحل شخصية عامل — نرجّع العامل ونحفظ الأصلي في real_user
    imp = session.get("impersonate_id")
    if imp:
        u = _load_user(imp)
        if u:
            return u
        # لو مش موجود نمسح الانتحال
        session.pop("impersonate_id", None)
    return _load_user(session.get("user_id"))


def real_user():
    """المستخدم الحقيقي المسجّل دخول (بدون انتحال)."""
    return _load_user(session.get("user_id"))



@app.before_request
def _boot():
    _ensure_schema()
    uid = session.get("user_id")
    if uid:
        try:
            db = get_db()
            cur = db.cursor()
            cur.execute("UPDATE users SET last_seen = NOW() WHERE id = %s", (uid,))
            db.commit()
            cur.close()
        except Exception:
            pass
    # وضع الإيقاف الكامل: كل المستخدمين ممنوعين ما عدا المسؤول الرئيسي (username='1')
    try:
        ep = request.endpoint or ""
        # نسمح دايمًا بالملفات الثابتة والدخول والخروج وزر التشغيل/الإيقاف نفسه
        _always_allowed = {"static", "admin_toggle_maintenance"}
        if ep not in _always_allowed and _maintenance_on():
            ru = real_user()
            if not _is_super_admin(ru):
                # لا نسجّل خروج أي حد — بس نعرض صفحة "تم إيقاف التطبيق من المطور"
                return render_template("maintenance.html"), 503
    except Exception:
        pass


def _maintenance_on():
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT maintenance_mode FROM system_settings WHERE id=1")
        row = cur.fetchone()
        cur.close()
        if not row:
            return False
        val = row["maintenance_mode"] if isinstance(row, dict) or hasattr(row, "get") else row[0]
        return bool(val)
    except Exception:
        return False



def _iso_utc(dt):
    """ترجع ISO بنهاية Z عشان المتصفح يفهمها UTC ويعرضها بتوقيت الجهاز"""
    if dt is None:
        return None
    # لو جاي string من قاعدة البيانات نحاول نحوله
    if isinstance(dt, str):
        try:
            from datetime import datetime as _dt
            dt = _dt.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return dt
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------- تفاعلات الرسائل ----------
ALLOWED_REACTIONS = {"👍", "❤️", "😂", "😮", "😢", "🙏"}

def _reactions_for(cur, table, msg_ids, me_id):
    """يرجّع dict: msg_id -> [{emoji, count, mine}] مرتب حسب أول تفاعل"""
    if not msg_ids:
        return {}
    cur.execute(
        f"SELECT message_id, emoji, user_id FROM {table} "
        f"WHERE message_id = ANY(%s) ORDER BY id ASC",
        (list(msg_ids),),
    )
    agg = {}
    for r in cur.fetchall():
        mid = r["message_id"]; emo = r["emoji"]
        bucket = agg.setdefault(mid, {})
        e = bucket.get(emo)
        if not e:
            e = {"emoji": emo, "count": 0, "mine": False, "_order": len(bucket)}
            bucket[emo] = e
        e["count"] += 1
        if r["user_id"] == me_id:
            e["mine"] = True
    out = {}
    for mid, bucket in agg.items():
        arr = sorted(bucket.values(), key=lambda x: x["_order"])
        for x in arr: x.pop("_order", None)
        out[mid] = arr
    return out


def _toggle_reaction(table, message_id, user_id, emoji):
    if emoji not in ALLOWED_REACTIONS:
        return None, "bad_emoji"
    db = get_db(); cur = db.cursor()
    cur.execute(
        f"DELETE FROM {table} WHERE message_id=%s AND user_id=%s AND emoji=%s",
        (message_id, user_id, emoji),
    )
    removed = cur.rowcount > 0
    if not removed:
        cur.execute(
            f"INSERT INTO {table}(message_id, user_id, emoji) VALUES(%s,%s,%s) "
            f"ON CONFLICT DO NOTHING",
            (message_id, user_id, emoji),
        )
    db.commit()
    reactions = _reactions_for(cur, table, [message_id], user_id).get(message_id, [])
    cur.close()
    return reactions, None


def is_day_closed(day_s):
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS reopened BOOLEAN NOT NULL DEFAULT FALSE")
        db.commit()
    except Exception:
        db.rollback()
    cur.execute("SELECT total_count, reopened FROM day_closures WHERE day=%s", (day_s,))
    _row = cur.fetchone()
    cur.close()
    if not _row:
        return False
    # اليوم اللي اتعاد فتحه يعتبر مش مقفول
    return not bool(_row["reopened"])


def get_day_closure_total(day_s):
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS reopened BOOLEAN NOT NULL DEFAULT FALSE")
        db.commit()
    except Exception:
        db.rollback()
    cur.execute("SELECT total_count, reopened FROM day_closures WHERE day=%s", (day_s,))
    _row = cur.fetchone()
    cur.close()
    if not _row:
        return None
    if bool(_row["reopened"]):
        return None
    return _row["total_count"]


def _farm_label(farm):
    return "بياض" if farm == "bayad" else ("تسمين" if farm == "tasmeen" else "")


def _closure_total_for_farm(row, farm):
    """يرجع رقم القسم الذي حضر فيه العامل فقط، بدون جمع التسمين والبياض."""
    if not row or farm not in ("tasmeen", "bayad"):
        return 0
    total_count = int(row.get("total_count") or 0)
    tasmeen_after = int(row.get("tasmeen_after") or 0)
    bayad_after = int(row.get("bayad_after") or 0)
    # توافق مع الأيام القديمة قبل فصل التسمين/البياض: القديم يُعامل كتسمين فقط.
    if farm == "tasmeen":
        return tasmeen_after if (tasmeen_after or bayad_after) else total_count
    return bayad_after


def _worker_closed_day_total(cur, day_s, user_id):
    """إجمالي اليوم للعامل = إجمالي القسم الذي حضر فيه فقط."""
    cur.execute("""
        SELECT c.total_count, COALESCE(c.tasmeen_after,0) AS tasmeen_after,
               COALESCE(c.bayad_after,0) AS bayad_after,
               COALESCE(c.reopened,FALSE) AS reopened,
               (SELECT a.farm FROM attendance a WHERE a.day=c.day AND a.user_id=%s LIMIT 1) AS my_farm
        FROM day_closures c
        WHERE c.day=%s
    """, (user_id, day_s))
    row = cur.fetchone()
    if not row or bool(row["reopened"]) or not row["my_farm"]:
        return None, None
    return _closure_total_for_farm(row, row["my_farm"]), row["my_farm"]


def _visible_group_body_for_user(body, kind, user):
    """إخفاء أرقام الإغلاق/ملخص الفترة عن العمال؛ تظهر للمسؤول فقط."""
    text = body or ""
    if not user or user.get("role") == "admin":
        return text
    if kind == "attendance" and ("[CLOSED:" in text or "تم إغلاق اليوم" in text or "إغلاق يوم" in text):
        return "[ICON:check] تم إغلاق اليوم\nالأرقام تظهر لكل عامل حسب القسم الذي حضر فيه فقط من صفحته."
    if kind == "system" and "ملخص" in text:
        return "[ICON:chart] ملخص الفترة\nالأرقام تظهر للمسؤول فقط."
    return text


def _purge_closure_message(cur, day):
    """يحذف/ينضف رسايل ملخّص إغلاق اليوم اللي فيها ماركر [CLOSED:{day}]."""
    import re as _re
    marker = f"[CLOSED:{day}]"
    cur.execute(
        "SELECT id, body FROM group_messages WHERE kind='attendance' AND deleted=FALSE AND body LIKE %s",
        (f"%{marker}%",),
    )
    rows = cur.fetchall() or []
    pat = _re.compile(r"\n*\[ICON:check\] تم إغلاق اليوم[\s\S]*?\[CLOSED:" + _re.escape(day) + r"\]")
    for r in rows:
        body = r["body"] or ""
        stand_prefix = f"[ICON:clipboard] إغلاق يوم {day}"
        if body.startswith(stand_prefix):
            # رسالة مستقلّة للإغلاق — نمسحها بالكامل
            cur.execute("UPDATE group_messages SET deleted=TRUE, pinned=FALSE WHERE id=%s", (r["id"],))
        else:
            new_body = pat.sub("", body).rstrip()
            cur.execute("UPDATE group_messages SET body=%s WHERE id=%s", (new_body, r["id"]))


def login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return w


def admin_required(f):
    @wraps(f)
    def w(*a, **kw):
        u = current_user()
        if not u or u["role"] != "admin":
            flash("هذه الصفحة للمسؤول فقط", "error")
            return redirect(url_for("dashboard"))
        return f(*a, **kw)
    return w


def _is_super_admin(u):
    # المسؤول الرئيسي فقط (اللي username = '1') هو اللي يقدر يدير المستخدمين
    return bool(u and u.get("role") == "admin" and str(u.get("username")) == "1")


def super_admin_required(f):
    @wraps(f)
    def w(*a, **kw):
        u = current_user()
        if not _is_super_admin(u):
            flash("هذه الصفحة للمسؤول الرئيسي فقط", "error")
            return redirect(url_for("admin_panel") if u and u["role"] == "admin" else url_for("dashboard"))
        return f(*a, **kw)
    return w


@app.context_processor
def inject_user():
    u = current_user()
    sidebar_workers = []
    if u:
        try:
            db = get_db()
            cur = db.cursor()
            # المسؤول يشوف الكل (بما فيهم نفسه عشان يحسب لنفسه لو حضر)
            # العامل يشوف نفسه بس
            if u["role"] == "admin":
                cur.execute("SELECT id, full_name, username, role, avatar FROM users ORDER BY (role='admin') DESC, full_name")
            else:
                cur.execute("SELECT id, full_name, username, role, avatar FROM users WHERE id=%s", (u["id"],))
            sidebar_workers = cur.fetchall()
            cur.close()
        except Exception:
            sidebar_workers = []
    ru = real_user()
    impersonator = ru if (ru and session.get("impersonate_id") and _is_super_admin(ru)) else None
    return {
        "current_user": u,
        "today": date.today().isoformat(),
        "sidebar_workers": sidebar_workers,
        "is_super_admin": _is_super_admin(u),
        "impersonator": impersonator,
        "is_real_super_admin": _is_super_admin(ru),
    }


# ---------- انتحال شخصية (المسؤول الرئيسي فقط) ----------
@app.route("/admin/impersonate/<int:uid>", methods=["POST", "GET"])
@login_required
def admin_impersonate(uid):
    ru = real_user()
    if not _is_super_admin(ru):
        flash("هذه الميزة للمسؤول الرئيسي فقط", "error")
        return redirect(url_for("dashboard"))
    if uid == ru["id"]:
        session.pop("impersonate_id", None)
        return redirect(url_for("admin_panel"))
    target = _load_user(uid)
    if not target:
        flash("المستخدم غير موجود", "error")
        return redirect(url_for("admin_panel"))
    session["impersonate_id"] = uid
    flash("تم الدخول بحساب: " + (target["full_name"] or ""), "success")
    if target["role"] == "admin":
        return redirect(url_for("admin_panel"))
    return redirect(url_for("dashboard"))


@app.route("/admin/unimpersonate", methods=["POST", "GET"])
@login_required
def admin_unimpersonate():
    session.pop("impersonate_id", None)
    flash("رجعت لحساب المسؤول ✓", "success")
    return redirect(url_for("admin_panel"))


# ---------- تعديل الرسائل (نص فقط، صاحبها فقط) ----------
@app.route("/chat/edit/<int:msg_id>", methods=["POST"])
@login_required
def chat_edit_msg(msg_id):
    u = current_user()
    new_body = (request.form.get("body") or "").strip()
    if not new_body:
        return jsonify({"ok": False, "error": "empty"}), 400
    if len(new_body) > 4000:
        new_body = new_body[:4000]
    db = get_db(); cur = db.cursor()
    cur.execute("SELECT sender_id, kind FROM chat_messages WHERE id=%s", (msg_id,))
    r = cur.fetchone()
    if not r:
        cur.close(); return jsonify({"ok": False, "error": "not_found"}), 404
    if r["sender_id"] != u["id"] or r["kind"] != "text":
        cur.close(); return jsonify({"ok": False, "error": "forbidden"}), 403
    cur.execute("UPDATE chat_messages SET body=%s, edited_at=NOW() WHERE id=%s", (new_body, msg_id))
    db.commit(); cur.close()
    return jsonify({"ok": True, "id": msg_id, "body": new_body, "edited": True})


@app.route("/group/edit/<int:msg_id>", methods=["POST"])
@login_required
def group_edit_msg(msg_id):
    u = current_user()
    new_body = (request.form.get("body") or "").strip()
    if not new_body:
        return jsonify({"ok": False, "error": "empty"}), 400
    if len(new_body) > 4000:
        new_body = new_body[:4000]
    db = get_db(); cur = db.cursor()
    cur.execute("SELECT sender_id, kind, deleted FROM group_messages WHERE id=%s", (msg_id,))
    r = cur.fetchone()
    if not r:
        cur.close(); return jsonify({"ok": False, "error": "not_found"}), 404
    if r["deleted"] or r["sender_id"] != u["id"] or r["kind"] != "text":
        cur.close(); return jsonify({"ok": False, "error": "forbidden"}), 403
    cur.execute("UPDATE group_messages SET body=%s, edited_at=NOW() WHERE id=%s", (new_body, msg_id))
    db.commit(); cur.close()
    return jsonify({"ok": True, "id": msg_id, "body": new_body, "edited": True})


# ---------- مسارات أساسية ----------
@app.route("/")
def index():
    return redirect(url_for("splash"))


@app.route("/welcome")
def splash():
    if session.get("user_id"):
        next_url = url_for("dashboard")
    else:
        next_url = url_for("login")
    return render_template("splash.html", next_url=next_url)


@app.route("/sw.js")
def _service_worker():
    from flask import send_from_directory
    import os as _os
    resp = send_from_directory(_os.path.join(app.root_path, "static"), "sw.js")
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@app.route("/offline")
def _offline_page():
    return render_template("offline.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip() or request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        cur = db.cursor()
        # نسمح بالدخول بالاسم الكامل أو برقم المستخدم (username)
        # 1) لو رقم — نبحث في username
        row = None
        if identifier.isdigit():
            cur.execute("SELECT * FROM users WHERE username=%s", (identifier,))
            row = cur.fetchone()
        # 2) لو مش رقم أو مش موجود — نبحث بالاسم الكامل (case-insensitive)
        if not row:
            cur.execute("SELECT * FROM users WHERE LOWER(TRIM(full_name))=LOWER(TRIM(%s)) ORDER BY id ASC LIMIT 1",
                        (identifier,))
            row = cur.fetchone()
        # 3) fallback على username كنص
        if not row:
            cur.execute("SELECT * FROM users WHERE username=%s", (identifier,))
            row = cur.fetchone()
        cur.close()
        if row and check_password_hash(row["password_hash"], password):
            session["user_id"] = row["id"]
            return redirect(url_for("dashboard"))
        flash("الاسم أو كلمة السر غير صحيحة", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    resp = redirect(url_for("login"))
    # امسح كوكيز الجلسة صراحة عشان لا يرجع تلقائي بعد الخروج
    try:
        resp.delete_cookie(app.session_cookie_name if hasattr(app, "session_cookie_name") else "session",
                           path="/")
    except Exception:
        try: resp.delete_cookie("session", path="/")
        except Exception: pass
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'
    return resp


@app.after_request
def _no_store_on_auth(resp):
    # صفحات المستخدمين المسجّلين مش المفروض تتكاش عشان مايرجعش من زر الرجوع بعد الخروج
    try:
        if session.get("user_id") and (request.endpoint or "") not in ("static",):
            resp.headers.setdefault("Cache-Control", "no-store, no-cache, must-revalidate, private, max-age=0")
            resp.headers.setdefault("Pragma", "no-cache")
    except Exception:
        pass
    return resp


@app.route("/register", methods=["GET", "POST"])
def register():
    # إنشاء الحسابات متاح للمسؤول الرئيسي فقط من لوحة إدارة المستخدمين
    flash("إنشاء الحسابات متاح للمسؤول الرئيسي فقط من لوحة الإدارة", "error")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    u = current_user()
    if u["role"] == "admin":
        return redirect(url_for("admin_panel"))

    db = get_db()
    cur = db.cursor()
    today = date.today().isoformat()
    closure_total = get_day_closure_total(today)
    closed = closure_total is not None

    cur.execute("SELECT farm FROM attendance WHERE user_id=%s AND day=%s", (u["id"], today))
    my_attendance = cur.fetchone()
    checked_in = my_attendance is not None
    my_farm = my_attendance["farm"] if my_attendance else None

    cur.execute("SELECT COALESCE(SUM(count),0) AS s FROM vaccinations WHERE user_id=%s AND day=%s",
                (u["id"], today))
    my_total = cur.fetchone()["s"]

    if closed:
        team_total, my_farm = _worker_closed_day_total(cur, today, u["id"])
        team_total = team_total or 0
    else:
        cur.execute("SELECT COALESCE(SUM(count),0) AS s FROM vaccinations WHERE day=%s", (today,))
        team_total = cur.fetchone()["s"]

    if my_farm:
        cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE day=%s AND farm=%s", (today, my_farm))
        present_count = cur.fetchone()["c"]
    else:
        present_count = 0

    present_list = []
    if closed and my_farm:
        cur.execute("""
            SELECT u.id, u.full_name, u.avatar
            FROM attendance a JOIN users u ON u.id=a.user_id
            WHERE a.day=%s AND a.farm=%s ORDER BY u.full_name
        """, (today, my_farm))
        present_list = cur.fetchall()

    cur.execute("""SELECT v.*, u.full_name FROM vaccinations v
                   JOIN users u ON u.id=v.user_id
                   WHERE v.user_id=%s ORDER BY v.created_at DESC LIMIT 5""",
                (u["id"],))
    recent = cur.fetchall()
    cur.close()

    return render_template(
        "dashboard.html",
        checked_in=checked_in,
        my_total=my_total,
        team_total=team_total,
        present_count=present_count,
        recent=recent,
        day_closed=closed,
        present_list=present_list,
        my_farm_label=_farm_label(my_farm),
    )


@app.route("/check-in", methods=["POST"])
@login_required
def check_in():
    u = current_user()
    today = date.today().isoformat()
    if is_day_closed(today):
        flash("اليوم مغلق من المسؤول — لا يمكن تسجيل حضور جديد", "error")
        return redirect(url_for("dashboard"))
    db = get_db()
    cur = db.cursor()
    farm = request.form.get("farm") if request.form.get("farm") in ("tasmeen", "bayad") else "tasmeen"
    try:
        cur.execute(
            "INSERT INTO attendance(user_id, day, farm) VALUES(%s,%s,%s)",
            (u["id"], today, farm),
        )
        db.commit()
        flash("تم تسجيل حضورك اليوم", "success")
    except psycopg2.IntegrityError:
        db.rollback()
        cur.execute("UPDATE attendance SET farm=%s WHERE user_id=%s AND day=%s", (farm, u["id"], today))
        db.commit()
        flash("تم تحديث نوع الحضور", "success")
    finally:
        cur.close()
    nxt = request.form.get("next") or url_for("dashboard")
    return redirect(nxt)


@app.route("/history")
@login_required
def history():
    import calendar
    u = current_user()
    is_admin = (u and u["role"] == "admin")
    db = get_db()
    cur = db.cursor()
    if is_admin:
        cur.execute("""
            SELECT c.day, c.total_count, COALESCE(c.no_deduct_total,0) AS no_deduct_total,
                   COALESCE(c.tasmeen_after,0) AS tasmeen_after,
                   COALESCE(c.bayad_after,0) AS bayad_after,
                   COALESCE(ARRAY_AGG(u.full_name ORDER BY u.full_name)
                            FILTER (WHERE u.full_name IS NOT NULL), '{}') AS names,
                   COALESCE(ARRAY_AGG(u.id ORDER BY u.full_name)
                            FILTER (WHERE u.id IS NOT NULL), '{}') AS ids,
                   COALESCE(ARRAY_AGG(a.farm ORDER BY u.full_name)
                            FILTER (WHERE a.farm IS NOT NULL), '{}') AS farms
            FROM day_closures c
            LEFT JOIN attendance a ON a.day = c.day
            LEFT JOIN users u ON u.id = a.user_id
            GROUP BY c.day, c.total_count, c.no_deduct_total, c.tasmeen_after, c.bayad_after
        """)
        by_day = {r["day"]: {"total": r["total_count"],
                              "no_deduct_total": r["no_deduct_total"],
                              "tasmeen_after": int(r["tasmeen_after"] or 0),
                              "bayad_after": int(r["bayad_after"] or 0),
                              "names": list(r["names"] or []),
                              "ids": list(r["ids"] or []),
                              "farms": list(r["farms"] or []),
                              "farm": ""}
                  for r in cur.fetchall()}
    else:
        cur.execute("""
            SELECT c.day, c.total_count, COALESCE(c.tasmeen_after,0) AS tasmeen_after,
                   COALESCE(c.bayad_after,0) AS bayad_after,
                   COALESCE(c.no_deduct_total,0) AS no_deduct_total,
                   a_self.farm AS my_farm,
                   COALESCE(ARRAY_AGG(u.full_name ORDER BY u.full_name)
                            FILTER (WHERE u.full_name IS NOT NULL), '{}') AS names,
                   COALESCE(ARRAY_AGG(u.id ORDER BY u.full_name)
                            FILTER (WHERE u.id IS NOT NULL), '{}') AS ids,
                   COALESCE(ARRAY_AGG(a.farm ORDER BY u.full_name)
                            FILTER (WHERE a.farm IS NOT NULL), '{}') AS farms
            FROM day_closures c
            JOIN attendance a_self ON a_self.day = c.day AND a_self.user_id = %s
            LEFT JOIN attendance a ON a.day = c.day AND a.farm = a_self.farm
            LEFT JOIN users u ON u.id = a.user_id
            WHERE COALESCE(c.reopened,FALSE) = FALSE
            GROUP BY c.day, c.total_count, c.tasmeen_after, c.bayad_after, c.no_deduct_total, a_self.farm
        """, (u["id"],))
        by_day = {r["day"]: {"total": _closure_total_for_farm(r, r["my_farm"]),
                              "no_deduct_total": 0,
                              "names": list(r["names"] or []),
                              "ids": list(r["ids"] or []),
                              "farms": list(r["farms"] or []),
                              "farm": _farm_label(r["my_farm"])}
                  for r in cur.fetchall()}

    # قائمة كل العمال (للمسؤول عشان يقدر يعدّل الحضور من السجل)
    all_workers = []
    if is_admin:
        # نعرض كل الأعضاء (عمال ومسؤولين + المسؤول الرئيسي) بدون تمييز — لتعديل الحضور من غير كشف مين مسؤول
        cur.execute("SELECT id, full_name FROM users ORDER BY full_name")
        all_workers = [{"id": r["id"], "full_name": r["full_name"]} for r in cur.fetchall()]
    cur.close()

    today = date.today()
    # نفس السجل لكل الناس (عامل أو مسؤول) — من غير أي تصفير تلقائي.
    # البيانات فضل ظاهرة لحد ما المسؤول يصفّرها يدويًا من زرار "تصفير الفترة".
    months = set((d.year, d.month) for d in by_day.keys())
    months.add((today.year, today.month))
    current_half = 1 if today.day <= 15 else 2
    periods = []
    AR_DAYS = ["الإثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"]
    AR_MONTHS = ["يناير","فبراير","مارس","أبريل","مايو","يونيو",
                 "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]
    for (y, m) in sorted(months, reverse=True):
        last_day = calendar.monthrange(y, m)[1]
        for half, (start, end) in enumerate([(1, 15), (16, last_day)], start=1):
            days_list = []
            for dnum in range(start, end + 1):
                d = date(y, m, dnum)
                wd = d.weekday()
                is_friday = (wd == 4)
                rec = by_day.get(d)
                days_list.append({
                    "date": d.isoformat(),
                    "day_num": dnum,
                    "weekday": AR_DAYS[wd],
                    "holiday": is_friday,
                    "total": rec["total"] if rec else 0,
                    "tasmeen_after": (rec.get("tasmeen_after", 0) if rec else 0),
                    "bayad_after": (rec.get("bayad_after", 0) if rec else 0),
                    "no_deduct_total": rec["no_deduct_total"] if rec else 0,
                    "names": rec["names"] if rec else [],
                    "attendee_ids": rec["ids"] if rec else [],
                    "attendee_farms": (rec.get("farms", []) if rec else []),
                    "farm": rec["farm"] if rec else "",
                    "has_data": rec is not None,
                })
            periods.append({
                "label": f"{AR_MONTHS[m-1]} {y} — {'النصف الأول (1-15)' if half==1 else f'النصف الثاني (16-{last_day})'}",
                "days": days_list,
                "is_current": (y == today.year and m == today.month and half == current_half),
            })
    return render_template("history.html", periods=periods, all_workers=all_workers)


# ---------- إحصائيات العامل الشهرية (نصيبه) ----------
@app.route("/worker/<int:worker_id>/stats")
@login_required
def worker_stats(worker_id):
    """
    يعرض كل المدد (نصف الشهر) اللي فيها بيانات للعامل — والمدة الحالية.
    المدة متفضل ظاهرة عند العامل حتى بعد نهاية الشهر لحد ما المسؤول يأكد
    استلام الأموال ويصفّر المدة (endpoint: admin_worker_clear_period)،
    وقتها البيانات بتتشال من قاعدة البيانات كمان.
    """
    import calendar as _cal
    me = current_user()
    if me["role"] != "admin" and me["id"] != worker_id:
        flash("مش مسموحلك تشوف صفحة عامل تاني", "error")
        return redirect(url_for("dashboard"))

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, full_name, username, role, avatar FROM users WHERE id=%s", (worker_id,))
    worker = cur.fetchone()
    if not worker:
        cur.close()
        flash("العامل مش موجود", "error")
        return redirect(url_for("dashboard"))

    # جداول التصفيات/التعديلات — نتأكد إنها موجودة
    cur.execute("""CREATE TABLE IF NOT EXISTS worker_adjustments (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        day DATE NOT NULL,
        amount INTEGER NOT NULL,
        reason TEXT,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(user_id, day))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS worker_settlements (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        day DATE NOT NULL,
        amount INTEGER NOT NULL,
        note TEXT,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS worker_day_settle (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        day DATE NOT NULL,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(user_id, day)
    )""")
    # علامة "تم استلام / تصفير المدة" لكل عامل — من غير ما نلمس الحضور
    cur.execute("""CREATE TABLE IF NOT EXISTS worker_period_clears (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        half INTEGER NOT NULL CHECK(half IN (1,2)),
        cleared_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        cleared_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        total_snapshot INTEGER NOT NULL DEFAULT 0,
        days_snapshot INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (user_id, year, month, half)
    )""")

    # نجيب المدد اللي المسؤول أكّد إنه استلم فلوسها للعامل ده — نخفيها
    cur.execute("""SELECT year, month, half FROM worker_period_clears WHERE user_id=%s""", (worker_id,))
    cleared_keys = set((r["year"], r["month"], r["half"]) for r in cur.fetchall())

    # هات كل (سنة/شهر/نصف) فيه أي بيانات للعامل ده — عشان المدد القديمة
    # اللي لسه المسؤول ما أكّدش استلامها متفضل ظاهره.
    cur.execute("""
        SELECT DISTINCT EXTRACT(YEAR FROM day)::int AS y,
                        EXTRACT(MONTH FROM day)::int AS m,
                        CASE WHEN EXTRACT(DAY FROM day) <= 15 THEN 1 ELSE 2 END AS half
        FROM (
            SELECT day FROM attendance          WHERE user_id=%s
            UNION SELECT day FROM worker_adjustments WHERE user_id=%s
            UNION SELECT day FROM worker_settlements WHERE user_id=%s
            UNION SELECT day FROM worker_day_settle  WHERE user_id=%s
        ) x
    """, (worker_id, worker_id, worker_id, worker_id))
    period_keys = set((r["y"], r["m"], r["half"]) for r in cur.fetchall())

    today = date.today()
    cur_half = 1 if today.day <= 15 else 2
    # المدة الحالية دايماً بتتعرض — حتى لو فاضية
    period_keys.add((today.year, today.month, cur_half))
    # نستبعد المدد اللي المسؤول أكّد استلامها بالفعل
    period_keys = period_keys - cleared_keys
    current_key = (today.year, today.month, cur_half)

    AR_DAYS = ["الإثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"]
    AR_MONTHS = ["يناير","فبراير","مارس","أبريل","مايو","يونيو",
                 "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]

    periods_out = []
    grand_pending_chicks = 0
    grand_pending_money  = 0
    grand_bonus = 0
    grand_deduct = 0
    grand_settled_chicks = 0

    for (y, m, half) in sorted(period_keys, reverse=True):
        last_day = _cal.monthrange(y, m)[1]
        if half == 1:
            start_d = date(y, m, 1);  end_d = date(y, m, min(15, last_day))
        else:
            start_d = date(y, m, 16); end_d = date(y, m, last_day)
        s_iso = start_d.isoformat(); e_iso = end_d.isoformat()

        cur.execute("""
            SELECT c.day, c.total_count,
                   CASE
                     WHEN COALESCE(c.tasmeen_after,0)=0 AND COALESCE(c.bayad_after,0)=0 THEN c.total_count
                     ELSE COALESCE(c.tasmeen_after,0)
                   END AS tasmeen_after,
                   COALESCE(c.bayad_after,0) AS bayad_after,
                   COALESCE(c.extra_tasmeen,0) AS extra_tasmeen,
                   COALESCE(c.extra_bayad,0) AS extra_bayad,
                   (SELECT COUNT(*) FROM attendance a WHERE a.day = c.day) AS attendees,
                   (SELECT COUNT(*) FROM attendance a WHERE a.day = c.day AND a.farm='tasmeen') AS att_tasmeen,
                   (SELECT COUNT(*) FROM attendance a WHERE a.day = c.day AND a.farm='bayad') AS att_bayad,
                   (SELECT COUNT(*) FROM attendance a WHERE a.day = c.day AND a.farm='tasmeen' AND COALESCE(a.extra,FALSE)=TRUE) AS att_extra_tasmeen,
                   (SELECT COUNT(*) FROM attendance a WHERE a.day = c.day AND a.farm='bayad' AND COALESCE(a.extra,FALSE)=TRUE) AS att_extra_bayad,
                   EXISTS(SELECT 1 FROM attendance a2 WHERE a2.day = c.day AND a2.user_id = %s) AS he_attended,
                   (SELECT a3.farm FROM attendance a3 WHERE a3.day = c.day AND a3.user_id = %s LIMIT 1) AS my_farm,
                   COALESCE((SELECT a4.extra FROM attendance a4 WHERE a4.day = c.day AND a4.user_id = %s LIMIT 1), FALSE) AS my_extra
            FROM day_closures c
            WHERE c.day BETWEEN %s AND %s
            ORDER BY c.day ASC
        """, (worker_id, worker_id, worker_id, s_iso, e_iso))
        rows = cur.fetchall()

        cur.execute("""SELECT day, amount, reason FROM worker_adjustments
                       WHERE user_id=%s AND day BETWEEN %s AND %s ORDER BY day ASC""",
                    (worker_id, s_iso, e_iso))
        adj_rows = cur.fetchall()

        cur.execute("""SELECT id, day, amount, note FROM worker_settlements
                       WHERE user_id=%s AND day BETWEEN %s AND %s
                       ORDER BY day ASC, id ASC""",
                    (worker_id, s_iso, e_iso))
        settle_rows = cur.fetchall()

        cur.execute("""SELECT day FROM worker_day_settle
                       WHERE user_id=%s AND day BETWEEN %s AND %s""",
                    (worker_id, s_iso, e_iso))
        _settled_days_set = set()
        for _r in cur.fetchall():
            _d = _r["day"]
            _settled_days_set.add(_d.isoformat() if hasattr(_d, "isoformat") else str(_d))

        days_list = []
        settled_days_list = []
        pending_days_list = []
        total_share = 0.0
        pending_share = 0.0
        settled_share = 0.0
        total_period = 0
        days_attended = 0
        for r in rows:
            d = r["day"]; d_s = d.isoformat() if hasattr(d, "isoformat") else str(d)
            wd = AR_DAYS[d.weekday()] if hasattr(d, "weekday") else ""
            my_farm = r["my_farm"]
            # لو مش حاضر خالص في اليوم ده — بنتخطاه ومنعرضش تاريخه ولا نضيفه للإجمالي
            if not my_farm:
                continue
            if my_farm == "tasmeen":
                farm_total = int(r["tasmeen_after"] or 0)
                farm_att   = int(r["att_tasmeen"] or 0)
                farm_lbl   = "تسمين"
                extra_pool = int(r["extra_tasmeen"] or 0)
                extra_att  = int(r["att_extra_tasmeen"] or 0)
            else:
                farm_total = int(r["bayad_after"] or 0)
                farm_att   = int(r["att_bayad"] or 0)
                farm_lbl   = "بياض"
                extra_pool = int(r["extra_bayad"] or 0)
                extra_att  = int(r["att_extra_bayad"] or 0)
            # إجمالي المدة للعامل = إجمالي القسم اللي حضر فيه فقط (بدون جمع القسم التاني)
            total_period += farm_total
            base_share = (farm_total / farm_att) if farm_att > 0 else 0.0
            extra_share = (extra_pool / extra_att) if (bool(r["my_extra"]) and extra_att > 0) else 0.0
            share = base_share + extra_share
            total_share += share; days_attended += 1
            is_settled = d_s in _settled_days_set
            item = {"date": d_s, "weekday": wd,
                    "chicks": int(share), "chicks_f": round(share, 2),
                    "farm": farm_lbl}
            if is_settled:
                settled_share += share; settled_days_list.append(item)
            else:
                pending_share += share; pending_days_list.append(item)
            days_list.append({"date": d_s, "weekday": wd, "total": farm_total,
                              "attendees": farm_att, "attended": True,
                              "share": round(share, 2), "settled": is_settled,
                              "farm": farm_lbl})

        bonus_list = []; deduct_list = []; bonus_total = 0; deduct_total = 0
        for a in adj_rows:
            d = a["day"]; d_s = d.isoformat() if hasattr(d, "isoformat") else str(d)
            wd = AR_DAYS[d.weekday()] if hasattr(d, "weekday") else ""
            amt = int(a["amount"] or 0)
            item = {"date": d_s, "weekday": wd, "amount": abs(amt), "reason": a["reason"] or ""}
            if amt >= 0: bonus_list.append(item); bonus_total += amt
            else:        deduct_list.append(item); deduct_total += -amt

        settle_list = []; settled_total = 0
        for s in settle_rows:
            d = s["day"]; d_s = d.isoformat() if hasattr(d, "isoformat") else str(d)
            wd = AR_DAYS[d.weekday()] if hasattr(d, "weekday") else ""
            amt = int(s["amount"] or 0)
            settle_list.append({"id": s["id"], "date": d_s, "weekday": wd,
                                "amount": amt, "note": s["note"] or ""})
            settled_total += amt

        pending_chicks   = int(pending_share)
        settled_chicks_i = int(settled_share)
        share_int  = int(total_share)
        pending_money = pending_chicks * 55
        money_egp     = share_int * 55

        is_current = (y == today.year and m == today.month and half == cur_half)
        has_any = bool(rows or adj_rows or settle_rows or _settled_days_set)
        # المدد الفاضية القديمة نتخطاها — بس المدة الحالية بتتعرض دايماً
        if not has_any and not is_current:
            continue

        half_label = "النصف الأول (1-15)" if half == 1 else f"النصف الثاني (16-{last_day})"
        periods_out.append({
            "y": y, "m": m, "half": half,
            "label": f"{AR_MONTHS[m-1]} {y} — {half_label}",
            "is_current": is_current,
            "start": s_iso, "end": e_iso,
            "days": days_list,
            "settled_days_list": settled_days_list,
            "pending_days_list": pending_days_list,
            "bonus_list": bonus_list, "deduct_list": deduct_list,
            "bonus_total": bonus_total, "deduct_total": deduct_total,
            "settle_list": settle_list, "settled_total": settled_total,
            "share_int": share_int, "money_egp": money_egp,
            "pending_chicks": pending_chicks, "settled_chicks": settled_chicks_i,
            "pending_money": pending_money,
            "total_period": total_period, "days_attended": days_attended,
        })

        grand_pending_chicks += pending_chicks
        grand_pending_money  += pending_money
        grand_bonus          += bonus_total
        grand_deduct         += deduct_total
        grand_settled_chicks += settled_chicks_i

    cur.close()

    # ==== المدة الحالية فقط (لعرض "نصيبي هذا الشهر" في الهيرو) ====
    current_pending_chicks = 0
    current_pending_money  = 0
    current_bonus = 0
    current_deduct = 0
    current_settled_chicks = 0
    for _p in periods_out:
        if _p["is_current"]:
            current_pending_chicks = _p["pending_chicks"]
            current_pending_money  = _p["pending_money"]
            current_bonus          = _p["bonus_total"]
            current_deduct         = _p["deduct_total"]
            current_settled_chicks = _p["settled_chicks"]
            break

    return render_template("worker_stats.html",
                           worker=worker,
                           periods=periods_out,
                           grand_pending_chicks=grand_pending_chicks,
                           grand_pending_money=grand_pending_money,
                           grand_bonus=grand_bonus,
                           grand_deduct=grand_deduct,
                           grand_settled_chicks=grand_settled_chicks,
                           current_pending_chicks=current_pending_chicks,
                           current_pending_money=current_pending_money,
                           current_bonus=current_bonus,
                           current_deduct=current_deduct,
                           current_settled_chicks=current_settled_chicks,
                           today_iso=today.isoformat(),
                           is_admin_view=(me["role"] == "admin"),
                           is_self=(me["id"] == worker_id))


# ---- تأكيد استلام الأموال + تصفير مدة (نصف شهر) لعامل ----
@app.route("/admin/worker-clear-period", methods=["POST"])
@admin_required
def admin_worker_clear_period():
    """
    المسؤول يأكد إنه استلم أموال العامل عن المدة دي (نصف شهر).
    مهم: مابنمسحش صفوف الحضور (attendance) عشان توزيع الكتاكيت على باقي
    العمال يفضل زي ما هو. بنعلّم المدة كـ "متسلَّمة" للعامل ده بس، ومسح
    الحاجات الخاصة بيه فقط (تعديلات/تصفيات/محاسبات يومية).
    """
    try:
        user_id = int(request.form.get("user_id") or 0)
        y = int(request.form.get("year") or 0)
        m = int(request.form.get("month") or 0)
        half = int(request.form.get("half") or 0)
    except (TypeError, ValueError):
        flash("مدخلات غير صالحة", "error")
        return redirect(url_for("dashboard"))
    if not (user_id and y and m and half in (1, 2)):
        flash("مدخلات غير صالحة", "error")
        return redirect(url_for("worker_stats", worker_id=user_id or 0))
    import calendar as _cal
    last_day = _cal.monthrange(y, m)[1]
    if half == 1:
        s = date(y, m, 1).isoformat();  e = date(y, m, min(15, last_day)).isoformat()
    else:
        s = date(y, m, 16).isoformat(); e = date(y, m, last_day).isoformat()
    me_u = current_user()
    db = get_db(); cur = db.cursor()
    try:
        cur.execute("""CREATE TABLE IF NOT EXISTS worker_period_clears (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            year INTEGER NOT NULL, month INTEGER NOT NULL,
            half INTEGER NOT NULL CHECK(half IN (1,2)),
            cleared_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            cleared_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            total_snapshot INTEGER NOT NULL DEFAULT 0,
            days_snapshot INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, year, month, half)
        )""")
        # نمسح فقط الحاجات الخاصة بالعامل ده (ملهاش تأثير على غيره) — بدون أي أرشيف
        cur.execute("DELETE FROM worker_adjustments  WHERE user_id=%s AND day BETWEEN %s AND %s", (user_id, s, e))
        cur.execute("DELETE FROM worker_day_settle   WHERE user_id=%s AND day BETWEEN %s AND %s", (user_id, s, e))
        cur.execute("DELETE FROM worker_settlements  WHERE user_id=%s AND day BETWEEN %s AND %s", (user_id, s, e))
        # نسجّل علامة "تم استلام" فقط (بدون snapshot لأي أعداد) — عشان المدة تختفي من نصيبي
        cur.execute("""INSERT INTO worker_period_clears
            (user_id, year, month, half, cleared_by, total_snapshot, days_snapshot)
            VALUES(%s,%s,%s,%s,%s,0,0)
            ON CONFLICT (user_id, year, month, half) DO UPDATE SET
              cleared_at=NOW(), cleared_by=EXCLUDED.cleared_by,
              total_snapshot=0, days_snapshot=0""",
                    (user_id, y, m, half, me_u["id"]))
        db.commit()
        flash("تم تأكيد استلام الأموال وتصفير المدة ✓ — توزيع الكتاكيت على باقي العمال متغيّرش", "success")
    except Exception as ex:
        db.rollback()
        flash("خطأ أثناء التصفير: " + str(ex), "error")
    finally:
        cur.close()
    return redirect(url_for("worker_stats", worker_id=user_id))



# ---------- المسؤول ----------
def _parse_day(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return date.today()


@app.route("/admin")
@admin_required
def admin_panel():
    day = _parse_day(request.args.get("day"))
    day_s = day.isoformat()
    prev_day = (day - timedelta(days=1)).isoformat()
    next_day = (day + timedelta(days=1)).isoformat()
    db = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT u.id, u.full_name, u.username, u.role, u.avatar,
               EXISTS(SELECT 1 FROM attendance a WHERE a.user_id=u.id AND a.day=%s) AS present,
               (SELECT a2.farm FROM attendance a2 WHERE a2.user_id=u.id AND a2.day=%s LIMIT 1) AS farm,
               COALESCE((SELECT SUM(count) FROM vaccinations v WHERE v.user_id=u.id AND v.day=%s),0) AS total
        FROM users u ORDER BY (u.role='admin') DESC, u.full_name
    """, (day_s, day_s, day_s))
    workers = cur.fetchall()

    cur.execute("SELECT COALESCE(SUM(count),0) AS s FROM vaccinations WHERE day=%s", (day_s,))
    day_total = cur.fetchone()["s"]

    cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE day=%s", (day_s,))
    present_count = cur.fetchone()["c"]

    _admin_u = current_user()
    cur.execute("SELECT 1 FROM attendance WHERE user_id=%s AND day=%s", (_admin_u["id"], day_s))
    admin_checked_in = cur.fetchone() is not None
    from datetime import date as _date
    is_today = (day_s == _date.today().isoformat())

    cur.execute("""SELECT v.*, u.full_name FROM vaccinations v
                   JOIN users u ON u.id=v.user_id WHERE v.day=%s
                   ORDER BY v.created_at DESC""", (day_s,))
    entries = cur.fetchall()

    days_bar = []
    for i in range(13, -1, -1):
        d = (day - timedelta(days=i)).isoformat()
        cur.execute("SELECT COALESCE(SUM(count),0) AS s FROM vaccinations WHERE day=%s", (d,))
        s = cur.fetchone()["s"]
        days_bar.append({"day": d, "total": s, "active": d == day_s})

    cur.execute("SELECT total_count, tasmeen_after, bayad_after FROM day_closures WHERE day=%s", (day_s,))
    _row = cur.fetchone()
    closed = _row is not None
    tasmeen_after = int(_row["tasmeen_after"] or 0) if closed else 0
    bayad_after   = int(_row["bayad_after"]   or 0) if closed else 0
    if closed:
        day_total = _row["total_count"]

    # عمال متاحين لإضافتهم في تحضير الغد (للزر الجديد)
    cur.execute("SELECT id, full_name FROM users WHERE role='worker' ORDER BY full_name")
    all_workers = cur.fetchall()

    cur.close()
    tomorrow = (day + timedelta(days=1)).isoformat()
    return render_template(
        "admin.html",
        workers=workers, entries=entries,
        day=day_s, prev_day=prev_day, next_day=next_day,
        day_total=day_total, present_count=present_count,
        days_bar=days_bar, day_closed=closed,
        all_workers=all_workers, tomorrow=tomorrow,
        admin_checked_in=admin_checked_in, is_today=is_today,
        maintenance_on=_maintenance_on(),
        tasmeen_after=tasmeen_after, bayad_after=bayad_after,
    )


@app.route("/admin/toggle-maintenance", methods=["POST"])
@super_admin_required
def admin_toggle_maintenance():
    """المسؤول الرئيسي فقط: يوقف البرنامج لكل الناس أو يشغّله تاني."""
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE system_settings
           SET maintenance_mode = NOT maintenance_mode,
               updated_at = NOW()
         WHERE id = 1
        RETURNING maintenance_mode
    """)
    row = cur.fetchone()
    db.commit()
    cur.close()
    on = bool(row["maintenance_mode"]) if row else False
    if on:
        flash("تم إيقاف البرنامج لكل المستخدمين ⏸️ — أنت الوحيد اللي تقدر تدخل الآن.", "success")
    else:
        flash("تم تشغيل البرنامج من جديد ▶️ — كل المستخدمين يقدروا يدخلوا.", "success")
    return redirect(url_for("admin_panel"))




@app.route("/admin/close-day", methods=["POST"])
@admin_required
def admin_close_day():
    u = current_user()
    day = _parse_day(request.form.get("day")).isoformat()
    try:
        tasmeen_after = int(request.form.get("tasmeen_after", "0") or "0")
        bayad_after = int(request.form.get("bayad_after", "0") or "0")
        extra_tasmeen = int(request.form.get("extra_tasmeen", "0") or "0")
        extra_bayad = int(request.form.get("extra_bayad", "0") or "0")
        if tasmeen_after < 0 or bayad_after < 0 or extra_tasmeen < 0 or extra_bayad < 0:
            raise ValueError
    except ValueError:
        flash("ادخل أعداد صحيحة", "error")
        return redirect(url_for("admin_close_page", day=day))
    total = tasmeen_after + bayad_after
    try:
        no_deduct_total = int(request.form.get("no_deduct_total", "0") or "0")
        if no_deduct_total < 0:
            no_deduct_total = 0
    except ValueError:
        no_deduct_total = 0
    db = get_db()
    cur = db.cursor()
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS total_count INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS tasmeen_after INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS bayad_after INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS extra_tasmeen INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS extra_bayad INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS no_deduct_total INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS reopened BOOLEAN NOT NULL DEFAULT FALSE")
    cur.execute(
        """INSERT INTO day_closures(day, closed_by, total_count, tasmeen_after, bayad_after, extra_tasmeen, extra_bayad, no_deduct_total, reopened)
           VALUES(%s,%s,%s,%s,%s,%s,%s,%s,FALSE)
           ON CONFLICT (day) DO UPDATE SET total_count = EXCLUDED.total_count,
                                             tasmeen_after = EXCLUDED.tasmeen_after,
                                             bayad_after = EXCLUDED.bayad_after,
                                             extra_tasmeen = EXCLUDED.extra_tasmeen,
                                             extra_bayad = EXCLUDED.extra_bayad,
                                            no_deduct_total = EXCLUDED.no_deduct_total,
                                            reopened = FALSE,
                                            closed_by = EXCLUDED.closed_by""",
        (day, u["id"], total, tasmeen_after, bayad_after, extra_tasmeen, extra_bayad, no_deduct_total),
    )
    # ==== نحدّث رسالة الإغلاق: نمسح القديمة (لو موجودة) ونضيف الجديدة بالإجمالي المحدّث ====
    try:
        marker = f"[CLOSED:{day}]"
        # امسح أي ملخّص إغلاق سابق لنفس اليوم (سواء كان مضاف لرسالة تحضير أو رسالة مستقلة)
        _purge_closure_message(cur, day)
        # ندوّر على أحدث رسالة كنوعها attendance و بتاعت نفس اليوم بعد التنضيف
        cur.execute("""SELECT id, body FROM group_messages
                       WHERE kind='attendance' AND deleted=FALSE AND body LIKE %s
                       ORDER BY id DESC LIMIT 1""", (f"%حضور يوم {day}%",))
        att = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE day=%s", (day,))
        present_c = int(cur.fetchone()["c"] or 0)
        summary_line = (
            f"\n\n[ICON:check] تم إغلاق اليوم"
            f"\n- تسمين: {tasmeen_after:,} كتكوت"
            f"\n- بياض: {bayad_after:,} كتكوت"
            + (f"\n- إضافي تسمين: {extra_tasmeen:,} كتكوت" if extra_tasmeen else "")
            + (f"\n- إضافي بياض: {extra_bayad:,} كتكوت" if extra_bayad else "")
            + f"\n- الإجمالي: {total:,} كتكوت"
            + f"\n- الحاضرون: {present_c}"
            + f"\n{marker}"
        )
        if att:
            new_body = (att["body"] or "").rstrip() + summary_line
            cur.execute("UPDATE group_messages SET body=%s, pinned=TRUE WHERE id=%s",
                        (new_body, att["id"]))
        else:
            # ما فيش رسالة حضور لليوم ده — ننشر رسالة إغلاق مثبّتة
            cur.execute("UPDATE group_messages SET pinned=FALSE WHERE pinned=TRUE AND kind='attendance'")
            body_new = f"[ICON:clipboard] إغلاق يوم {day}{summary_line}"
            cur.execute("""INSERT INTO group_messages(sender_id, kind, body, pinned)
                           VALUES (%s, 'attendance', %s, TRUE)""", (u["id"], body_new))
    except Exception as _e:
        print("update pinned attendance error:", _e)

    db.commit()
    cur.close()
    # ==== ملخص الفترة (نصف شهر) — تلقائي في الجروب ====
    try:
        cur = db.cursor()
        import calendar as _cal
        y, m, dnum = [int(x) for x in day.split('-')]
        last_day = _cal.monthrange(y, m)[1]
        is_period_end = (dnum == 15) or (dnum == last_day)
        if is_period_end:
            half = 1 if dnum == 15 else 2
            start_d = f"{y:04d}-{m:02d}-01" if half == 1 else f"{y:04d}-{m:02d}-16"
            end_d   = f"{y:04d}-{m:02d}-15" if half == 1 else f"{y:04d}-{m:02d}-{last_day:02d}"
            cur.execute(
                "SELECT COALESCE(SUM(total_count),0) AS s, COUNT(*) AS c FROM day_closures WHERE day BETWEEN %s AND %s",
                (start_d, end_d),
            )
            row = cur.fetchone()
            period_total = int(row["s"] or 0)
            days_closed = int(row["c"] or 0)
            cur.execute("SELECT 1 FROM period_summaries WHERE year=%s AND month=%s AND half=%s",
                        (y, m, half))
            already = cur.fetchone()
            if not already and period_total > 0:
                AR_MONTHS = ["يناير","فبراير","مارس","أبريل","مايو","يونيو",
                             "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]
                half_lbl = f"النصف الأول (1-15)" if half == 1 else f"النصف الثاني (16-{last_day})"
                body = (
                    "[ICON:chart] ملخص " + half_lbl + " من " + AR_MONTHS[m-1] + f" {y}\n"
                    + f"- الإجمالي: {period_total:,} كتكوت\n"
                    + f"- عدد أيام العمل: {days_closed}\n"
                    + f"- الفترة: {start_d} → {end_d}"
                )
                cur.execute("""INSERT INTO group_messages(sender_id, kind, body, pinned)
                               VALUES (%s, 'system', %s, TRUE)""", (u["id"], body))
                # نلغي تثبيت أى ملخّص فتره قديم
                cur.execute("""UPDATE group_messages SET pinned=FALSE
                               WHERE pinned=TRUE AND kind='system' AND id <> (SELECT MAX(id) FROM group_messages WHERE kind='system')""")
                cur.execute("INSERT INTO period_summaries(year, month, half, total) VALUES(%s,%s,%s,%s)",
                            (y, m, half, period_total))
                db.commit()
                flash(f"تم نشر ملخص {half_lbl} في الجروب تلقائيًا", "success")
        cur.close()
    except Exception as _e:
        print("period summary error:", _e)
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({
            "ok": True,
            "total": total,
            "tasmeen_after": tasmeen_after,
            "bayad_after": bayad_after,
            "extra_tasmeen": extra_tasmeen,
            "extra_bayad": extra_bayad,
            "no_deduct_total": no_deduct_total,
        })
    flash("تم إغلاق اليوم — العمال هيشوفوا الإجمالي الآن", "success")
    return redirect(url_for("admin_close_page", day=day))



# ---- إضافي/خصم لكل عامل في يوم معيّن (للمسؤول فقط) ----
@app.route("/admin/worker-adjust", methods=["POST"])
@admin_required
def admin_worker_adjust():
    u = current_user()
    try:
        user_id = int(request.form.get("user_id") or 0)
    except (TypeError, ValueError):
        user_id = 0
    day = _parse_day(request.form.get("day")).isoformat()
    try:
        amount = int(request.form.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0
    reason = (request.form.get("reason") or "").strip() or None
    if not user_id:
        return jsonify({"ok": False, "err": "user_id"}), 400
    db = get_db(); cur = db.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS worker_adjustments (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, day DATE NOT NULL, amount INTEGER NOT NULL, reason TEXT, created_by INTEGER REFERENCES users(id) ON DELETE SET NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(user_id, day))")
    if amount == 0:
        cur.execute("DELETE FROM worker_adjustments WHERE user_id=%s AND day=%s", (user_id, day))
    else:
        cur.execute(
            """INSERT INTO worker_adjustments(user_id, day, amount, reason, created_by)
               VALUES(%s,%s,%s,%s,%s)
               ON CONFLICT (user_id, day) DO UPDATE SET
                 amount=EXCLUDED.amount, reason=EXCLUDED.reason,
                 created_by=EXCLUDED.created_by, created_at=NOW()""",
            (user_id, day, amount, reason, u["id"]),
        )
    db.commit(); cur.close()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"ok": True, "amount": amount})
    flash("تم حفظ التعديل ✓", "success")
    return redirect(url_for("admin_close_page", day=day))


# ---- تصفية الحساب: تسجيل مبلغ تم دفعه للعامل (للمسؤول فقط) ----
@app.route("/admin/worker-settle", methods=["POST"])
@admin_required
def admin_worker_settle():
    u = current_user()
    try:
        user_id = int(request.form.get("user_id") or 0)
    except (TypeError, ValueError):
        user_id = 0
    day = _parse_day(request.form.get("day") or date.today().isoformat()).isoformat()
    try:
        amount = int(request.form.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0
    note = (request.form.get("note") or "").strip() or None
    if not user_id or amount <= 0:
        flash("ادخل مبلغ صحيح", "error")
        return redirect(url_for("worker_stats", worker_id=user_id or u["id"]))
    db = get_db(); cur = db.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS worker_settlements (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        day DATE NOT NULL,
        amount INTEGER NOT NULL,
        note TEXT,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""")
    cur.execute("""INSERT INTO worker_settlements(user_id, day, amount, note, created_by)
                   VALUES(%s,%s,%s,%s,%s)""",
                (user_id, day, amount, note, u["id"]))
    db.commit(); cur.close()
    flash("تم تسجيل التصفية ✓", "success")
    return redirect(url_for("worker_stats", worker_id=user_id))


@app.route("/admin/worker-settle/<int:sid>/delete", methods=["POST"])
@admin_required
def admin_worker_settle_delete(sid):
    try:
        user_id = int(request.form.get("user_id") or 0)
    except (TypeError, ValueError):
        user_id = 0
    db = get_db(); cur = db.cursor()
    cur.execute("DELETE FROM worker_settlements WHERE id=%s", (sid,))
    db.commit(); cur.close()
    flash("تم حذف التصفية", "info")
    return redirect(url_for("worker_stats", worker_id=user_id))




# ---- تصفية يوم بعدد الكتاكيت (تبديل/toggle) ----
@app.route("/admin/worker-day-settle", methods=["POST"])
@admin_required
def admin_worker_day_settle():
    u = current_user()
    try:
        user_id = int(request.form.get("user_id") or 0)
    except (TypeError, ValueError):
        user_id = 0
    day = _parse_day(request.form.get("day") or date.today().isoformat()).isoformat()
    nxt = (request.form.get("next") or "").strip()
    if not user_id:
        return ("bad request", 400)
    db = get_db(); cur = db.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS worker_day_settle (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        day DATE NOT NULL,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(user_id, day)
    )""")
    cur.execute("SELECT 1 FROM worker_day_settle WHERE user_id=%s AND day=%s", (user_id, day))
    exists = cur.fetchone() is not None
    if exists:
        cur.execute("DELETE FROM worker_day_settle WHERE user_id=%s AND day=%s", (user_id, day))
        state = "unsettled"
    else:
        cur.execute("""INSERT INTO worker_day_settle(user_id, day, created_by)
                       VALUES(%s,%s,%s) ON CONFLICT DO NOTHING""",
                    (user_id, day, u["id"]))
        state = "settled"
    db.commit(); cur.close()
    if request.headers.get("X-Requested-With") == "fetch" or request.args.get("ajax") == "1":
        return {"ok": True, "state": state}
    if nxt == "close-page":
        return redirect(url_for("admin_close_page", day=day))
    return redirect(url_for("worker_stats", worker_id=user_id))


@app.route("/admin/reopen-day", methods=["POST"])
@admin_required
def admin_reopen_day():
    day = _parse_day(request.form.get("day")).isoformat()
    nxt = (request.form.get("next") or "").strip()
    db = get_db()
    cur = db.cursor()
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS reopened BOOLEAN NOT NULL DEFAULT FALSE")
    # نحتفظ بالأرقام (total_count / no_deduct_total) عشان متضيعش لما المسؤول يفتح اليوم تاني
    cur.execute("UPDATE day_closures SET reopened=TRUE WHERE day=%s", (day,))
    # امسح ملخّص الإغلاق اللي اتبعت للجروب — هيتبعت جديد لما اليوم يقفل تاني
    try:
        _purge_closure_message(cur, day)
    except Exception as _e:
        print("purge closure on reopen error:", _e)
    db.commit()
    cur.close()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"ok": True, "day": day, "closed": False})
    flash("تم إعادة فتح اليوم", "info")
    if nxt == "close-page":
        return redirect(url_for("admin_close_page", day=day))
    return redirect(url_for("admin_panel", day=day))


@app.route("/admin/add-for-worker", methods=["POST"])
@admin_required
def admin_add_for_worker():
    day = _parse_day(request.form.get("day"))
    user_id = int(request.form.get("user_id"))
    try:
        count = int(request.form.get("count", "0"))
        if count <= 0:
            raise ValueError
    except ValueError:
        flash("عدد غير صالح", "error")
        return redirect(url_for("admin_panel", day=day.isoformat()))
    note = request.form.get("note", "").strip() or None
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO vaccinations(user_id, day, count, note) VALUES(%s,%s,%s,%s)",
        (user_id, day.isoformat(), count, note),
    )
    cur.execute(
        "INSERT INTO attendance(user_id, day) VALUES(%s,%s) ON CONFLICT DO NOTHING",
        (user_id, day.isoformat()),
    )
    db.commit()
    cur.close()
    flash("تمت الإضافة", "success")
    return redirect(url_for("admin_panel", day=day.isoformat()))


@app.route("/admin/mark-attendance", methods=["POST"])
@admin_required
def admin_mark_attendance():
    day = _parse_day(request.form.get("day")).isoformat()
    user_id = int(request.form.get("user_id"))
    farm = request.form.get("farm") if request.form.get("farm") in ("tasmeen", "bayad") else "tasmeen"
    nxt = (request.form.get("next") or "").strip()
    db = get_db()
    cur = db.cursor()
    cur.execute("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS farm TEXT NOT NULL DEFAULT 'tasmeen'")
    cur.execute("SELECT farm FROM attendance WHERE user_id=%s AND day=%s", (user_id, day))
    exists = cur.fetchone()
    if exists and exists["farm"] == farm:
        cur.execute("DELETE FROM attendance WHERE user_id=%s AND day=%s", (user_id, day))
        state = "absent"
    elif exists:
        cur.execute("UPDATE attendance SET farm=%s WHERE user_id=%s AND day=%s", (farm, user_id, day))
        state = "present"
    else:
        cur.execute("INSERT INTO attendance(user_id, day, farm) VALUES(%s,%s,%s)", (user_id, day, farm))
        state = "present"
    cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE day=%s", (day,))
    present_count = int(cur.fetchone()["c"] or 0)
    cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE day=%s AND farm='tasmeen'", (day,))
    present_tasmeen = int(cur.fetchone()["c"] or 0)
    cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE day=%s AND farm='bayad'", (day,))
    present_bayad = int(cur.fetchone()["c"] or 0)
    db.commit()
    cur.close()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({
            "ok": True,
            "state": state,
            "farm": farm,
            "present_count": present_count,
            "present_tasmeen": present_tasmeen,
            "present_bayad": present_bayad,
        })
    if nxt == "history":
        return redirect(url_for("history") + "#day-" + day)
    if nxt == "close-page":
        return redirect(url_for("admin_close_page", day=day))
    return redirect(url_for("admin_panel", day=day))


@app.route("/admin/mark-extra", methods=["POST"])
@admin_required
def admin_mark_extra():
    """يبدّل علامة 'إضافي' لعامل حاضر في يوم — عشان يتوزع عليه الإضافي."""
    day = _parse_day(request.form.get("day")).isoformat()
    user_id = int(request.form.get("user_id"))
    db = get_db()
    cur = db.cursor()
    cur.execute("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS extra BOOLEAN NOT NULL DEFAULT FALSE")
    cur.execute("SELECT id, COALESCE(extra,FALSE) AS extra FROM attendance WHERE user_id=%s AND day=%s", (user_id, day))
    row = cur.fetchone()
    if not row:
        cur.close()
        if request.headers.get("X-Requested-With") == "fetch":
            return jsonify({"ok": False, "error": "not_attending"}), 400
        flash("لازم تحضر العامل الأول قبل تحديده كإضافي", "error")
        return redirect(url_for("admin_close_page", day=day))
    new_state = not bool(row["extra"])
    cur.execute("UPDATE attendance SET extra=%s WHERE id=%s", (new_state, row["id"]))
    cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE day=%s AND farm='tasmeen' AND COALESCE(extra,FALSE)=TRUE", (day,))
    ex_t = int(cur.fetchone()["c"] or 0)
    cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE day=%s AND farm='bayad' AND COALESCE(extra,FALSE)=TRUE", (day,))
    ex_b = int(cur.fetchone()["c"] or 0)
    db.commit()
    cur.close()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"ok": True, "extra": new_state, "extra_tasmeen_count": ex_t, "extra_bayad_count": ex_b})
    return redirect(url_for("admin_close_page", day=day))




@app.route("/admin/delete-entry/<int:entry_id>", methods=["POST"])
@admin_required
def admin_delete_entry(entry_id):
    day = _parse_day(request.form.get("day")).isoformat()
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM vaccinations WHERE id=%s", (entry_id,))
    db.commit()
    cur.close()
    flash("تم الحذف", "info")
    return redirect(url_for("admin_panel", day=day))


# ---- إعلان تحضير الغد (يُنشر في الجروب ويُثبّت) ----
@app.route("/admin/announce-tomorrow", methods=["POST"])
@admin_required
def admin_announce_tomorrow():
    u = current_user()
    raw_day = request.form.get("day") or (date.today() + timedelta(days=1)).isoformat()
    day = _parse_day(raw_day).isoformat()
    ids = request.form.getlist("user_ids")
    if not ids:
        flash("اختر عامل واحد على الأقل", "error")
        return redirect(url_for("admin_tomorrow_page", day=day))
    db = get_db()
    cur = db.cursor()
    id_ints = [int(x) for x in ids]
    cur.execute("SELECT full_name FROM users WHERE id = ANY(%s) ORDER BY full_name", (id_ints,))
    names = [r["full_name"] for r in cur.fetchall()]
    # نلغي تثبيت أي إعلان حضور سابق
    cur.execute("UPDATE group_messages SET pinned=FALSE WHERE pinned=TRUE AND kind='attendance'")
    body = "[ICON:clipboard] حضور يوم " + day + "\n- " + "\n- ".join(names)
    cur.execute("""INSERT INTO group_messages(sender_id, kind, body, pinned)
                   VALUES (%s, 'attendance', %s, TRUE)""", (u["id"], body))
    db.commit()
    cur.close()
    # 🔔 إشعار لكل عامل مدرج في القائمة
    _notify_users(id_ints,
                  "حضورك مطلوب يوم " + day,
                  f"اضغط لعرض التفاصيل في الجروب",
                  url=url_for("group_room"),
                  type_="attendance")
    flash(f"تم نشر قائمة حضور يوم {day} + إرسال إشعار لكل عامل ✓", "success")
    return redirect(url_for("admin_tomorrow_page", day=day))


@app.route("/admin/users", methods=["GET", "POST"])
@super_admin_required
def admin_users():
    db = get_db()
    cur = db.cursor()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            full_name = request.form.get("full_name", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "worker")
            if not (full_name and password):
                flash("الاسم وكلمة السر مطلوبين", "error")
            else:
                try:
                    new_uid = _next_free_userid(cur)
                    cur.execute(
                        "INSERT INTO users(username, full_name, password_hash, role) VALUES(%s,%s,%s,%s)",
                        (new_uid, full_name, generate_password_hash(password), role),
                    )
                    db.commit()
                    flash(f"تم إضافة المستخدم برقم {new_uid}", "success")
                except psycopg2.IntegrityError:
                    db.rollback()
                    flash("حصل تعارض في الرقم — حاول تاني", "error")
        elif action == "delete":
            uid = int(request.form.get("user_id"))
            u = current_user()
            if uid != u["id"]:
                cur.execute("DELETE FROM users WHERE id=%s", (uid,))
                db.commit()
                flash("تم حذف المستخدم", "info")
        elif action == "reset_pw":
            uid = int(request.form.get("user_id"))
            new_pw = request.form.get("password", "")
            if new_pw:
                cur.execute("UPDATE users SET password_hash=%s WHERE id=%s",
                            (generate_password_hash(new_pw), uid))
                db.commit()
                flash("تم تغيير كلمة السر", "success")
        cur.close()
        return redirect(url_for("admin_users"))

    cur.execute("SELECT * FROM users ORDER BY (role='admin') DESC, full_name")
    users = cur.fetchall()
    cur.close()
    return render_template("admin_users.html", users=users)


# ---- صفحة مستقلة لإغلاق اليوم ----
@app.route("/admin/close-page")
@admin_required
def admin_close_page():
    day = _parse_day(request.args.get("day"))
    day_s = day.isoformat()
    prev_day = (day - timedelta(days=1)).isoformat()
    next_day = (day + timedelta(days=1)).isoformat()
    from datetime import date as _date
    is_today = (day_s == _date.today().isoformat())
    db = get_db()
    cur = db.cursor()
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS reopened BOOLEAN NOT NULL DEFAULT FALSE")
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS tasmeen_after INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS bayad_after INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS extra_tasmeen INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS extra_bayad INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS farm TEXT NOT NULL DEFAULT 'tasmeen'")
    cur.execute("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS extra BOOLEAN NOT NULL DEFAULT FALSE")
    cur.execute("SELECT COALESCE(SUM(count),0) AS s FROM vaccinations WHERE day=%s", (day_s,))
    day_total = cur.fetchone()["s"]
    cur.execute("SELECT total_count, tasmeen_after, bayad_after, COALESCE(extra_tasmeen,0) AS extra_tasmeen, COALESCE(extra_bayad,0) AS extra_bayad, no_deduct_total, reopened FROM day_closures WHERE day=%s", (day_s,))
    _row = cur.fetchone()
    has_saved = _row is not None
    closed = has_saved and not (_row.get("reopened") if isinstance(_row, dict) else _row["reopened"])
    no_deduct_total = 0
    tasmeen_after = 0
    bayad_after = 0
    extra_tasmeen = 0
    extra_bayad = 0
    # نعرض القيم المحفوظة حتى لو اليوم مفتوح تاني — عشان المسؤول ميعيدش كتابتها
    if has_saved:
        day_total = _row["total_count"]
        tasmeen_after = int(_row["tasmeen_after"] or 0)
        bayad_after = int(_row["bayad_after"] or 0)
        extra_tasmeen = int(_row["extra_tasmeen"] or 0)
        extra_bayad = int(_row["extra_bayad"] or 0)
        if tasmeen_after == 0 and bayad_after == 0:
            tasmeen_after = int(day_total or 0)
        no_deduct_total = _row["no_deduct_total"] or 0
    cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE day=%s", (day_s,))
    present_count = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE day=%s AND farm='tasmeen'", (day_s,))
    present_tasmeen = int(cur.fetchone()["c"] or 0)
    cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE day=%s AND farm='bayad'", (day_s,))
    present_bayad = int(cur.fetchone()["c"] or 0)

    _admin_u = current_user()
    cur.execute("SELECT 1 FROM attendance WHERE user_id=%s AND day=%s", (_admin_u["id"], day_s))
    admin_checked_in = cur.fetchone() is not None
    # كل المستخدمين (عمال + المسؤول) — يظهروا كقائمة تحضير مع حالة الحضور + التعديل
    cur.execute("""CREATE TABLE IF NOT EXISTS worker_day_settle (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        day DATE NOT NULL,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(user_id, day)
    )""")
    cur.execute("""
        SELECT u.id, u.full_name, u.role, u.avatar,
               (SELECT a.farm FROM attendance a WHERE a.user_id=u.id AND a.day=%s LIMIT 1) AS att_farm,
               COALESCE((SELECT a.extra FROM attendance a WHERE a.user_id=u.id AND a.day=%s LIMIT 1), FALSE) AS att_extra,
               COALESCE((SELECT amount FROM worker_adjustments wa
                          WHERE wa.user_id=u.id AND wa.day=%s), 0) AS adjust,
               EXISTS(SELECT 1 FROM worker_day_settle ws WHERE ws.user_id=u.id AND ws.day=%s) AS day_settled
        FROM users u
        ORDER BY (u.role='admin') DESC, u.full_name
    """, (day_s, day_s, day_s, day_s))
    all_people = cur.fetchall()
    cur.close()
    return render_template("admin_close_day.html",
                           day=day_s, day_total=day_total,
                            tasmeen_after=tasmeen_after,
                            bayad_after=bayad_after,
                            extra_tasmeen=extra_tasmeen,
                            extra_bayad=extra_bayad,
                           no_deduct_total=no_deduct_total,
                           present_count=present_count, day_closed=closed,
                            present_tasmeen=present_tasmeen,
                            present_bayad=present_bayad,
                           all_people=all_people,
                           prev_day=prev_day, next_day=next_day, is_today=is_today)


# ---- سجل الأعداد بدون خصم (مرجع للمسؤول) ----
@app.route("/admin/gross-log")
@admin_required
def admin_gross_log():
    import calendar as _cal
    db = get_db()
    cur = db.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS no_deduct_clears (
        year INTEGER NOT NULL, month INTEGER NOT NULL,
        half INTEGER NOT NULL CHECK(half IN (1,2)),
        cleared_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        cleared_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        total_snapshot INTEGER NOT NULL DEFAULT 0,
        days_snapshot INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (year, month, half)
    )""")

    cur.execute("""SELECT day, total_count, no_deduct_total, closed_at
                   FROM day_closures
                   WHERE COALESCE(no_deduct_total,0) > 0
                   ORDER BY day DESC LIMIT 365""")
    rows = cur.fetchall()
    cur.execute("SELECT COALESCE(SUM(no_deduct_total),0) AS s FROM day_closures")
    grand = int(cur.fetchone()["s"] or 0)

    # المدة الحالية (نصف شهر)
    today = date.today()
    cur_half = 1 if today.day <= 15 else 2
    last_day = _cal.monthrange(today.year, today.month)[1]
    if cur_half == 1:
        cur_s = date(today.year, today.month, 1).isoformat()
        cur_e = date(today.year, today.month, min(15, last_day)).isoformat()
        cur_label = f"النصف الأول (1-15) — {today.month}/{today.year}"
    else:
        cur_s = date(today.year, today.month, 16).isoformat()
        cur_e = date(today.year, today.month, last_day).isoformat()
        cur_label = f"النصف الثاني (16-{last_day}) — {today.month}/{today.year}"
    cur.execute("""SELECT COALESCE(SUM(no_deduct_total),0) AS s, COUNT(*) AS c
                   FROM day_closures WHERE day BETWEEN %s AND %s
                     AND COALESCE(no_deduct_total,0)>0""",
                (cur_s, cur_e))
    r = cur.fetchone()
    current_period = {
        "year": today.year, "month": today.month, "half": cur_half,
        "label": cur_label, "start": cur_s, "end": cur_e,
        "total": int(r["s"] or 0), "days": int(r["c"] or 0),
    }

    # المدد السابقة اللي فيها بيانات ومش متصفّرة
    cur.execute("""SELECT EXTRACT(YEAR FROM day)::int AS y,
                          EXTRACT(MONTH FROM day)::int AS m,
                          CASE WHEN EXTRACT(DAY FROM day)<=15 THEN 1 ELSE 2 END AS half,
                          COALESCE(SUM(no_deduct_total),0) AS s,
                          COUNT(*) AS c
                   FROM day_closures
                   WHERE COALESCE(no_deduct_total,0)>0
                   GROUP BY 1,2,3
                   ORDER BY 1 DESC, 2 DESC, 3 DESC""")
    all_periods = cur.fetchall()
    past_periods = []
    for p in all_periods:
        k = (p["y"], p["m"], p["half"])
        if k == (today.year, today.month, cur_half):
            continue
        last_d = _cal.monthrange(p["y"], p["m"])[1]
        if p["half"] == 1:
            lab = f"النصف الأول (1-15) — {p['m']}/{p['y']}"
        else:
            lab = f"النصف الثاني (16-{last_d}) — {p['m']}/{p['y']}"
        past_periods.append({
            "year": p["y"], "month": p["m"], "half": p["half"],
            "label": lab, "total": int(p["s"] or 0), "days": int(p["c"] or 0),
        })

    cur.close()
    return render_template("admin_gross_log.html",
                           rows=rows, grand=grand,
                           current_period=current_period,
                           past_periods=past_periods)


@app.route("/admin/gross-log/clear-period", methods=["POST"])
@admin_required
def admin_gross_clear_period():
    import calendar as _cal
    try:
        y = int(request.form.get("year") or 0)
        m = int(request.form.get("month") or 0)
        half = int(request.form.get("half") or 0)
    except (TypeError, ValueError):
        flash("مدخلات غير صالحة", "error")
        return redirect(url_for("admin_gross_log"))
    if not (y and m and half in (1, 2)):
        flash("مدخلات غير صالحة", "error")
        return redirect(url_for("admin_gross_log"))
    last_day = _cal.monthrange(y, m)[1]
    if half == 1:
        s = date(y, m, 1).isoformat();  e = date(y, m, min(15, last_day)).isoformat()
    else:
        s = date(y, m, 16).isoformat(); e = date(y, m, last_day).isoformat()
    me_u = current_user()
    db = get_db(); cur = db.cursor()
    try:
        # تصفير نهائي: مسح قيمة الأعداد بدون خصم لأيام المدة — من غير أي أرشيف/snapshot
        cur.execute("UPDATE day_closures SET no_deduct_total=0 WHERE day BETWEEN %s AND %s", (s, e))
        db.commit()
        flash("تم تصفير الأعداد بدون خصم للمدة ✓", "success")
    except Exception as ex:
        db.rollback()
        flash("خطأ: " + str(ex), "error")
    finally:
        cur.close()
    return redirect(url_for("admin_gross_log"))


@app.route("/admin/gross-log/undo-clear", methods=["POST"])
@admin_required
def admin_gross_undo_clear():
    try:
        y = int(request.form.get("year") or 0)
        m = int(request.form.get("month") or 0)
        half = int(request.form.get("half") or 0)
    except (TypeError, ValueError):
        return redirect(url_for("admin_gross_log"))
    db = get_db(); cur = db.cursor()
    cur.execute("DELETE FROM no_deduct_clears WHERE year=%s AND month=%s AND half=%s", (y, m, half))
    db.commit(); cur.close()
    flash("تم حذف علامة التصفير — المدة رجعت للعرض", "success")
    return redirect(url_for("admin_gross_log"))


# ---- بروفايل العامل ----
@app.route("/me/profile", methods=["GET", "POST"])
@login_required
def worker_profile():
    u = current_user()
    db = get_db()
    cur = db.cursor()
    if request.method == "POST":
        action = request.form.get("action", "password")
        # العامل مسموحله يغيّر كلمة السر بتاعته بس — مش الاسم ولا اليوزرنيم
        # (تغيير الصورة له مسار منفصل عبر /me/avatar)
        if action == "password":
            old_pw = request.form.get("old_password", "")
            new_pw = request.form.get("new_password", "")
            if not new_pw or len(new_pw) < 4:
                flash("كلمة السر الجديدة قصيرة", "error")
            elif not check_password_hash(u["password_hash"], old_pw):
                flash("كلمة السر الحالية غلط", "error")
            else:
                cur.execute("UPDATE users SET password_hash=%s WHERE id=%s",
                            (generate_password_hash(new_pw), u["id"]))
                db.commit()
                flash("تم تحديث كلمة السر", "success")
        else:
            flash("مش مسموحلك تغيّر البيانات دي — العامل يقدر يغيّر الصورة وكلمة السر بس", "error")
        cur.close()
        return redirect(url_for("worker_profile"))
    cur.close()
    return render_template("admin_profile.html", me=u)


# ---- (تم حذف صفحة تحضير عمال بكره — لم تعد مستخدمة) ----
@app.route("/admin/tomorrow-page")
@admin_required
def admin_tomorrow_page():
    return redirect(url_for("admin_panel"))



# ---- بروفايل المسؤول: تغيير الاسم / كلمة السر ----
@app.route("/admin/profile", methods=["GET", "POST"])
@admin_required
def admin_profile():
    u = current_user()
    db = get_db()
    cur = db.cursor()
    if request.method == "POST":
        action = request.form.get("action", "name")
        if action == "name":
            new_name = (request.form.get("full_name") or "").strip()
            new_username = (request.form.get("username") or "").strip()
            if not new_name or not new_username:
                flash("الاسم واسم المستخدم مطلوبين", "error")
            else:
                try:
                    cur.execute("UPDATE users SET full_name=%s, username=%s WHERE id=%s",
                                (new_name[:80], new_username[:40], u["id"]))
                    db.commit()
                    flash("تم تحديث بياناتك ✓", "success")
                except psycopg2.IntegrityError:
                    db.rollback()
                    flash("اسم المستخدم ده موجود بالفعل", "error")
        elif action == "password":
            old_pw = request.form.get("old_password", "")
            new_pw = request.form.get("new_password", "")
            if not new_pw or len(new_pw) < 4:
                flash("كلمة السر الجديدة قصيرة", "error")
            elif not check_password_hash(u["password_hash"], old_pw):
                flash("كلمة السر الحالية غلط", "error")
            else:
                cur.execute("UPDATE users SET password_hash=%s WHERE id=%s",
                            (generate_password_hash(new_pw), u["id"]))
                db.commit()
                flash("تم تحديث كلمة السر ✓", "success")
        cur.close()
        return redirect(url_for("admin_profile"))
    cur.close()
    return render_template("admin_profile.html", me=u)


# ============================================================
# ============ تقرير فترة مخصّصة (المسؤول فقط) ================
# ============================================================
@app.route("/admin/range-report", methods=["GET", "POST"])
@admin_required
def admin_range_report():
    u = current_user()
    db = get_db()
    cur = db.cursor()
    # ensure table exists (safety)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS range_reports (
            id SERIAL PRIMARY KEY,
            admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            start_day DATE NOT NULL,
            end_day DATE NOT NULL,
            total INTEGER NOT NULL DEFAULT 0,
            days_count INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    # عمود إضافي لحفظ إجمالي "الأعداد بدون خصم" داخل التقرير كمرجع
    cur.execute("ALTER TABLE range_reports ADD COLUMN IF NOT EXISTS distributed_total INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE range_reports ADD COLUMN IF NOT EXISTS target_kind TEXT")
    cur.execute("ALTER TABLE range_reports ADD COLUMN IF NOT EXISTS target_id INTEGER")
    cur.execute("ALTER TABLE range_reports ADD COLUMN IF NOT EXISTS target_label TEXT")
    cur.execute("ALTER TABLE range_reports ADD COLUMN IF NOT EXISTS chick_count INTEGER NOT NULL DEFAULT 0")

    # قائمة موحّدة للعمال + المسؤولين للـ dropdown (بدون تمييز في الواجهة)
    cur.execute("SELECT id, full_name, role, avatar FROM users WHERE role IN ('worker','admin') ORDER BY full_name")
    all_people = cur.fetchall()
    # نخلطهم كلهم في قائمة واحدة "people_list" باسم عام "نصيب"
    people_list = list(all_people)
    workers_list = [p for p in all_people if p["role"] == "worker"]
    admins_list  = [p for p in all_people if p["role"] == "admin"]

    result = None
    if request.method == "POST":
        start_s = (request.form.get("start_day") or "").strip()
        end_s   = (request.form.get("end_day") or "").strip()
        target  = (request.form.get("target") or "no_deduct").strip()
        note    = None
        try:
            start_d = datetime.strptime(start_s, "%Y-%m-%d").date()
            end_d   = datetime.strptime(end_s, "%Y-%m-%d").date()
        except ValueError:
            flash("اختار تاريخين صحيحين", "error")
            cur.close()
            return redirect(url_for("admin_range_report"))
        if end_d < start_d:
            start_d, end_d = end_d, start_d
        s_iso = start_d.isoformat(); e_iso = end_d.isoformat()

        # أساسيات مشتركة (مرجع)
        cur.execute(
            "SELECT COALESCE(SUM(no_deduct_total),0) AS s_nd, "
            "COALESCE(SUM(total_count),0) AS s_dist, COUNT(*) AS c "
            "FROM day_closures WHERE day BETWEEN %s AND %s",
            (s_iso, e_iso),
        )
        row = cur.fetchone()
        s_nd   = int(row["s_nd"] or 0)
        s_dist = int(row["s_dist"] or 0)
        days_count = int(row["c"] or 0)

        target_kind  = "no_deduct"
        target_id    = None
        target_label = "إجمالي بدون خصم"
        total = s_nd
        chick_count = 0

        if target == "no_deduct":
            target_kind = "no_deduct"; target_label = "إجمالي بدون خصم"
            total = s_nd
        elif target == "after_deduct":
            target_kind = "after_deduct"; target_label = "إجمالي بعد الخصم (الموزَّع)"
            total = s_dist
        elif target.startswith(("worker:", "admin:", "person:")):
            try:
                pid = int(target.split(":", 1)[1])
            except ValueError:
                pid = 0
            if pid:
                # نتعامل مع العامل والمسؤول بنفس الطريقة تمامًا وبنفس التسمية
                # عشان محدش يقدر يميّز من التقرير مين مسؤول ومين عامل
                cur.execute("SELECT full_name, role FROM users WHERE id=%s", (pid,))
                pr = cur.fetchone()
                if pr:
                    cur.execute("""
                        SELECT COALESCE(SUM(c.total_count::float /
                                 NULLIF((SELECT COUNT(*) FROM attendance a WHERE a.day=c.day),0)
                               ),0) AS shr,
                               (SELECT COUNT(*) FROM attendance a2
                                WHERE a2.user_id=%s AND a2.day BETWEEN %s AND %s) AS att_days
                        FROM day_closures c
                        WHERE c.day BETWEEN %s AND %s
                          AND EXISTS(SELECT 1 FROM attendance a3
                                     WHERE a3.day=c.day AND a3.user_id=%s)
                    """, (pid, s_iso, e_iso, s_iso, e_iso, pid))
                    r2 = cur.fetchone()
                    chick_count = int(r2["shr"] or 0)
                    total = chick_count * 55
                    days_count = int(r2["att_days"] or 0)
                    # نخزّن kind='worker' دايمًا (بدون تمييز) ونستخدم نفس التسمية العامة
                    target_kind = "worker"; target_id = pid
                    target_label = f"نصيب: {pr['full_name']}"

        cur.execute(
            "INSERT INTO range_reports(admin_id, start_day, end_day, total, days_count, note, distributed_total, target_kind, target_id, target_label, chick_count) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (u["id"], s_iso, e_iso, total, days_count, note, s_dist, target_kind, target_id, target_label, chick_count),
        )
        db.commit()
        result = {
            "start": s_iso, "end": e_iso,
            "start_display": f"{start_d.day}/{start_d.month}/{start_d.year}",
            "end_display": f"{end_d.day}/{end_d.month}/{end_d.year}",
            "total": total, "distributed_total": s_dist,
            "no_deduct_total": s_nd,
            "days": days_count, "note": note,
            "target_kind": target_kind, "target_label": target_label,
            "chick_count": chick_count,
            "is_money": target_kind in ("worker", "admin"),
        }
        flash(f"تم حساب التقرير ({target_label}) وحفظه ✓", "success")

    cur.execute(
        "SELECT id, start_day, end_day, total, days_count, note, created_at, "
        "distributed_total, target_kind, target_label, chick_count "
        "FROM range_reports ORDER BY created_at DESC LIMIT 100"
    )
    reports = cur.fetchall()
    cur.close()
    return render_template("admin_range_report.html",
                           result=result, reports=reports,
                           people_list=people_list,
                           workers_list=workers_list, admins_list=admins_list)


@app.route("/admin/range-report/<int:rid>/delete", methods=["POST"])
@admin_required
def admin_range_report_delete(rid):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM range_reports WHERE id=%s", (rid,))
    db.commit()
    cur.close()
    flash("تم حذف التقرير", "success")
    return redirect(url_for("admin_range_report"))



# ============================================================
# ====================== الشات (Chat) =========================
# ============================================================

ONLINE_WINDOW_SECONDS = 60


def _is_online(last_seen):
    if not last_seen:
        return False
    now = datetime.now(timezone.utc)
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return (now - last_seen).total_seconds() <= ONLINE_WINDOW_SECONDS


def _msg_preview(m):
    if not m:
        return ""
    if m["kind"] == "image":
        return "صورة"
    if m["kind"] == "audio":
        return "رسالة صوتية"
    if m["kind"] == "attendance":
        return "قائمة حضور"
    if m["kind"] == "system":
        body = (m.get("body") or "")
        return body.replace("[ICON:chart]","").replace("[ICON:check]","").replace("[ICON:clipboard]","").strip()[:60]
    body = m.get("body") or ""
    return body if len(body) <= 40 else body[:40] + "…"


def _get_group_settings():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM group_settings WHERE id=1")
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO group_settings(id,name) VALUES(1,'دردشة العمال') ON CONFLICT DO NOTHING")
        db.commit()
        cur.execute("SELECT * FROM group_settings WHERE id=1")
        row = cur.fetchone()
    cur.close()
    return row


@app.route("/chats")
@login_required
def chats_list():
    u = current_user()
    db = get_db()
    cur = db.cursor()

    # المحادثات الفردية
    cur.execute("""
        SELECT u.id, u.full_name, u.username, u.avatar, u.last_seen,
          (SELECT row_to_json(t) FROM (
              SELECT id, sender_id, receiver_id, kind, body, created_at
              FROM chat_messages
              WHERE (sender_id=%s AND receiver_id=u.id)
                 OR (sender_id=u.id AND receiver_id=%s)
              ORDER BY created_at DESC LIMIT 1
          ) t) AS last_msg,
          (SELECT COUNT(*) FROM chat_messages
             WHERE sender_id=u.id AND receiver_id=%s AND read_at IS NULL) AS unread
        FROM users u
        WHERE u.id <> %s
        ORDER BY u.full_name
    """, (u["id"], u["id"], u["id"], u["id"]))
    rows = cur.fetchall()

    contacts = []
    for r in rows:
        lm = r["last_msg"]
        last_text = _msg_preview(lm) if lm else "اضغط لبدء المحادثة"
        last_time = lm["created_at"] if lm else None
        contacts.append({
            "id": r["id"],
            "full_name": r["full_name"],
            "username": r["username"],
            "avatar": r["avatar"],
            "online": _is_online(r["last_seen"]),
            "last_seen": _iso_utc(r["last_seen"]),
            "last_text": last_text,
            "last_time": _iso_utc(last_time) if last_time else None,
            "unread": r["unread"] or 0,
        })
    contacts.sort(key=lambda c: c["last_time"] or "", reverse=True)

    # بيانات المجموعة
    gs = _get_group_settings()
    cur.execute("""SELECT id, sender_id, kind, body, created_at FROM group_messages
                   WHERE deleted=FALSE ORDER BY created_at DESC LIMIT 1""")
    g_last = cur.fetchone()
    cur.execute("SELECT last_read_id FROM group_reads WHERE user_id=%s", (u["id"],))
    gr = cur.fetchone()
    last_read_id = gr["last_read_id"] if gr else 0
    cur.execute("SELECT COUNT(*) AS c FROM group_messages WHERE id > %s AND deleted=FALSE AND sender_id <> %s",
                (last_read_id, u["id"]))
    g_unread = cur.fetchone()["c"]
    cur.close()

    g_last_preview = g_last
    if g_last:
        g_last_preview = dict(g_last)
        g_last_preview["body"] = _visible_group_body_for_user(g_last_preview.get("body"), g_last_preview.get("kind"), u)
    group = {
        "name": gs["name"],
        "avatar": gs["avatar"],
        "last_text": _msg_preview(g_last_preview) if g_last_preview else "ابدأ الكلام مع الفريق",
        "last_time": _iso_utc(g_last["created_at"]) if g_last else None,
        "unread": g_unread,
    }
    return render_template("chats.html", contacts=contacts, group=group)


@app.route("/chat/<int:other_id>")
@login_required
def chat_room(other_id):
    u = current_user()
    if other_id == u["id"]:
        return redirect(url_for("chats_list"))
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, full_name, username, avatar, last_seen FROM users WHERE id=%s", (other_id,))
    other = cur.fetchone()
    if not other:
        cur.close()
        flash("المستخدم غير موجود", "error")
        return redirect(url_for("chats_list"))
    cur.execute("""UPDATE chat_messages SET read_at = NOW()
                   WHERE sender_id=%s AND receiver_id=%s AND read_at IS NULL""",
                (other_id, u["id"]))
    db.commit()
    cur.close()
    other_dict = {
        "id": other["id"],
        "full_name": other["full_name"],
        "username": other["username"],
        "avatar": other["avatar"],
        "online": _is_online(other["last_seen"]),
    }
    return render_template("chat.html", other=other_dict)


@app.route("/chat/<int:other_id>/messages")
@login_required
def chat_messages_api(other_id):
    u = current_user()
    after = request.args.get("after", "0")
    try:
        after = int(after)
    except ValueError:
        after = 0
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT id, sender_id, receiver_id, kind, body, created_at, read_at, reply_to_id, edited_at
        FROM chat_messages
        WHERE ((sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s))
          AND id > %s
        ORDER BY id ASC LIMIT 200
    """, (u["id"], other_id, other_id, u["id"], after))
    rows = cur.fetchall()
    # جِب مقتطفات الرد
    reply_ids = [r["reply_to_id"] for r in rows if r["reply_to_id"]]
    replies_map = {}
    if reply_ids:
        cur.execute("""SELECT id, kind, body, sender_id FROM chat_messages WHERE id = ANY(%s)""",
                    (reply_ids,))
        for rr in cur.fetchall():
            snip = rr["body"] if rr["kind"] == "text" else ("[صورة]" if rr["kind"] == "image" else "[رسالة صوتية]")
            replies_map[rr["id"]] = {
                "id": rr["id"],
                "snippet": (snip or "")[:140],
                "mine": rr["sender_id"] == u["id"],
            }
    cur.execute("""UPDATE chat_messages SET read_at = NOW()
                   WHERE sender_id=%s AND receiver_id=%s AND read_at IS NULL""",
                (other_id, u["id"]))
    db.commit()
    # كل الرسايل بتاعتي اللي الطرف التاني قراها (عشان نظبط الـ ticks)
    cur.execute("""SELECT id FROM chat_messages
                   WHERE sender_id=%s AND receiver_id=%s AND read_at IS NOT NULL
                   ORDER BY id DESC LIMIT 200""",
                (u["id"], other_id))
    read_ids = [row["id"] for row in cur.fetchall()]
    cur.execute("SELECT last_seen FROM users WHERE id=%s", (other_id,))
    other_row = cur.fetchone()
    # تفاعلات: للرسائل الجديدة + آخر 100 رسالة (عشان تحديث التفاعلات القديمة)
    new_ids = [r["id"] for r in rows]
    cur.execute("""SELECT id FROM chat_messages
                   WHERE ((sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s))
                   ORDER BY id DESC LIMIT 100""",
                (u["id"], other_id, other_id, u["id"]))
    recent_ids = [r["id"] for r in cur.fetchall()]
    all_ids = list(set(new_ids) | set(recent_ids))
    reactions_map = _reactions_for(cur, "chat_reactions", all_ids, u["id"])
    cur.close()
    msgs = []
    for r in rows:
        visible_body = _visible_group_body_for_user(r["body"], r["kind"], u)
        msgs.append({
            "id": r["id"],
            "sender_id": r["sender_id"],
            "kind": r["kind"],
            "body": visible_body,
            "created_at": _iso_utc(r["created_at"]),
            "mine": r["sender_id"] == u["id"],
            "read": r["read_at"] is not None,
            "reply_to": replies_map.get(r["reply_to_id"]) if r["reply_to_id"] else None,
            "reactions": reactions_map.get(r["id"], []),
            "edited": r["edited_at"] is not None,
        })
    reactions_updates = {str(mid): reactions_map.get(mid, []) for mid in recent_ids}
    return jsonify({
        "messages": msgs,
        "read_ids": read_ids,
        "other_online": _is_online(other_row["last_seen"]) if other_row else False,
        "other_last_seen": _iso_utc(other_row["last_seen"]) if other_row else None,
        "reactions_updates": reactions_updates,
    })


@app.route("/chat/<int:other_id>/send", methods=["POST"])
@login_required
def chat_send(other_id):
    u = current_user()
    if other_id == u["id"]:
        return jsonify({"ok": False, "error": "self"}), 400
    kind = request.form.get("kind", "text")
    body = None
    if kind == "text":
        text = (request.form.get("body") or "").strip()
        if not text:
            return jsonify({"ok": False, "error": "empty"}), 400
        if len(text) > 4000:
            text = text[:4000]
        body = text
    elif kind in ("image", "audio"):
        f = request.files.get("file")
        if not f:
            return jsonify({"ok": False, "error": "no_file"}), 400
        data = f.read()
        if len(data) > 8 * 1024 * 1024:
            return jsonify({"ok": False, "error": "too_large"}), 413
        mime = f.mimetype or ("image/jpeg" if kind == "image" else "audio/webm")
        body = "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")
    else:
        return jsonify({"ok": False, "error": "bad_kind"}), 400

    reply_to_id = request.form.get("reply_to_id")
    try:
        reply_to_id = int(reply_to_id) if reply_to_id else None
    except (TypeError, ValueError):
        reply_to_id = None
    db = get_db()
    cur = db.cursor()
    cur.execute("""INSERT INTO chat_messages(sender_id, receiver_id, kind, body, reply_to_id)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id, created_at""",
                (u["id"], other_id, kind, body, reply_to_id))
    row = cur.fetchone()
    db.commit()
    cur.close()
    # 🔔 إشعار للمستقبل
    preview = body if kind == "text" else ("[صورة]" if kind == "image" else "[رسالة صوتية]")
    _notify_users([other_id],
                  f"{u['full_name']}",
                  (preview or "")[:120],
                  url=url_for("chat_room", other_id=u["id"]),
                  type_="dm")
    return jsonify({"ok": True, "id": row["id"], "created_at": _iso_utc(row["created_at"])})


# ====================== الجروب الجماعي ======================

@app.route("/group")
@login_required
def group_room():
    u = current_user()
    gs = _get_group_settings()
    # حدّث آخر قراءة
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COALESCE(MAX(id),0) AS m FROM group_messages")
    max_id = cur.fetchone()["m"]
    cur.execute("""INSERT INTO group_reads(user_id, last_read_id) VALUES(%s,%s)
                   ON CONFLICT (user_id) DO UPDATE SET last_read_id=EXCLUDED.last_read_id, updated_at=NOW()""",
                (u["id"], max_id))
    db.commit()
    # عدد الأعضاء
    cur.execute("SELECT COUNT(*) AS c FROM users")
    members = cur.fetchone()["c"]
    cur.close()
    is_admin = (u["role"] == "admin")
    cur2 = db.cursor()
    cur2.execute("SELECT can_delete FROM group_perms WHERE user_id=%s", (u["id"],))
    _mp = cur2.fetchone(); cur2.close()
    my_can_delete = bool(_mp and _mp["can_delete"])
    return render_template("group.html", group={
        "name": gs["name"], "avatar": gs["avatar"], "members": members,
        "is_locked": bool(gs["is_locked"]) if "is_locked" in gs else False
    }, is_admin=is_admin, my_can_delete=my_can_delete)


@app.route("/group/messages")
@login_required
def group_messages_api():
    u = current_user()
    after = request.args.get("after", "0")
    try:
        after = int(after)
    except ValueError:
        after = 0
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT m.id, m.sender_id, m.kind, m.body, m.pinned, m.deleted, m.created_at,
               m.reply_to_id, m.mentions, m.edited_at,
               u.full_name AS sender_name, u.avatar AS sender_avatar, u.role AS sender_role
        FROM group_messages m
        LEFT JOIN users u ON u.id = m.sender_id
        WHERE m.id > %s AND m.deleted = FALSE
        ORDER BY m.id ASC LIMIT 300
    """, (after,))
    rows = cur.fetchall()
    # جِب مقتطفات الرسايل المُردّ عليها
    reply_ids = [r["reply_to_id"] for r in rows if r["reply_to_id"]]
    replies_map = {}
    if reply_ids:
        cur.execute("""SELECT m.id, m.kind, m.body, u.full_name AS sender_name
                       FROM group_messages m LEFT JOIN users u ON u.id=m.sender_id
                       WHERE m.id = ANY(%s)""", (reply_ids,))
        for rr in cur.fetchall():
            snippet = rr["body"] if rr["kind"] == "text" else ("[صورة]" if rr["kind"] == "image" else "[رسالة صوتية]")
            replies_map[rr["id"]] = {
                "id": rr["id"], "sender_name": rr["sender_name"] or "محذوف",
                "snippet": (snippet or "")[:140]
            }
    # المثبّت
    cur.execute("""SELECT id, body, kind FROM group_messages
                   WHERE pinned=TRUE AND deleted=FALSE
                   ORDER BY created_at DESC LIMIT 1""")
    pinned = cur.fetchone()
    # ids اللي اتحذفت من الآخر (عشان الكلاينت يشيلها من الشاشة) — آخر 500
    cur.execute("""SELECT id FROM group_messages WHERE deleted=TRUE
                   ORDER BY id DESC LIMIT 500""")
    deleted_ids = [r["id"] for r in cur.fetchall()]
    # حدّث آخر قراءة لأكبر id
    if rows:
        cur.execute("""INSERT INTO group_reads(user_id, last_read_id) VALUES(%s,%s)
                       ON CONFLICT (user_id) DO UPDATE SET last_read_id=GREATEST(group_reads.last_read_id, EXCLUDED.last_read_id), updated_at=NOW()""",
                    (u["id"], rows[-1]["id"]))
        db.commit()
    # تفاعلات: للرسائل الجديدة + آخر 100 رسالة
    new_ids = [r["id"] for r in rows]
    cur.execute("""SELECT id FROM group_messages WHERE deleted=FALSE
                   ORDER BY id DESC LIMIT 100""")
    recent_ids = [r["id"] for r in cur.fetchall()]
    all_ids = list(set(new_ids) | set(recent_ids))
    reactions_map = _reactions_for(cur, "group_reactions", all_ids, u["id"])
    cur.close()
    msgs = []
    for r in rows:
        try:
            mentions = _json.loads(r["mentions"]) if r["mentions"] else []
        except Exception:
            mentions = []
        msgs.append({
            "id": r["id"],
            "sender_id": r["sender_id"],
            "sender_name": r["sender_name"] or "محذوف",
            "sender_avatar": r["sender_avatar"],
            "sender_role": (r["sender_role"] if _is_super_admin(u) else "") or "",
            "kind": r["kind"],
            "body": r["body"],
            "pinned": r["pinned"],
            "deleted": r["deleted"],
            "created_at": _iso_utc(r["created_at"]),
            "mine": r["sender_id"] == u["id"],
            "reply_to": replies_map.get(r["reply_to_id"]) if r["reply_to_id"] else None,
            "mentions": mentions,
            "reactions": reactions_map.get(r["id"], []),
            "edited": r["edited_at"] is not None,
        })
    reactions_updates = {str(mid): reactions_map.get(mid, []) for mid in recent_ids}
    return jsonify({
        "messages": msgs,
        "pinned": ({"id": pinned["id"], "body": _visible_group_body_for_user(pinned["body"], pinned["kind"], u), "kind": pinned["kind"]} if pinned else None),
        "deleted_ids": deleted_ids,
        "reactions_updates": reactions_updates,
    })


@app.route("/group/send", methods=["POST"])
@login_required
def group_send():
    u = current_user()
    # منع الإرسال إذا كانت الدردشة مقفولة (إلا للمسؤول)
    if u["role"] != "admin":
        _gs = _get_group_settings()
        if _gs and _gs["is_locked"]:
            return jsonify({"ok": False, "error": "locked", "message": "الدردشة مقفولة من المسؤول"}), 403
    kind = request.form.get("kind", "text")
    body = None
    if kind == "text":
        text = (request.form.get("body") or "").strip()
        if not text:
            return jsonify({"ok": False, "error": "empty"}), 400
        if len(text) > 4000:
            text = text[:4000]
        body = text
    elif kind in ("image", "audio"):
        f = request.files.get("file")
        if not f:
            return jsonify({"ok": False, "error": "no_file"}), 400
        data = f.read()
        if len(data) > 8 * 1024 * 1024:
            return jsonify({"ok": False, "error": "too_large"}), 413
        mime = f.mimetype or ("image/jpeg" if kind == "image" else "audio/webm")
        body = "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")
    else:
        return jsonify({"ok": False, "error": "bad_kind"}), 400

    # reply + mentions
    reply_to_id = request.form.get("reply_to_id")
    try:
        reply_to_id = int(reply_to_id) if reply_to_id else None
    except (TypeError, ValueError):
        reply_to_id = None
    mention_ids = []
    for raw in request.form.getlist("mentions"):
        try:
            mention_ids.append(int(raw))
        except (TypeError, ValueError):
            pass
    mentions_json = _json.dumps(mention_ids) if mention_ids else None

    db = get_db()
    cur = db.cursor()
    cur.execute("""INSERT INTO group_messages(sender_id, kind, body, reply_to_id, mentions)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id, created_at""",
                (u["id"], kind, body, reply_to_id, mentions_json))
    row = cur.fetchone()
    db.commit()

    # 🔔 إشعارات: للمُنشَن + لصاحب الرسالة اللي بيتم الرد عليها
    notify_ids = set(mention_ids)
    if reply_to_id:
        cur.execute("SELECT sender_id FROM group_messages WHERE id=%s", (reply_to_id,))
        rr = cur.fetchone()
        if rr and rr["sender_id"] and rr["sender_id"] != u["id"]:
            notify_ids.add(rr["sender_id"])
    notify_ids.discard(u["id"])
    cur.close()
    if notify_ids:
        preview = body if kind == "text" else ("[صورة]" if kind == "image" else "[رسالة صوتية]")
        _notify_users(list(notify_ids),
                      f"{u['full_name']} في المجموعة",
                      (preview or "")[:120],
                      url=url_for("group_room"),
                      type_="group_mention")
    return jsonify({"ok": True, "id": row["id"], "created_at": _iso_utc(row["created_at"])})


@app.route("/group/delete/<int:msg_id>", methods=["POST"])
@login_required
def group_delete_msg(msg_id):
    u = current_user()
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT sender_id FROM group_messages WHERE id=%s", (msg_id,))
    r = cur.fetchone()
    if not r:
        cur.close()
        return jsonify({"ok": False, "error": "not_found"}), 404
    if u["role"] != "admin" and r["sender_id"] != u["id"]:
        cur.execute("SELECT can_delete FROM group_perms WHERE user_id=%s", (u["id"],))
        _pr = cur.fetchone()
        if not (_pr and _pr["can_delete"]):
            cur.close()
            return jsonify({"ok": False, "error": "forbidden"}), 403
    cur.execute("UPDATE group_messages SET deleted=TRUE, body=NULL, pinned=FALSE WHERE id=%s", (msg_id,))
    db.commit()
    cur.close()
    return jsonify({"ok": True})


@app.route("/group/avatar", methods=["POST"])
@admin_required
def group_avatar():
    f = request.files.get("file")
    if not f:
        flash("اختر صورة", "error")
        return redirect(url_for("group_room"))
    data = f.read()
    if len(data) > 5 * 1024 * 1024:
        flash("الصورة كبيرة (الحد 5 ميجا)", "error")
        return redirect(url_for("group_room"))
    mime = f.mimetype or "image/jpeg"
    data_url = "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE group_settings SET avatar=%s WHERE id=1", (data_url,))
    db.commit()
    cur.close()
    flash("تم تحديث صورة المجموعة ✓", "success")
    return redirect(url_for("group_room"))


@app.route("/group/rename", methods=["POST"])
@admin_required
def group_rename():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("ادخل اسم", "error")
        return redirect(url_for("group_room"))
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE group_settings SET name=%s WHERE id=1", (name[:60],))
    db.commit()
    cur.close()
    flash("تم تحديث اسم المجموعة ✓", "success")
    return redirect(url_for("group_room"))


@app.route("/group/lock", methods=["POST"])
@admin_required
def group_toggle_lock():
    """قفل/فتح الدردشة — المسؤول فقط. لما تكون مقفولة، لا أحد غير المسؤول يقدر يرسل."""
    val = (request.form.get("locked") or "").strip().lower() in ("1", "true", "on", "yes")
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE group_settings SET is_locked=%s WHERE id=1", (val,))
    db.commit()
    cur.close()
    return jsonify({"ok": True, "is_locked": val})





@app.route("/group/members")
@login_required
def group_members_api():
    db = get_db()
    cur = db.cursor()
    cur.execute("""SELECT u.id, u.full_name, u.username, u.avatar, u.role, u.last_seen,
                          COALESCE(gp.can_delete, FALSE) AS can_delete
                   FROM users u LEFT JOIN group_perms gp ON gp.user_id = u.id
                   ORDER BY u.full_name""")
    rows = cur.fetchall()
    cur.close()
    members = []
    for r in rows:
        members.append({
            "id": r["id"],
            "full_name": r["full_name"],
            "username": r["username"],
            "avatar": r["avatar"],
            "role": r["role"],
            "online": _is_online(r["last_seen"]),
            "last_seen": _iso_utc(r["last_seen"]),
            "can_delete": bool(r["can_delete"]),
        })
    members.sort(key=lambda m: (not m["online"], m["full_name"]))
    online_count = sum(1 for m in members if m["online"])
    return jsonify({"members": members, "online": online_count, "total": len(members)})


# ================== تفاعلات (Reactions) ==================
@app.route("/chat/<int:other_id>/react/<int:msg_id>", methods=["POST"])
@login_required
def chat_react(other_id, msg_id):
    u = current_user()
    emoji = (request.form.get("emoji") or "").strip()
    # تحقّق: الرسالة تخص المحادثة بين u و other_id
    db = get_db(); cur = db.cursor()
    cur.execute("""SELECT id FROM chat_messages
                   WHERE id=%s AND ((sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s))""",
                (msg_id, u["id"], other_id, other_id, u["id"]))
    if not cur.fetchone():
        cur.close(); return jsonify({"ok": False, "error": "not_found"}), 404
    cur.close()
    reactions, err = _toggle_reaction("chat_reactions", msg_id, u["id"], emoji)
    if err: return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True, "message_id": msg_id, "reactions": reactions})


@app.route("/group/perms/<int:uid>", methods=["POST"])
@login_required
def group_set_perm(uid):
    u = current_user()
    if u["role"] != "admin":
        return jsonify({"ok": False, "error": "forbidden"}), 403
    val = (request.form.get("can_delete") or "").strip().lower() in ("1","true","on","yes")
    db = get_db(); cur = db.cursor()
    cur.execute("""INSERT INTO group_perms(user_id, can_delete, updated_at)
                   VALUES(%s,%s,NOW())
                   ON CONFLICT (user_id) DO UPDATE SET can_delete=EXCLUDED.can_delete, updated_at=NOW()""",
                (uid, val))
    db.commit(); cur.close()
    return jsonify({"ok": True, "user_id": uid, "can_delete": val})


@app.route("/group/react/<int:msg_id>", methods=["POST"])
@login_required
def group_react(msg_id):
    u = current_user()
    emoji = (request.form.get("emoji") or "").strip()
    db = get_db(); cur = db.cursor()
    cur.execute("SELECT id FROM group_messages WHERE id=%s AND deleted=FALSE", (msg_id,))
    if not cur.fetchone():
        cur.close(); return jsonify({"ok": False, "error": "not_found"}), 404
    cur.close()
    reactions, err = _toggle_reaction("group_reactions", msg_id, u["id"], emoji)
    if err: return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True, "message_id": msg_id, "reactions": reactions})


@app.route("/me/avatar", methods=["POST"])
@login_required
def update_avatar():
    u = current_user()
    f = request.files.get("file")
    if not f:
        flash("اختر صورة", "error")
        return redirect(request.referrer or url_for("chats_list"))
    data = f.read()
    if len(data) > 5 * 1024 * 1024:
        flash("الصورة كبيرة (الحد 5 ميجا)", "error")
        return redirect(request.referrer or url_for("chats_list"))
    mime = f.mimetype or "image/jpeg"
    data_url = "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE users SET avatar=%s WHERE id=%s", (data_url, u["id"]))
    db.commit()
    cur.close()
    flash("تم تحديث صورتك ✓", "success")
    return redirect(request.referrer or url_for("chats_list"))


@app.route("/me/cover", methods=["POST"])
@login_required
def update_cover():
    u = current_user()
    action = request.form.get("action", "")
    db = get_db()
    cur = db.cursor()
    if action == "remove":
        cur.execute("UPDATE users SET cover=NULL WHERE id=%s", (u["id"],))
        db.commit()
        cur.close()
        flash("تم إزالة صورة الغلاف", "info")
        return redirect(request.referrer or url_for("chats_list"))
    f = request.files.get("file")
    if not f:
        flash("اختر صورة", "error")
        return redirect(request.referrer or url_for("chats_list"))
    data = f.read()
    if len(data) > 5 * 1024 * 1024:
        flash("الصورة كبيرة (الحد 5 ميجا)", "error")
        return redirect(request.referrer or url_for("chats_list"))
    mime = f.mimetype or "image/jpeg"
    data_url = "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")
    cur.execute("UPDATE users SET cover=%s WHERE id=%s", (data_url, u["id"]))
    db.commit()
    cur.close()
    flash("تم تحديث صورة الغلاف ✓", "success")
    return redirect(request.referrer or url_for("chats_list"))


# ---- تعديل إجمالي يوم مقفول + تصفير فترة (المسؤول) ----
@app.route("/admin/edit-day-total", methods=["POST"])
@admin_required
def admin_edit_day_total():
    u = current_user()
    day = request.form.get("day", "").strip()
    # ندعم مدخلين منفصلين (تسمين + بياض) — والقديم total_count يبقى للتوافق
    def _int_or(v, default=None):
        try:
            iv = int(v)
            if iv < 0: return default
            return iv
        except (TypeError, ValueError):
            return default
    tasmeen_after = _int_or(request.form.get("tasmeen_after"), None)
    bayad_after = _int_or(request.form.get("bayad_after"), None)
    total_form = _int_or(request.form.get("total_count"), None)
    no_deduct_total = _int_or(request.form.get("no_deduct_total"), 0) or 0

    db = get_db()
    cur = db.cursor()
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS no_deduct_total INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS tasmeen_after INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS bayad_after INTEGER NOT NULL DEFAULT 0")

    # لو اتبعت واحد فيهم بس — نحافظ على القيمة الحالية للتاني
    if tasmeen_after is None or bayad_after is None:
        cur.execute("SELECT COALESCE(tasmeen_after,0) AS t, COALESCE(bayad_after,0) AS b, total_count FROM day_closures WHERE day=%s", (day,))
        row = cur.fetchone()
        cur_t = int(row["t"]) if row else 0
        cur_b = int(row["b"]) if row else 0
        # لو الصف قديم من غير فصل — نعتبر الكل تسمين للتوافق
        if row and cur_t == 0 and cur_b == 0 and int(row["total_count"] or 0) > 0:
            cur_t = int(row["total_count"])
        if tasmeen_after is None: tasmeen_after = cur_t
        if bayad_after is None: bayad_after = cur_b

    # لو المسؤول بعت total_count بس (نموذج قديم) — من غير tasmeen/bayad — نعتبره تسمين
    if total_form is not None and request.form.get("tasmeen_after") is None and request.form.get("bayad_after") is None:
        tasmeen_after = total_form
        bayad_after = 0

    total = int(tasmeen_after) + int(bayad_after)
    cur.execute("""INSERT INTO day_closures(day, closed_by, total_count, tasmeen_after, bayad_after, no_deduct_total)
                   VALUES(%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (day) DO UPDATE SET total_count = EXCLUDED.total_count,
                                                    tasmeen_after = EXCLUDED.tasmeen_after,
                                                    bayad_after = EXCLUDED.bayad_after,
                                                    no_deduct_total = EXCLUDED.no_deduct_total""",
                (day, u["id"], total, tasmeen_after, bayad_after, no_deduct_total))
    db.commit()
    cur.close()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({
            "ok": True,
            "day": day,
            "tasmeen_after": int(tasmeen_after),
            "bayad_after": int(bayad_after),
            "total": int(total),
        })
    flash("تم تحديث إجمالي يوم " + day + " (تسمين " + str(tasmeen_after) + " + بياض " + str(bayad_after) + ") ✓", "success")
    return redirect(url_for("history"))


@app.route("/admin/reset-period", methods=["POST"])
@admin_required
def admin_reset_period():
    """يمسح كل إغلاقات + تحصينات + حضور فترة (نصف شهر أو شهر كامل)"""
    start_d = request.form.get("start", "").strip()
    end_d   = request.form.get("end", "").strip()
    if not (start_d and end_d):
        flash("فترة غير صالحة", "error")
        return redirect(url_for("history"))
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("DELETE FROM vaccinations WHERE day BETWEEN %s AND %s", (start_d, end_d))
        cur.execute("DELETE FROM attendance   WHERE day BETWEEN %s AND %s", (start_d, end_d))
        cur.execute("DELETE FROM day_closures WHERE day BETWEEN %s AND %s", (start_d, end_d))
        # نمسح ملخصات الفترة اللي جواها الفترة دي (لو موجودة)
        cur.execute("""DELETE FROM period_summaries
                       WHERE make_date(year, month, CASE WHEN half=1 THEN 1 ELSE 16 END) BETWEEN %s AND %s""",
                    (start_d, end_d))
        db.commit()
        flash("تم تصفير الفترة من " + start_d + " إلى " + end_d + " ✓", "success")
    except Exception as e:
        db.rollback()
        flash("خطأ أثناء التصفير: " + str(e), "error")
    finally:
        cur.close()
    return redirect(url_for("history"))


@app.route("/me/ping", methods=["POST"])
@login_required
def ping():
    return jsonify({"ok": True, "ts": datetime.now(timezone.utc).isoformat()})


@app.route("/init-db")
def init_db_route():
    secret = request.args.get("secret", "")
    if secret != os.environ.get("INIT_SECRET", ""):
        return "غير مسموح", 403
    try:
        init_db()
        return "تم إنشاء قاعدة البيانات", 200
    except Exception as e:
        return f"خطأ: {e}", 500


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)

# ---------- favicon + error handlers ----------
@app.route("/favicon.ico")
@app.route("/favicon.png")
def _favicon():
    from flask import send_from_directory
    import os as _os
    static_dir = _os.path.join(app.root_path, "static")
    for name in ("favicon.ico", "favicon.png", "logo.png"):
        if _os.path.exists(_os.path.join(static_dir, name)):
            return send_from_directory(static_dir, name)
    return ("", 204)


# =========================================================================
# ============================ ملاحظات المسؤول (Notes) ====================
# =========================================================================
NOTE_COLORS = ["gold", "green", "blue", "pink", "purple", "slate"]

@app.route("/admin/notes")
@admin_required
def admin_notes():
    db = get_db(); cur = db.cursor()
    cur.execute("""
        SELECT id, title, body, color, pinned, created_at, updated_at
        FROM admin_notes ORDER BY pinned DESC, updated_at DESC
    """)
    notes = cur.fetchall()
    cur.close()
    return render_template("admin_notes.html", notes=notes, note_colors=NOTE_COLORS)


@app.route("/admin/notes/create", methods=["POST"])
@admin_required
def admin_notes_create():
    u = current_user()
    title = (request.form.get("title") or "").strip() or None
    body  = (request.form.get("body")  or "").strip()
    color = (request.form.get("color") or "gold").strip()
    if color not in NOTE_COLORS: color = "gold"
    if not body:
        flash("اكتب محتوى الملاحظة", "error")
        return redirect(url_for("admin_notes"))
    db = get_db(); cur = db.cursor()
    cur.execute("""INSERT INTO admin_notes(admin_id, title, body, color)
                   VALUES(%s,%s,%s,%s)""", (u["id"], title, body, color))
    db.commit(); cur.close()
    flash("تم حفظ الملاحظة ✓", "success")
    return redirect(url_for("admin_notes"))


@app.route("/admin/notes/<int:nid>/update", methods=["POST"])
@admin_required
def admin_notes_update(nid):
    title = (request.form.get("title") or "").strip() or None
    body  = (request.form.get("body")  or "").strip()
    color = (request.form.get("color") or "gold").strip()
    if color not in NOTE_COLORS: color = "gold"
    if not body:
        flash("محتوى الملاحظة فاضي", "error")
        return redirect(url_for("admin_notes"))
    db = get_db(); cur = db.cursor()
    cur.execute("""UPDATE admin_notes SET title=%s, body=%s, color=%s, updated_at=NOW()
                   WHERE id=%s""", (title, body, color, nid))
    db.commit(); cur.close()
    flash("تم تعديل الملاحظة ✓", "success")
    return redirect(url_for("admin_notes"))


@app.route("/admin/notes/<int:nid>/pin", methods=["POST"])
@admin_required
def admin_notes_pin(nid):
    db = get_db(); cur = db.cursor()
    cur.execute("UPDATE admin_notes SET pinned = NOT pinned, updated_at=NOW() WHERE id=%s", (nid,))
    db.commit(); cur.close()
    return redirect(url_for("admin_notes"))


@app.route("/admin/notes/<int:nid>/delete", methods=["POST"])
@admin_required
def admin_notes_delete(nid):
    db = get_db(); cur = db.cursor()
    cur.execute("DELETE FROM admin_notes WHERE id=%s", (nid,))
    db.commit(); cur.close()
    flash("تم حذف الملاحظة", "success")
    return redirect(url_for("admin_notes"))


# =========================================================================
# ================== المكالمات الصوتية (تمت الإزالة) =======================
# =========================================================================
# تم شيل كل مسارات وواجهات المكالمات بناءً على طلب الإدارة.



# ====================== تنزيل الوسائط (صور/صوت) باسم صحيح ======================
_MEDIA_EXT = {
    "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png",
    "image/webp": "webp", "image/gif": "gif", "image/heic": "heic",
    "audio/webm": "webm", "audio/ogg": "ogg", "audio/mpeg": "mp3",
    "audio/mp4": "m4a", "audio/aac": "aac", "audio/wav": "wav",
}

def _decode_data_url(body):
    if not body or not body.startswith("data:"):
        return None, None
    try:
        header, b64 = body.split(",", 1)
        mime = header[5:].split(";")[0].strip() or "application/octet-stream"
        data = base64.b64decode(b64)
        return mime, data
    except Exception:
        return None, None

@app.route("/media/<scope>/<int:msg_id>")
@login_required
def media_msg(scope, msg_id):
    """يرجّع صورة/صوت الرسالة بامتداد صحيح + Content-Disposition عشان يتحفظ بشكل سليم على أندرويد."""
    u = current_user()
    db = get_db(); cur = db.cursor()
    row = None
    if scope == "group":
        cur.execute("SELECT id, kind, body FROM group_messages WHERE id=%s AND deleted=FALSE", (msg_id,))
        row = cur.fetchone()
    elif scope == "chat":
        cur.execute("SELECT id, kind, body, sender_id, receiver_id FROM chat_messages WHERE id=%s", (msg_id,))
        row = cur.fetchone()
        if row and u["id"] not in (row["sender_id"], row["receiver_id"]):
            cur.close(); abort(403)
    cur.close()
    if not row:
        abort(404)
    if row["kind"] not in ("image", "audio"):
        abort(404)
    mime, data = _decode_data_url(row["body"])
    if data is None:
        abort(404)
    ext = _MEDIA_EXT.get(mime, "jpg" if row["kind"] == "image" else "webm")
    # اسم الملف: يبدأ بـ "صور تطبيق التحصين" عشان يتجمّع فى الداونلودز
    prefix = "صور تطبيق التحصين" if row["kind"] == "image" else "أصوات تطبيق التحصين"
    fname = f"{prefix}_{scope}_{msg_id}.{ext}"
    ascii_fallback = f"TahsinApp_{scope}_{msg_id}.{ext}"
    dl = request.args.get("dl", "0") == "1"
    resp = Response(data, mimetype=mime)
    disp = "attachment" if dl else "inline"
    resp.headers["Content-Disposition"] = (
        f'{disp}; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{_urlquote(fname)}"
    )
    resp.headers["Cache-Control"] = "private, max-age=86400"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp



# ==================== نظام الإشعارات + FCM ====================

_FIREBASE_APP = None

def _get_firebase_app():
    """يهيّئ Firebase Admin SDK مرة واحدة فقط (lazy init)."""
    global _FIREBASE_APP
    if _FIREBASE_APP is not None:
        return _FIREBASE_APP
    try:
        import firebase_admin
        from firebase_admin import credentials
        project_id = os.environ.get("FIREBASE_PROJECT_ID", "")
        client_email = os.environ.get("FIREBASE_CLIENT_EMAIL", "")
        private_key = os.environ.get("FIREBASE_PRIVATE_KEY", "")
        if not (project_id and client_email and private_key):
            return None
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": project_id,
            "client_email": client_email,
            "private_key": private_key.replace("\\n", "\n"),
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        _FIREBASE_APP = firebase_admin.initialize_app(cred)
        return _FIREBASE_APP
    except Exception as e:
        print("Firebase init error:", e)
        return None


def _send_fcm(tokens, title, body, url=""):
    """يبعث إشعار FCM لقائمة توكنات عن طريق HTTP v1 API (Firebase Admin SDK).
    صامت لو مفيش إعدادات Firebase أو مفيش توكنات."""
    tokens = [t for t in (tokens or []) if t]
    if not tokens:
        return
    app_fb = _get_firebase_app()
    if app_fb is None:
        print("FCM skipped: Firebase not configured")
        return
    try:
        from firebase_admin import messaging
        invalid_tokens = []
        # multicast v1 API - نرسل لحد 500 توكن في المرة الواحدة
        for i in range(0, len(tokens), 500):
            batch = tokens[i:i + 500]
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title[:200], body=(body or "")[:200]
                ),
                data={
                    "title": str(title or ""),
                    "body":  str(body or ""),
                    "url":   str(url or ""),
                    "click_action": "FLUTTER_NOTIFICATION_CLICK",
                },
                android=messaging.AndroidConfig(
                    priority="high",
                    ttl=3600,
                    notification=messaging.AndroidNotification(
                        title=title[:200],
                        body=(body or "")[:200],
                        sound="default",
                        channel_id="default_channel",
                        priority="max",
                        default_sound=True,
                        default_vibrate_timings=True,
                        visibility="public",
                        notification_count=1,
                    ),
                ),
                tokens=batch,
            )
            response = messaging.send_each_for_multicast(message)
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    err = str(resp.exception)
                    if "UNREGISTERED" in err or "INVALID_ARGUMENT" in err or "NOT_FOUND" in err:
                        invalid_tokens.append(batch[idx])
        if invalid_tokens:
            try:
                db = get_db(); cur = db.cursor()
                cur.execute("DELETE FROM fcm_tokens WHERE token = ANY(%s)", (invalid_tokens,))
                db.commit(); cur.close()
            except Exception as ce:
                print("FCM cleanup error:", ce)
    except Exception as e:
        print("FCM error:", e)


def _notify_users(user_ids, title, body, url="", type_="general", push=True):
    """يضيف صف في notifications لكل مستخدم + يبعت FCM اختياريًا."""
    ids = [int(x) for x in user_ids if x]
    if not ids:
        return
    db = get_db(); cur = db.cursor()
    for uid in ids:
        cur.execute("""INSERT INTO notifications(user_id, title, body, url, type)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (uid, title[:200], (body or "")[:1000], url or None, type_))
    db.commit()
    if push:
        cur.execute("SELECT token FROM fcm_tokens WHERE user_id = ANY(%s)", (ids,))
        tokens = [r["token"] for r in cur.fetchall()]
        if tokens:
            _send_fcm(tokens, title, body or "", url or "")
    cur.close()


@app.route("/api/notifications/unread")
@login_required
def api_notifications_unread():
    u = current_user()
    db = get_db(); cur = db.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM notifications WHERE user_id=%s AND read_at IS NULL", (u["id"],))
    count = cur.fetchone()["c"]
    cur.execute("""SELECT id, title, body, url, type, created_at, read_at
                   FROM notifications WHERE user_id=%s
                   ORDER BY id DESC LIMIT 20""", (u["id"],))
    items = [{
        "id": r["id"], "title": r["title"], "body": r["body"], "url": r["url"],
        "type": r["type"], "created_at": _iso_utc(r["created_at"]),
        "read": r["read_at"] is not None,
    } for r in cur.fetchall()]
    cur.close()
    return jsonify({"count": count, "items": items})


@app.route("/notifications")
@login_required
def notifications_page():
    u = current_user()
    db = get_db(); cur = db.cursor()
    cur.execute("""SELECT id, title, body, url, type, created_at, read_at
                   FROM notifications WHERE user_id=%s
                   ORDER BY id DESC LIMIT 200""", (u["id"],))
    rows = cur.fetchall()
    cur.execute("UPDATE notifications SET read_at=NOW() WHERE user_id=%s AND read_at IS NULL", (u["id"],))
    db.commit(); cur.close()
    return render_template("notifications.html", items=rows)


@app.route("/notifications/mark-all-read", methods=["POST"])
@login_required
def notifications_mark_all_read():
    u = current_user()
    db = get_db(); cur = db.cursor()
    cur.execute("UPDATE notifications SET read_at=NOW() WHERE user_id=%s AND read_at IS NULL", (u["id"],))
    db.commit(); cur.close()
    return jsonify({"ok": True})


@app.route("/notifications/<int:nid>/delete", methods=["POST"])
@login_required
def notification_delete(nid):
    u = current_user()
    db = get_db(); cur = db.cursor()
    cur.execute("DELETE FROM notifications WHERE id=%s AND user_id=%s", (nid, u["id"]))
    db.commit(); cur.close()
    return jsonify({"ok": True})


@app.route("/notifications/delete-all", methods=["POST"])
@login_required
def notifications_delete_all():
    u = current_user()
    db = get_db(); cur = db.cursor()
    cur.execute("DELETE FROM notifications WHERE user_id=%s", (u["id"],))
    db.commit(); cur.close()
    return jsonify({"ok": True})


@app.route("/admin/notify", methods=["GET", "POST"])
@admin_required
def admin_notify():
    db = get_db(); cur = db.cursor()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        body  = (request.form.get("body") or "").strip()
        url   = (request.form.get("url") or "").strip()
        target = request.form.get("target", "all")
        if not title:
            flash("لازم تكتب عنوان للإشعار", "error")
            return redirect(url_for("admin_notify"))
        if target == "all":
            cur.execute("SELECT id FROM users")
            user_ids = [r["id"] for r in cur.fetchall()]
        else:
            raw = request.form.getlist("user_ids")
            user_ids = [int(x) for x in raw if x]
            if not user_ids:
                flash("اختر عامل واحد على الأقل", "error")
                return redirect(url_for("admin_notify"))
        cur.close()
        _notify_users(user_ids, title, body, url=url, type_="admin_broadcast")
        flash(f"تم إرسال الإشعار لـ {len(user_ids)} مستخدم ✓", "success")
        return redirect(url_for("admin_notify"))
    cur.execute("SELECT id, full_name, role FROM users ORDER BY (role='admin') DESC, full_name")
    users = cur.fetchall()
    cur.close()
    return render_template("admin_notify.html", users=users)


@app.route("/api/fcm/register", methods=["POST"])
@login_required
def api_fcm_register():
    u = current_user()
    token = (request.form.get("token") or (request.json or {}).get("token") if request.is_json else request.form.get("token") or "").strip()
    if not token or len(token) < 20:
        return jsonify({"ok": False, "error": "bad_token"}), 400
    platform = (request.form.get("platform") or "android").strip()[:20]
    db = get_db(); cur = db.cursor()
    cur.execute("""INSERT INTO fcm_tokens(user_id, token, platform) VALUES(%s,%s,%s)
                   ON CONFLICT (token) DO UPDATE SET user_id=EXCLUDED.user_id, last_seen=NOW()""",
                (u["id"], token, platform))
    db.commit(); cur.close()
    return jsonify({"ok": True})


@app.route("/api/fcm/unregister", methods=["POST"])
@login_required
def api_fcm_unregister():
    token = (request.form.get("token") or "").strip()
    if token:
        db = get_db(); cur = db.cursor()
        cur.execute("DELETE FROM fcm_tokens WHERE token=%s", (token,))
        db.commit(); cur.close()
    return jsonify({"ok": True})


from werkzeug.exceptions import HTTPException as _HTTPException
import traceback as _tb, os as _os_env

@app.errorhandler(_HTTPException)
def _handle_http_exc(e):
    # نرجّع الرد الطبيعي (404/403/…): من غير ما نحوّله 500
    return e

@app.errorhandler(Exception)
def _handle_any_exc(e):
    print("=== UNHANDLED ERROR ===\n", _tb.format_exc(), flush=True)
    if _os_env.environ.get("SHOW_ERRORS") == "1":
        return ("<pre style='direction:ltr;text-align:left'>" + _tb.format_exc() + "</pre>", 500)
    # لو الخطأ حصل في صفحة اترجعنا ليها تلقائيًا — نمسح الكوكي عشان ما يتكررش
    html = ("<!doctype html><html dir='rtl' lang='ar'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<body style=\"font-family:system-ui;background:#0f1a24;color:#eee;"
            "display:grid;place-items:center;min-height:100vh;margin:0;text-align:center\">"
            "<div><h2>حصل خطأ مؤقت</h2>"
            "<p style='color:#9fb0c0'>جرّب تاني أو ارجع للرئيسية.</p>"
            "<a href='/dashboard' style='display:inline-block;padding:10px 20px;border-radius:99px;"
            "background:#e3b445;color:#12202b;font-weight:800;text-decoration:none'>الرئيسية</a>"
            "</div></body></html>")
    return make_response(html, 500)



# =========================================================================
# =================== إدارة المساحة (Storage) — للمسؤول الرئيسي ===========
# =========================================================================
import json as _json_st
from datetime import datetime as _dt_st

# على Vercel/السيرفرلس نظام الملفات للقراءة فقط ما عدا /tmp
# فبنستخدم /tmp/th_backups، ومنعملش المجلد إلا لما فعلاً نحتاج نكتب ملف
# (يعني بس لما مساحة قاعدة البيانات تخلص ويشتغل الأرشيف التلقائي).
if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or not os.access(app.root_path, os.W_OK):
    _BACKUP_DIR = os.environ.get("BACKUP_DIR", "/tmp/th_backups")
else:
    _BACKUP_DIR = os.environ.get("BACKUP_DIR", os.path.join(app.root_path, "backups"))

def _ensure_backup_dir():
    """ينشئ مجلد النسخ الاحتياطي عند الحاجة فقط (بدل ما يفشل عند الاستيراد)."""
    try:
        os.makedirs(_BACKUP_DIR, exist_ok=True)
        return True
    except OSError as _e:
        print(f"[backup] لا يمكن إنشاء {_BACKUP_DIR}: {_e}", flush=True)
        return False

# الجداول اللي المسؤول ممكن يحذف منها لتفريغ مساحة
_STORAGE_TABLES = [
    ("chat_messages",     "رسائل الدردشة الخاصة",  "created_at"),
    ("group_messages",    "رسائل الجروب",           "created_at"),
    ("notifications",     "الإشعارات",              "created_at"),
    ("admin_notes",       "ملاحظات المسؤول",        "created_at"),
    ("vaccinations",      "تسجيلات اللقاحات",       "created_at"),
    ("attendance",        "سجلات الحضور",           "checked_in_at"),
    ("group_reads",       "قراءات الجروب",          None),
    ("chat_reactions",    "تفاعلات الدردشة",        "created_at"),
    ("group_reactions",   "تفاعلات الجروب",         "created_at"),
    ("voice_signals",     "إشارات المكالمات",       "created_at"),
    ("voice_participants","مشاركو المكالمات",       None),
    ("fcm_tokens",        "توكنات الإشعارات",       "last_seen"),
]

def _fmt_bytes(n):
    n = int(n or 0)
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f} {u}" if u != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} PB"


def _table_stats():
    """يرجّع حجم وعدد كل جدول من _STORAGE_TABLES."""
    db = get_db(); cur = db.cursor()
    rows = []
    total_bytes = 0
    for tname, label, date_col in _STORAGE_TABLES:
        try:
            cur.execute(f"SELECT pg_total_relation_size(%s) AS sz", (tname,))
            sz = int(cur.fetchone()["sz"] or 0)
            cur.execute(f"SELECT COUNT(*) AS c FROM {tname}")
            cnt = int(cur.fetchone()["c"] or 0)
            rows.append({
                "table": tname, "label": label, "size": sz,
                "size_h": _fmt_bytes(sz), "count": cnt,
                "date_col": date_col,
            })
            total_bytes += sz
        except Exception as e:
            print(f"stats err {tname}:", e)
    # حجم كل قاعدة البيانات
    try:
        cur.execute("SELECT pg_database_size(current_database()) AS db_sz")
        db_size = int(cur.fetchone()["db_sz"] or 0)
    except Exception:
        db_size = total_bytes
    cur.close()
    rows.sort(key=lambda r: -r["size"])
    return {"tables": rows, "total": total_bytes, "db_size": db_size,
            "db_size_h": _fmt_bytes(db_size)}


def _backup_before_delete(table, where_sql, params):
    """يعمل export CSV/JSON للسطور المستهدفة قبل حذفها."""
    try:
        db = get_db(); cur = db.cursor()
        cur.execute(f"SELECT * FROM {table} {where_sql}", params)
        rows = cur.fetchall()
        cur.close()
        if not rows:
            return None, 0
        if not _ensure_backup_dir():
            return None, 0
        ts = _dt_st.utcnow().strftime("%Y%m%d_%H%M%S")
        fname = f"{table}_{ts}.json"
        fpath = os.path.join(_BACKUP_DIR, fname)
        # تحويل التواريخ لسترنج قابل للسريلَة
        def _ser(o):
            if hasattr(o, "isoformat"):
                return o.isoformat()
            return str(o)
        with open(fpath, "w", encoding="utf-8") as f:
            _json_st.dump([dict(r) for r in rows], f, ensure_ascii=False,
                          default=_ser, indent=2)
        return fname, len(rows)
    except Exception as e:
        print("backup err:", e)
        return None, 0


def _list_backups():
    try:
        if not os.path.isdir(_BACKUP_DIR):
            return []
        files = []
        for name in sorted(os.listdir(_BACKUP_DIR), reverse=True):
            fpath = os.path.join(_BACKUP_DIR, name)
            if os.path.isfile(fpath):
                st = os.stat(fpath)
                files.append({
                    "name": name,
                    "size": st.st_size,
                    "size_h": _fmt_bytes(st.st_size),
                    "at": _dt_st.utcfromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                })
        return files
    except Exception:
        return []


# حد المساحة (بايت) اللي بعده يبدأ الأرشيف التلقائي — افتراضي 400MB
_AUTO_ARCHIVE_LIMIT = int(os.environ.get("AUTO_ARCHIVE_BYTES", str(400 * 1024 * 1024)))
_AUTO_ARCHIVE_KEEP_DAYS = int(os.environ.get("AUTO_ARCHIVE_KEEP_DAYS", "90"))

def _auto_archive_if_needed():
    """لو حجم الـ DB عدّى الحد الأقصى، بيأرشف أقدم رسائل/إشعارات في ملف JSON ويحذفهم."""
    try:
        db = get_db(); cur = db.cursor()
        cur.execute("SELECT pg_database_size(current_database()) AS sz")
        sz = int(cur.fetchone()["sz"] or 0)
        if sz < _AUTO_ARCHIVE_LIMIT:
            cur.close()
            return None
        # نأرشف الأقدم من X يوم من chat_messages ثم group_messages ثم notifications
        archived_any = False
        for tname in ("chat_messages", "group_messages", "notifications"):
            where = f"WHERE created_at < NOW() - INTERVAL '{_AUTO_ARCHIVE_KEEP_DAYS} days'"
            fname, n = _backup_before_delete(tname, where, ())
            if n > 0:
                cur.execute(f"DELETE FROM {tname} {where}")
                db.commit()
                archived_any = True
                print(f"[auto-archive] {tname}: {n} rows -> {fname}")
        cur.close()
        return archived_any
    except Exception as e:
        print("auto-archive err:", e)
        return None


def _server_info():
    """معلومات فعلية 100% عن السيرفر — كل قيمة مقروءة من مصدرها المباشر."""
    import sys as _sys, platform as _plat, time as _time, socket as _sock
    info = {}
    # Runtime
    info["python"] = _sys.version.split()[0]
    info["platform"] = _plat.platform()
    info["machine"] = _plat.machine() or "-"
    try:
        import flask as _flk; info["flask"] = _flk.__version__
    except Exception:
        info["flask"] = "-"
    try:
        info["psycopg2"] = psycopg2.__version__.split(" ")[0]
    except Exception:
        info["psycopg2"] = "-"
    # Hosting
    info["host"] = _sock.gethostname()
    info["region"] = os.environ.get("VERCEL_REGION") or os.environ.get("AWS_REGION") or "-"
    info["env"] = os.environ.get("VERCEL_ENV") or ("vercel" if os.environ.get("VERCEL") else ("lambda" if os.environ.get("AWS_LAMBDA_FUNCTION_NAME") else "local"))
    # Uptime (منذ استيراد الموديول — دقيق للـ instance الحالي)
    info["boot_at"] = getattr(app, "_boot_time", None)
    if info["boot_at"] is None:
        info["boot_at"] = _time.time(); app._boot_time = info["boot_at"]
    up = max(0, int(_time.time() - info["boot_at"]))
    h, r = divmod(up, 3600); m, s = divmod(r, 60)
    info["uptime"] = f"{h}س {m}د {s}ث" if h else f"{m}د {s}ث"
    # DB
    try:
        db = get_db(); cur = db.cursor()
        cur.execute("SELECT version() AS v, current_database() AS d, NOW() AS n, current_user AS u")
        r = cur.fetchone()
        info["db_version"] = (r["v"] or "").split(" on ")[0]
        info["db_name"] = r["d"]; info["db_user"] = r["u"]
        info["db_time"] = r["n"].isoformat(timespec="seconds") if hasattr(r["n"],"isoformat") else str(r["n"])
        cur.execute("SELECT pg_size_pretty(pg_database_size(current_database())) AS s, pg_database_size(current_database()) AS b")
        r = cur.fetchone()
        info["db_size_pretty"] = r["s"]; info["db_size_bytes"] = int(r["b"] or 0)
        cur.execute("SELECT COUNT(*) AS c FROM pg_stat_activity WHERE datname = current_database()")
        info["db_connections"] = int(cur.fetchone()["c"] or 0)
        cur.execute("SELECT COUNT(*) AS c FROM users")
        info["users_count"] = int(cur.fetchone()["c"] or 0)
        cur.close()
        info["db_ok"] = True
    except Exception as e:
        info["db_ok"] = False; info["db_error"] = str(e)[:180]
    return info


@app.route("/admin/storage")
@super_admin_required
def admin_storage():
    stats = _table_stats()
    backups = _list_backups()
    limit_h = _fmt_bytes(_AUTO_ARCHIVE_LIMIT)
    usage_pct = int(min(100, (stats["db_size"] / _AUTO_ARCHIVE_LIMIT) * 100)) if _AUTO_ARCHIVE_LIMIT > 0 else 0
    return render_template("admin_storage.html",
                           stats=stats, backups=backups,
                           limit_h=limit_h, usage_pct=usage_pct,
                           keep_days=_AUTO_ARCHIVE_KEEP_DAYS,
                           server_info=_server_info())


@app.route("/admin/storage/cleanup", methods=["POST"])
@super_admin_required
def admin_storage_cleanup():
    table = (request.form.get("table") or "").strip()
    days_raw = request.form.get("days") or "0"
    try:
        days = max(0, int(days_raw))
    except ValueError:
        days = 0
    valid = {t[0]: t for t in _STORAGE_TABLES}
    if table not in valid:
        flash("جدول غير معروف", "error")
        return redirect(url_for("admin_storage"))
    _tname, _label, date_col = valid[table]
    db = get_db(); cur = db.cursor()
    if days == 0:
        where_sql, params = "", ()
    elif date_col:
        where_sql = f"WHERE {date_col} < NOW() - INTERVAL '{days} days'"
        params = ()
    else:
        flash("الجدول ده مفيهوش عمود تاريخ يقدر يفلتر عليه", "error")
        return redirect(url_for("admin_storage"))
    # نسخة احتياطية أولاً
    fname, n = _backup_before_delete(table, where_sql, params)
    if n == 0:
        cur.close()
        flash("لا يوجد سطور مطابقة للحذف", "info")
        return redirect(url_for("admin_storage"))
    cur.execute(f"DELETE FROM {table} {where_sql}", params)
    db.commit(); cur.close()
    flash(f"تم حذف {n} سطر من ({_label}) وحفظهم في ملف: {fname}", "success")
    return redirect(url_for("admin_storage"))


@app.route("/admin/storage/download/<name>")
@super_admin_required
def admin_storage_download(name):
    from flask import send_from_directory
    # نمنع الخروج بره المجلد
    if "/" in name or "\\" in name or ".." in name:
        abort(400)
    fpath = os.path.join(_BACKUP_DIR, name)
    if not os.path.isfile(fpath):
        abort(404)
    return send_from_directory(_BACKUP_DIR, name, as_attachment=True)


@app.route("/admin/storage/delete-backup", methods=["POST"])
@super_admin_required
def admin_storage_delete_backup():
    name = (request.form.get("name") or "").strip()
    if "/" in name or "\\" in name or ".." in name or not name:
        flash("اسم ملف غير صالح", "error")
        return redirect(url_for("admin_storage"))
    fpath = os.path.join(_BACKUP_DIR, name)
    if os.path.isfile(fpath):
        try:
            os.remove(fpath)
            flash("تم حذف الملف الاحتياطي", "success")
        except Exception as e:
            flash(f"خطأ في الحذف: {e}", "error")
    return redirect(url_for("admin_storage"))


@app.route("/admin/storage/auto-archive", methods=["POST"])
@super_admin_required
def admin_storage_auto_archive():
    r = _auto_archive_if_needed()
    if r is None:
        flash("لسه المساحة تحت الحد — مفيش داعي للأرشيف", "info")
    elif r:
        flash("تم أرشفة السطور القديمة وحذفها ✓", "success")
    else:
        flash("مفيش سطور قديمة تتأرشف", "info")
    return redirect(url_for("admin_storage"))
