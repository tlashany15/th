"""
تطبيق فريق تحصين الكتاكيت
Flask + PostgreSQL — يعمل على Vercel
"""
import os
import base64
import psycopg2
import psycopg2.extras
from datetime import date, datetime, timedelta, timezone
from functools import wraps

from flask import (Flask, g, redirect, render_template, request, session,
                   url_for, flash, jsonify)
from werkzeug.security import check_password_hash, generate_password_hash

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

        ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar TEXT;
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
            CHECK (id = 1)
        );
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
        CREATE TABLE IF NOT EXISTS group_reads (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            last_read_id INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    cur.execute("SELECT 1 FROM users WHERE username='admin'")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users(username, full_name, password_hash, role) VALUES(%s,%s,%s,%s)",
            ("admin", "المسؤول", generate_password_hash("admin123"), "admin"),
        )
    conn.commit()
    cur.close()
    conn.close()


# ---------- مساعدات ----------
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (uid,))
    row = cur.fetchone()
    cur.close()
    return row


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


def is_day_closed(day_s):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT total_count FROM day_closures WHERE day=%s", (day_s,))
    _row = cur.fetchone()
    closed = _row is not None
    cur.close()
    return closed


def get_day_closure_total(day_s):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT total_count FROM day_closures WHERE day=%s", (day_s,))
    _row = cur.fetchone()
    cur.close()
    return _row["total_count"] if _row else None


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


@app.context_processor
def inject_user():
    return {"current_user": current_user(), "today": date.today().isoformat()}


# ---------- مسارات أساسية ----------
@app.route("/")
def index():
    return redirect(url_for("splash"))


@app.route("/welcome")
def splash():
    next_url = url_for("dashboard") if session.get("user_id") else url_for("login")
    return render_template("splash.html", next_url=next_url)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        row = cur.fetchone()
        cur.close()
        if row and check_password_hash(row["password_hash"], password):
            session["user_id"] = row["id"]
            return redirect(url_for("dashboard"))
        flash("اسم المستخدم أو كلمة السر غير صحيحة", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        if not (username and full_name and password):
            flash("كل الحقول مطلوبة", "error")
        else:
            db = get_db()
            cur = db.cursor()
            try:
                cur.execute(
                    "INSERT INTO users(username, full_name, password_hash, role) VALUES(%s,%s,%s,'worker')",
                    (username, full_name, generate_password_hash(password)),
                )
                db.commit()
                flash("تم إنشاء الحساب، سجّل دخولك", "success")
                return redirect(url_for("login"))
            except psycopg2.IntegrityError:
                db.rollback()
                flash("اسم المستخدم موجود بالفعل", "error")
            finally:
                cur.close()
    return render_template("register.html")


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

    cur.execute("SELECT 1 FROM attendance WHERE user_id=%s AND day=%s", (u["id"], today))
    checked_in = cur.fetchone() is not None

    cur.execute("SELECT COALESCE(SUM(count),0) AS s FROM vaccinations WHERE user_id=%s AND day=%s",
                (u["id"], today))
    my_total = cur.fetchone()["s"]

    if closed:
        team_total = closure_total
    else:
        cur.execute("SELECT COALESCE(SUM(count),0) AS s FROM vaccinations WHERE day=%s", (today,))
        team_total = cur.fetchone()["s"]

    cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE day=%s", (today,))
    present_count = cur.fetchone()["c"]

    present_list = []
    if closed:
        cur.execute("""
            SELECT u.id, u.full_name, u.avatar
            FROM attendance a JOIN users u ON u.id=a.user_id
            WHERE a.day=%s ORDER BY u.full_name
        """, (today,))
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
    try:
        cur.execute("INSERT INTO attendance(user_id, day) VALUES(%s,%s)", (u["id"], today))
        db.commit()
        flash("تم تسجيل حضورك اليوم 💉", "success")
    except psycopg2.IntegrityError:
        db.rollback()
        flash("أنت مسجَّل حضورك بالفعل اليوم", "info")
    finally:
        cur.close()
    return redirect(url_for("dashboard"))


@app.route("/history")
@login_required
def history():
    import calendar
    u = current_user()
    is_admin = (u and u["role"] == "admin")
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT c.day, c.total_count,
               COALESCE(ARRAY_AGG(u.full_name ORDER BY u.full_name)
                        FILTER (WHERE u.full_name IS NOT NULL), '{}') AS names
        FROM day_closures c
        LEFT JOIN attendance a ON a.day = c.day
        LEFT JOIN users u ON u.id = a.user_id
        GROUP BY c.day, c.total_count
    """)
    by_day = {r["day"]: {"total": r["total_count"], "names": list(r["names"] or [])}
              for r in cur.fetchall()}
    cur.close()

    today = date.today()
    if is_admin:
        months = set((d.year, d.month) for d in by_day.keys())
        months.add((today.year, today.month))
    else:
        # العمال يشوفوا الفترة الحالية بس (نصف الشهر الجاري)
        months = {(today.year, today.month)}
    current_half = 1 if today.day <= 15 else 2
    periods = []
    AR_DAYS = ["الإثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"]
    AR_MONTHS = ["يناير","فبراير","مارس","أبريل","مايو","يونيو",
                 "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]
    for (y, m) in sorted(months, reverse=True):
        last_day = calendar.monthrange(y, m)[1]
        for half, (start, end) in enumerate([(1, 15), (16, last_day)], start=1):
            # للعمال: لو الشهر الحالي، أظهر النصف الحالي بس
            if (not is_admin) and (y, m) == (today.year, today.month) and half != current_half:
                continue
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
                    "names": rec["names"] if rec else [],
                    "has_data": rec is not None,
                })
            periods.append({
                "label": f"{AR_MONTHS[m-1]} {y} — {'النصف الأول (1-15)' if half==1 else f'النصف الثاني (16-{last_day})'}",
                "days": days_list,
            })
    return render_template("history.html", periods=periods)


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
        SELECT u.id, u.full_name, u.username, u.role,
               EXISTS(SELECT 1 FROM attendance a WHERE a.user_id=u.id AND a.day=%s) AS present,
               COALESCE((SELECT SUM(count) FROM vaccinations v WHERE v.user_id=u.id AND v.day=%s),0) AS total
        FROM users u ORDER BY (u.role='admin') DESC, u.full_name
    """, (day_s, day_s))
    workers = cur.fetchall()

    cur.execute("SELECT COALESCE(SUM(count),0) AS s FROM vaccinations WHERE day=%s", (day_s,))
    day_total = cur.fetchone()["s"]

    cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE day=%s", (day_s,))
    present_count = cur.fetchone()["c"]

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

    cur.execute("SELECT total_count FROM day_closures WHERE day=%s", (day_s,))
    _row = cur.fetchone()
    closed = _row is not None
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
    )


