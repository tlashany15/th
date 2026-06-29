"""
تطبيق فريق تحصين الكتاكيت
Flask + PostgreSQL — يعمل على Vercel
"""
import os
import psycopg2
import psycopg2.extras
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, g, redirect, render_template, request, session,
                   url_for, flash, jsonify)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-please-very-secret")

DATABASE_URL = os.environ.get("DATABASE_URL", "")


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
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            day DATE NOT NULL,
            checked_in_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, day)
        );
        CREATE TABLE IF NOT EXISTS vaccinations (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            day DATE NOT NULL,
            count INTEGER NOT NULL CHECK(count >= 0),
            note TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS day_closures (
            day DATE PRIMARY KEY,
            closed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            closed_at TIMESTAMP NOT NULL DEFAULT NOW(),
            total_count INTEGER NOT NULL DEFAULT 0
        );
        ALTER TABLE day_closures ADD COLUMN IF NOT EXISTS total_count INTEGER NOT NULL DEFAULT 0;
    """)
    # admin افتراضي
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


def is_day_closed(day_s):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT 1 FROM day_closures WHERE day=%s", (day_s,))
    closed = cur.fetchone() is not None
    cur.close()
    return closed


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


# ---------- مسارات ----------
@app.route("/")
def index():
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))


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
    # المسؤول له صفحته الخاصة فقط
    if u["role"] == "admin":
        return redirect(url_for("admin_panel"))

    db = get_db()
    cur = db.cursor()
    today = date.today().isoformat()
    closed = is_day_closed(today)

    cur.execute("SELECT 1 FROM attendance WHERE user_id=%s AND day=%s", (u["id"], today))
    checked_in = cur.fetchone() is not None

    cur.execute("SELECT COALESCE(SUM(count),0) AS s FROM vaccinations WHERE user_id=%s AND day=%s",
                (u["id"], today))
    my_total = cur.fetchone()["s"]

    cur.execute("SELECT COALESCE(SUM(count),0) AS s FROM vaccinations WHERE day=%s", (today,))
    team_total = cur.fetchone()["s"]

    cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE day=%s", (today,))
    present_count = cur.fetchone()["c"]

    # في حالة إغلاق اليوم نعرض ملخص: الحاضرون + كل عامل وعدده
    present_list = []
    if closed:
        cur.execute("""
            SELECT u.full_name,
                   COALESCE((SELECT SUM(count) FROM vaccinations v
                             WHERE v.user_id=u.id AND v.day=%s),0) AS total
            FROM attendance a JOIN users u ON u.id=a.user_id
            WHERE a.day=%s
            ORDER BY total DESC, u.full_name
        """, (today, today))
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
        flash("تم تسجيل حضورك اليوم ✓", "success")
    except psycopg2.IntegrityError:
        db.rollback()
        flash("أنت مسجَّل حضورك بالفعل اليوم", "info")
    finally:
        cur.close()
    return redirect(url_for("dashboard"))


@app.route("/history")
@login_required
def history():
    """سجل التحصين مقسوم نصفين شهريين (1-15 و 16-آخر الشهر)، الجمعة إجازة"""
    import calendar
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

    # determine months to show: any month that has a closure, plus current month
    months = set((d.year, d.month) for d in by_day.keys())
    today = date.today()
    months.add((today.year, today.month))
    periods = []  # list of {label, days: [{date, weekday_name, holiday, total, names, has_data}]}
    AR_DAYS = ["الإثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"]
    AR_MONTHS = ["يناير","فبراير","مارس","أبريل","مايو","يونيو",
                 "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]
    for (y, m) in sorted(months, reverse=True):
        last_day = calendar.monthrange(y, m)[1]
        for half, (start, end) in enumerate([(1, 15), (16, last_day)], start=1):
            days_list = []
            for dnum in range(start, end + 1):
                d = date(y, m, dnum)
                wd = d.weekday()  # Mon=0 .. Sun=6 ; Friday=4
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

    cur.execute("SELECT 1 FROM day_closures WHERE day=%s", (day_s,))
    closed = cur.fetchone() is not None

    cur.close()
    return render_template(
        "admin.html",
        workers=workers, entries=entries,
        day=day_s, prev_day=prev_day, next_day=next_day,
        day_total=day_total, present_count=present_count,
        days_bar=days_bar, day_closed=closed,
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
    cur.execute(
        """INSERT INTO day_closures(day, closed_by, total_count)
           VALUES(%s,%s,%s)
           ON CONFLICT (day) DO UPDATE SET total_count = EXCLUDED.total_count, closed_by = EXCLUDED.closed_by""",
        (day, u["id"], total),
    )
    db.commit()
    cur.close()
    flash("تم إغلاق اليوم — العمال هيشوفوا الملخص الآن", "success")
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
    flash("تمت الإضافة ✓", "success")
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
                    flash("تم إضافة المستخدم ✓", "success")
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


@app.route("/init-db")
def init_db_route():
    """Route مؤقت لإنشاء الجداول — احذفه بعد أول تشغيل"""
    secret = request.args.get("secret", "")
    if secret != os.environ.get("INIT_SECRET", ""):
        return "غير مسموح", 403
    try:
        init_db()
        return "تم إنشاء قاعدة البيانات ✓", 200
    except Exception as e:
        return f"خطأ: {e}", 500


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
