"""
تطبيق فريق تحصين الكتاكيت
Flask + SQLite — يعمل من المتصفح على الموبايل والكمبيوتر
تشغيل:
    pip install -r requirements.txt
    python app.py
الافتراضي: مسؤول admin / كلمة السر admin123
"""
import os
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, g, redirect, render_template, request, session,
                   url_for, flash, jsonify)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-please-very-secret")


# ---------- قاعدة البيانات ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'worker',  -- 'admin' or 'worker'
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,  -- YYYY-MM-DD
            checked_in_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, day),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS vaccinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            count INTEGER NOT NULL CHECK(count >= 0),
            note TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    db.commit()
    # admin افتراضي
    cur = db.execute("SELECT 1 FROM users WHERE username='admin'")
    if not cur.fetchone():
        db.execute(
            "INSERT INTO users(username, full_name, password_hash, role) VALUES(?,?,?,?)",
            ("admin", "المسؤول", generate_password_hash("admin123"), "admin"),
        )
        db.commit()
    db.close()


# ---------- مساعدات ----------
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


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
        row = get_db().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
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
            try:
                get_db().execute(
                    "INSERT INTO users(username, full_name, password_hash, role) VALUES(?,?,?,'worker')",
                    (username, full_name, generate_password_hash(password)),
                )
                get_db().commit()
                flash("تم إنشاء الحساب، سجّل دخولك", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("اسم المستخدم موجود بالفعل", "error")
    return render_template("register.html")


@app.route("/dashboard")
@login_required
def dashboard():
    u = current_user()
    db = get_db()
    today = date.today().isoformat()
    checked_in = db.execute(
        "SELECT 1 FROM attendance WHERE user_id=? AND day=?", (u["id"], today)
    ).fetchone() is not None
    my_total = db.execute(
        "SELECT COALESCE(SUM(count),0) AS s FROM vaccinations WHERE user_id=? AND day=?",
        (u["id"], today),
    ).fetchone()["s"]
    team_total = db.execute(
        "SELECT COALESCE(SUM(count),0) AS s FROM vaccinations WHERE day=?", (today,)
    ).fetchone()["s"]
    present_count = db.execute(
        "SELECT COUNT(*) AS c FROM attendance WHERE day=?", (today,)
    ).fetchone()["c"]
    recent = db.execute(
        """SELECT v.*, u.full_name FROM vaccinations v
           JOIN users u ON u.id=v.user_id
           WHERE v.user_id=? ORDER BY v.created_at DESC LIMIT 5""",
        (u["id"],),
    ).fetchall()
    return render_template(
        "dashboard.html",
        checked_in=checked_in,
        my_total=my_total,
        team_total=team_total,
        present_count=present_count,
        recent=recent,
    )


@app.route("/check-in", methods=["POST"])
@login_required
def check_in():
    u = current_user()
    today = date.today().isoformat()
    try:
        get_db().execute(
            "INSERT INTO attendance(user_id, day) VALUES(?,?)", (u["id"], today)
        )
        get_db().commit()
        flash("تم تسجيل حضورك اليوم ✓", "success")
    except sqlite3.IntegrityError:
        flash("أنت مسجَّل حضورك بالفعل اليوم", "info")
    return redirect(url_for("dashboard"))


@app.route("/add-vaccination", methods=["POST"])
@login_required
def add_vaccination():
    u = current_user()
    try:
        count = int(request.form.get("count", "0"))
        if count <= 0:
            raise ValueError
    except ValueError:
        flash("أدخل عدد صحيح أكبر من صفر", "error")
        return redirect(url_for("dashboard"))
    note = request.form.get("note", "").strip() or None
    today = date.today().isoformat()
    db = get_db()
    db.execute(
        "INSERT INTO vaccinations(user_id, day, count, note) VALUES(?,?,?,?)",
        (u["id"], today, count, note),
    )
    # تسجيل الحضور تلقائياً
    db.execute("INSERT OR IGNORE INTO attendance(user_id, day) VALUES(?,?)", (u["id"], today))
    db.commit()
    flash(f"تم تسجيل {count} كتكوت ✓", "success")
    return redirect(url_for("dashboard"))


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

    workers = db.execute(
        """
        SELECT u.id, u.full_name, u.username, u.role,
               EXISTS(SELECT 1 FROM attendance a WHERE a.user_id=u.id AND a.day=?) AS present,
               COALESCE((SELECT SUM(count) FROM vaccinations v WHERE v.user_id=u.id AND v.day=?),0) AS total
        FROM users u ORDER BY u.role='admin' DESC, u.full_name
        """,
        (day_s, day_s),
    ).fetchall()

    day_total = db.execute(
        "SELECT COALESCE(SUM(count),0) AS s FROM vaccinations WHERE day=?", (day_s,)
    ).fetchone()["s"]
    present_count = db.execute(
        "SELECT COUNT(*) AS c FROM attendance WHERE day=?", (day_s,)
    ).fetchone()["c"]
    entries = db.execute(
        """SELECT v.*, u.full_name FROM vaccinations v
           JOIN users u ON u.id=v.user_id WHERE v.day=?
           ORDER BY v.created_at DESC""",
        (day_s,),
    ).fetchall()

    # شريط آخر 14 يوم
    days_bar = []
    for i in range(13, -1, -1):
        d = (day - timedelta(days=i)).isoformat()
        s = db.execute(
            "SELECT COALESCE(SUM(count),0) AS s FROM vaccinations WHERE day=?", (d,)
        ).fetchone()["s"]
        days_bar.append({"day": d, "total": s, "active": d == day_s})

    return render_template(
        "admin.html",
        workers=workers, entries=entries,
        day=day_s, prev_day=prev_day, next_day=next_day,
        day_total=day_total, present_count=present_count,
        days_bar=days_bar,
    )


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
    db.execute(
        "INSERT INTO vaccinations(user_id, day, count, note) VALUES(?,?,?,?)",
        (user_id, day.isoformat(), count, note),
    )
    db.execute(
        "INSERT OR IGNORE INTO attendance(user_id, day) VALUES(?,?)",
        (user_id, day.isoformat()),
    )
    db.commit()
    flash("تمت الإضافة ✓", "success")
    return redirect(url_for("admin_panel", day=day.isoformat()))


@app.route("/admin/mark-attendance", methods=["POST"])
@admin_required
def admin_mark_attendance():
    day = _parse_day(request.form.get("day")).isoformat()
    user_id = int(request.form.get("user_id"))
    db = get_db()
    exists = db.execute(
        "SELECT 1 FROM attendance WHERE user_id=? AND day=?", (user_id, day)
    ).fetchone()
    if exists:
        db.execute("DELETE FROM attendance WHERE user_id=? AND day=?", (user_id, day))
    else:
        db.execute("INSERT INTO attendance(user_id, day) VALUES(?,?)", (user_id, day))
    db.commit()
    return redirect(url_for("admin_panel", day=day))


@app.route("/admin/delete-entry/<int:entry_id>", methods=["POST"])
@admin_required
def admin_delete_entry(entry_id):
    day = _parse_day(request.form.get("day")).isoformat()
    get_db().execute("DELETE FROM vaccinations WHERE id=?", (entry_id,))
    get_db().commit()
    flash("تم الحذف", "info")
    return redirect(url_for("admin_panel", day=day))


@app.route("/admin/users", methods=["GET", "POST"])
@admin_required
def admin_users():
    db = get_db()
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
                    db.execute(
                        "INSERT INTO users(username, full_name, password_hash, role) VALUES(?,?,?,?)",
                        (username, full_name, generate_password_hash(password), role),
                    )
                    db.commit()
                    flash("تم إضافة المستخدم ✓", "success")
                except sqlite3.IntegrityError:
                    flash("اسم المستخدم موجود", "error")
        elif action == "delete":
            uid = int(request.form.get("user_id"))
            if uid != current_user()["id"]:
                db.execute("DELETE FROM users WHERE id=?", (uid,))
                db.commit()
                flash("تم حذف المستخدم", "info")
        elif action == "reset_pw":
            uid = int(request.form.get("user_id"))
            new_pw = request.form.get("password", "")
            if new_pw:
                db.execute("UPDATE users SET password_hash=? WHERE id=?",
                           (generate_password_hash(new_pw), uid))
                db.commit()
                flash("تم تغيير كلمة السر", "success")
        return redirect(url_for("admin_users"))
    users = db.execute("SELECT * FROM users ORDER BY role='admin' DESC, full_name").fetchall()
    return render_template("admin_users.html", users=users)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