@app.route("/admin/close-day", methods=["POST"])
@admin_required
def admin_close_day():
    u = current_user()
    day = _parse_day(request.form.get("day")).isoformat()
    try:
        total = int(request.form.get("total_count", "0"))
        if total < 0:
            raise ValueError
    except ValueError:
        flash("ادخل عدد إجمالي صحيح", "error")
        return redirect(url_for("admin_panel", day=day))
    db = get_db()
    cur = db.cursor()
    cur.execute("ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS total_count INTEGER NOT NULL DEFAULT 0")
    cur.execute(
        """INSERT INTO day_closures(day, closed_by, total_count)
           VALUES(%s,%s,%s)
           ON CONFLICT (day) DO UPDATE SET total_count = EXCLUDED.total_count, closed_by = EXCLUDED.closed_by""",
        (day, u["id"], total),
    )
    db.commit()
    cur.close()
    # ==== ملخص الفترة (نصف شهر) — تلقائي في الجروب ====
    try:
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
                    "📊 ملخص " + half_lbl + " من " + AR_MONTHS[m-1] + f" {y}\n"
                    + f"• الإجمالي: {period_total:,} كتكوت\n"
                    + f"• عدد أيام العمل: {days_closed}\n"
                    + f"• الفترة: {start_d} → {end_d}"
                )
                cur.execute("""INSERT INTO group_messages(sender_id, kind, body, pinned)
                               VALUES (%s, 'system', %s, TRUE)""", (u["id"], body))
                # نلغي تثبيت أى ملخّص فتره قديم
                cur.execute("""UPDATE group_messages SET pinned=FALSE
                               WHERE pinned=TRUE AND kind='system' AND id <> (SELECT MAX(id) FROM group_messages WHERE kind='system')""")
                cur.execute("INSERT INTO period_summaries(year, month, half, total) VALUES(%s,%s,%s,%s)",
                            (y, m, half, period_total))
                db.commit()
                flash(f"تم نشر ملخص {half_lbl} في الجروب تلقائيًا 📊", "success")
    except Exception as _e:
        print("period summary error:", _e)
    flash("تم إغلاق اليوم — العمال هيشوفوا الإجمالي الآن", "success")
    return redirect(url_for("admin_panel", day=day))


@app.route("/admin/reopen-day", methods=["POST"])
@admin_required
def admin_reopen_day():
    day = _parse_day(request.form.get("day")).isoformat()
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM day_closures WHERE day=%s", (day,))
    db.commit()
    cur.close()
    flash("تم إعادة فتح اليوم", "info")
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
    flash("تمت الإضافة 💉", "success")
    return redirect(url_for("admin_panel", day=day.isoformat()))


@app.route("/admin/mark-attendance", methods=["POST"])
@admin_required
def admin_mark_attendance():
    day = _parse_day(request.form.get("day")).isoformat()
    user_id = int(request.form.get("user_id"))
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT 1 FROM attendance WHERE user_id=%s AND day=%s", (user_id, day))
    exists = cur.fetchone()
    if exists:
        cur.execute("DELETE FROM attendance WHERE user_id=%s AND day=%s", (user_id, day))
    else:
        cur.execute("INSERT INTO attendance(user_id, day) VALUES(%s,%s)", (user_id, day))
    db.commit()
    cur.close()
    return redirect(url_for("admin_panel", day=day))


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
    day = request.form.get("day") or (date.today() + timedelta(days=1)).isoformat()
    ids = request.form.getlist("user_ids")
    if not ids:
        flash("اختر عامل واحد على الأقل", "error")
        return redirect(url_for("admin_panel"))
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT full_name FROM users WHERE id = ANY(%s) ORDER BY full_name",
                ([int(x) for x in ids],))
    names = [r["full_name"] for r in cur.fetchall()]
    # نلغي تثبيت أي إعلان حضور سابق
    cur.execute("UPDATE group_messages SET pinned=FALSE WHERE pinned=TRUE AND kind='attendance'")
    body = "📋 حضور يوم " + day + "\n• " + "\n• ".join(names)
    cur.execute("""INSERT INTO group_messages(sender_id, kind, body, pinned)
                   VALUES (%s, 'attendance', %s, TRUE)""", (u["id"], body))
    db.commit()
    cur.close()
    flash("تم نشر قائمة حضور الغد في الدردشة الجماعية 📌", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/users", methods=["GET", "POST"])
@admin_required
def admin_users():
    db = get_db()
    cur = db.cursor()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            username = request.form.get("username", "").strip()
            full_name = request.form.get("full_name", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "worker")
            if not (username and full_name and password):
                flash("كل الحقول مطلوبة", "error")
            else:
                try:
                    cur.execute(
                        "INSERT INTO users(username, full_name, password_hash, role) VALUES(%s,%s,%s,%s)",
                        (username, full_name, generate_password_hash(password), role),
                    )
                    db.commit()
                    flash("تم إضافة المستخدم 💉", "success")
                except psycopg2.IntegrityError:
                    db.rollback()
                    flash("اسم المستخدم موجود", "error")
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
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COALESCE(SUM(count),0) AS s FROM vaccinations WHERE day=%s", (day_s,))
    day_total = cur.fetchone()["s"]
    cur.execute("SELECT total_count FROM day_closures WHERE day=%s", (day_s,))
    _row = cur.fetchone()
    closed = _row is not None
    if closed:
        day_total = _row["total_count"]
    cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE day=%s", (day_s,))
    present_count = cur.fetchone()["c"]
    cur.close()
    return render_template("admin_close_day.html",
                           day=day_s, day_total=day_total,
                           present_count=present_count, day_closed=closed)


# ---- صفحة مستقلة لتحضير عمال بكره ----
@app.route("/admin/tomorrow-page")
@admin_required
def admin_tomorrow_page():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, full_name FROM users WHERE role='worker' ORDER BY full_name")
    all_workers = cur.fetchall()
    cur.close()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    return render_template("admin_tomorrow.html",
                           all_workers=all_workers, tomorrow=tomorrow)


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
        return "📷 صورة"
    if m["kind"] == "audio":
        return "🎤 رسالة صوتية"
    if m["kind"] == "attendance":
        return "📋 قائمة حضور"
    if m["kind"] == "system":
        return (m.get("body") or "")[:60]
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

    group = {
        "name": gs["name"],
        "avatar": gs["avatar"],
        "last_text": _msg_preview(g_last) if g_last else "ابدأ الكلام مع الفريق",
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
        SELECT id, sender_id, receiver_id, kind, body, created_at, read_at
        FROM chat_messages
        WHERE ((sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s))
          AND id > %s
        ORDER BY id ASC LIMIT 200
    """, (u["id"], other_id, other_id, u["id"], after))
    rows = cur.fetchall()
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
    cur.close()
    msgs = []
    for r in rows:
        msgs.append({
            "id": r["id"],
            "sender_id": r["sender_id"],
            "kind": r["kind"],
            "body": r["body"],
            "created_at": _iso_utc(r["created_at"]),
            "mine": r["sender_id"] == u["id"],
            "read": r["read_at"] is not None,
        })
    return jsonify({
        "messages": msgs,
        "read_ids": read_ids,
        "other_online": _is_online(other_row["last_seen"]) if other_row else False,
        "other_last_seen": _iso_utc(other_row["last_seen"]) if other_row else None,
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

    db = get_db()
    cur = db.cursor()
    cur.execute("""INSERT INTO chat_messages(sender_id, receiver_id, kind, body)
                   VALUES (%s, %s, %s, %s) RETURNING id, created_at""",
                (u["id"], other_id, kind, body))
    row = cur.fetchone()
    db.commit()
    cur.close()
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
    return render_template("group.html", group={
        "name": gs["name"], "avatar": gs["avatar"], "members": members
    }, is_admin=is_admin)


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
               u.full_name AS sender_name, u.avatar AS sender_avatar, u.role AS sender_role
        FROM group_messages m
        LEFT JOIN users u ON u.id = m.sender_id
        WHERE m.id > %s
        ORDER BY m.id ASC LIMIT 300
    """, (after,))
    rows = cur.fetchall()
    # المثبّت
    cur.execute("""SELECT id, body, kind FROM group_messages
                   WHERE pinned=TRUE AND deleted=FALSE
                   ORDER BY created_at DESC LIMIT 1""")
    pinned = cur.fetchone()
    # حدّث آخر قراءة لأكبر id
    if rows:
        cur.execute("""INSERT INTO group_reads(user_id, last_read_id) VALUES(%s,%s)
                       ON CONFLICT (user_id) DO UPDATE SET last_read_id=GREATEST(group_reads.last_read_id, EXCLUDED.last_read_id), updated_at=NOW()""",
                    (u["id"], rows[-1]["id"]))
        db.commit()
    cur.close()
    msgs = []
    for r in rows:
        msgs.append({
            "id": r["id"],
            "sender_id": r["sender_id"],
            "sender_name": r["sender_name"] or "محذوف",
            "sender_avatar": r["sender_avatar"],
            "sender_role": r["sender_role"] or "",
            "kind": r["kind"],
            "body": r["body"],
            "pinned": r["pinned"],
            "deleted": r["deleted"],
            "created_at": _iso_utc(r["created_at"]),
            "mine": r["sender_id"] == u["id"],
        })
    return jsonify({
        "messages": msgs,
        "pinned": ({"id": pinned["id"], "body": pinned["body"], "kind": pinned["kind"]} if pinned else None),
    })


@app.route("/group/send", methods=["POST"])
@login_required
def group_send():
    u = current_user()
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

    db = get_db()
    cur = db.cursor()
    cur.execute("""INSERT INTO group_messages(sender_id, kind, body)
                   VALUES (%s, %s, %s) RETURNING id, created_at""",
                (u["id"], kind, body))
    row = cur.fetchone()
    db.commit()
    cur.close()
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
    if len(data) > 3 * 1024 * 1024:
        flash("الصورة كبيرة (الحد 3 ميجا)", "error")
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


@app.route("/group/members")
@login_required
def group_members_api():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, full_name, username, avatar, role, last_seen FROM users ORDER BY full_name")
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
        })
    members.sort(key=lambda m: (not m["online"], m["full_name"]))
    online_count = sum(1 for m in members if m["online"])
    return jsonify({"members": members, "online": online_count, "total": len(members)})


@app.route("/me/avatar", methods=["POST"])
@login_required
def update_avatar():
    u = current_user()
    f = request.files.get("file")
    if not f:
        flash("اختر صورة", "error")
        return redirect(request.referrer or url_for("chats_list"))
    data = f.read()
    if len(data) > 2 * 1024 * 1024:
        flash("الصورة كبيرة (الحد 2 ميجا)", "error")
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
        return "تم إنشاء قاعدة البيانات 💉", 200
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
    return ("حدث خطأ غير متوقع. حاول تاني.", 500)

