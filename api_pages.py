# -*- coding: utf-8 -*-
"""
api_pages.py — مسارات JSON للصفحات الإضافية في تطبيق الأندرويد
================================================================
بيكمّل api_v1.py (نفس نظام التوكن) ومبيعدّلش على أي مسار في الموقع.
كل منطق الصفحات هنا منسوخ حرفياً من app.py (الإشعارات / ملاحظاتي / إرسال إشعار / حسابي).

التفعيل: في آخر app.py، بعد سطري api_v1، ضيف:
    import api_pages
    api_pages.init_pages(app, globals())

وفي vercel.json ضيف "api_pages.py" في includeFiles.
"""
import base64
import json
from datetime import date, datetime
from decimal import Decimal

from flask import request, make_response
from werkzeug.security import check_password_hash, generate_password_hash

API = "/api/v1/"


def _ser(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o) if o % 1 else int(o)
    return str(o)


def init_pages(app, ns):
    def _json(data, status=200):
        resp = make_response(json.dumps(data, default=_ser, ensure_ascii=False), status)
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
        return resp

    def _err(msg, status=400):
        return _json({"ok": False, "error": msg}, status)

    def _is_admin(u):
        return bool(u and (u["role"] == "admin" or ns["_is_idara"](u)))

    def _body():
        return request.get_json(silent=True) or {}

    def _int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    # ───────────────────────── الإشعارات ─────────────────────────
    @app.route(API + "notifications")
    def api_notifications():
        u = ns["current_user"]()
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("""SELECT id, title, body, url, type, created_at, read_at
                       FROM notifications WHERE user_id=%s
                       ORDER BY id DESC LIMIT 200""", (u["id"],))
        rows = cur.fetchall()
        # زي الموقع بالظبط: فتح الصفحة = قراءة الكل (بعد ما نرجّع حالة «غير مقروء»)
        cur.execute("UPDATE notifications SET read_at=NOW() WHERE user_id=%s AND read_at IS NULL", (u["id"],))
        db.commit(); cur.close()
        items = [{
            "id": r["id"], "title": r["title"], "body": r["body"], "url": r["url"],
            "type": r["type"], "created_at": ns["_iso_utc"](r["created_at"]),
            "unread": r["read_at"] is None,
        } for r in rows]
        return _json({"ok": True, "items": items})

    @app.route(API + "notifications/unread-count")
    def api_notifications_unread_count():
        u = ns["current_user"]()
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM notifications WHERE user_id=%s AND read_at IS NULL", (u["id"],))
        c = cur.fetchone()["c"]
        cur.close()
        return _json({"ok": True, "count": int(c)})

    @app.route(API + "notifications/delete", methods=["POST"])
    def api_notification_delete():
        u = ns["current_user"]()
        nid = _int(_body().get("id"))
        if not nid:
            return _err("مدخلات غير صالحة")
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("DELETE FROM notifications WHERE id=%s AND user_id=%s", (nid, u["id"]))
        db.commit(); cur.close()
        return _json({"ok": True})

    @app.route(API + "notifications/delete-all", methods=["POST"])
    def api_notifications_delete_all():
        u = ns["current_user"]()
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("DELETE FROM notifications WHERE user_id=%s", (u["id"],))
        db.commit(); cur.close()
        return _json({"ok": True})

    # ───────────────────────── ملاحظاتي (مسؤول) ─────────────────────────
    def _note_colors():
        return list(ns.get("NOTE_COLORS") or ["gold", "green", "blue", "pink", "purple", "slate"])

    @app.route(API + "notes")
    def api_notes():
        if not _is_admin(ns["current_user"]()):
            return _err("للمسؤول فقط", 403)
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("""SELECT id, title, body, color, pinned, created_at, updated_at
                       FROM admin_notes ORDER BY pinned DESC, updated_at DESC""")
        rows = cur.fetchall(); cur.close()
        notes = [{
            "id": r["id"], "title": r["title"] or "", "body": r["body"], "color": r["color"],
            "pinned": bool(r["pinned"]),
            "updated_at": r["updated_at"].strftime("%Y-%m-%d %H:%M") if r["updated_at"] else "",
        } for r in rows]
        return _json({"ok": True, "notes": notes, "colors": _note_colors()})

    @app.route(API + "notes/save", methods=["POST"])
    def api_notes_save():
        u = ns["current_user"]()
        if not _is_admin(u):
            return _err("للمسؤول فقط", 403)
        b = _body()
        nid = _int(b.get("id"))
        title = (str(b.get("title") or "")).strip()[:120] or None
        body = (str(b.get("body") or "")).strip()
        color = (str(b.get("color") or "gold")).strip()
        if color not in _note_colors():
            color = "gold"
        if not body:
            return _err("اكتب محتوى الملاحظة")
        db = ns["get_db"](); cur = db.cursor()
        if nid:
            cur.execute("""UPDATE admin_notes SET title=%s, body=%s, color=%s, updated_at=NOW()
                           WHERE id=%s""", (title, body, color, nid))
            msg = "تم تعديل الملاحظة"
        else:
            cur.execute("""INSERT INTO admin_notes(admin_id, title, body, color)
                           VALUES(%s,%s,%s,%s)""", (u["id"], title, body, color))
            msg = "تم حفظ الملاحظة"
        db.commit(); cur.close()
        return _json({"ok": True, "message": msg})

    @app.route(API + "notes/pin", methods=["POST"])
    def api_notes_pin():
        if not _is_admin(ns["current_user"]()):
            return _err("للمسؤول فقط", 403)
        nid = _int(_body().get("id"))
        if not nid:
            return _err("مدخلات غير صالحة")
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("UPDATE admin_notes SET pinned = NOT pinned, updated_at=NOW() WHERE id=%s", (nid,))
        db.commit(); cur.close()
        return _json({"ok": True})

    @app.route(API + "notes/delete", methods=["POST"])
    def api_notes_delete():
        if not _is_admin(ns["current_user"]()):
            return _err("للمسؤول فقط", 403)
        nid = _int(_body().get("id"))
        if not nid:
            return _err("مدخلات غير صالحة")
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("DELETE FROM admin_notes WHERE id=%s", (nid,))
        db.commit(); cur.close()
        return _json({"ok": True, "message": "تم حذف الملاحظة"})

    # ───────────────────────── إرسال إشعار (مسؤول) ─────────────────────────
    @app.route(API + "admin/notify-users")
    def api_notify_users():
        if not _is_admin(ns["current_user"]()):
            return _err("للمسؤول فقط", 403)
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("SELECT id, full_name, role FROM users WHERE role<>'system' "
                    "ORDER BY (role='admin') DESC, full_name")
        users = [{"id": r["id"], "full_name": r["full_name"], "role": r["role"]} for r in cur.fetchall()]
        cur.close()
        return _json({"ok": True, "users": users})

    @app.route(API + "admin/notify", methods=["POST"])
    def api_admin_notify():
        if not _is_admin(ns["current_user"]()):
            return _err("للمسؤول فقط", 403)
        b = _body()
        title = (str(b.get("title") or "")).strip()
        text = (str(b.get("body") or "")).strip()
        target = str(b.get("target") or "all")
        if not title:
            return _err("لازم تكتب عنوان للإشعار")
        db = ns["get_db"](); cur = db.cursor()
        if target in ("all", "workers", "admins"):
            if target == "workers":
                cur.execute("SELECT id FROM users WHERE role='worker'")
            elif target == "admins":
                cur.execute("SELECT id FROM users WHERE role='admin'")
            else:
                cur.execute("SELECT id FROM users WHERE role<>'system'")
            user_ids = [r["id"] for r in cur.fetchall()]
            cur.close()
            if not user_ids:
                return _err("مفيش مستخدمين في القسم ده")
        else:
            cur.close()
            user_ids = [_int(x) for x in (b.get("user_ids") or []) if _int(x)]
            if not user_ids:
                return _err("اختر عامل واحد على الأقل")
        ns["_notify_users"](user_ids, title, text, url="", type_="admin_broadcast")
        return _json({"ok": True, "message": "تم إرسال الإشعار لـ %d مستخدم" % len(user_ids)})

    # ───────────────────────── حسابي ─────────────────────────
    @app.route(API + "profile")
    def api_profile():
        u = ns["current_user"]()
        return _json({"ok": True, "me": {
            "id": u["id"], "full_name": u["full_name"], "username": u["username"],
            "role": u["role"], "avatar": u.get("avatar") if hasattr(u, "get") else u["avatar"],
            "is_admin": _is_admin(u),
        }})

    @app.route(API + "profile/update", methods=["POST"])
    def api_profile_update():
        u = ns["current_user"]()
        # زي الموقع: تغيير الاسم والـ ID للمسؤول فقط
        if not _is_admin(u):
            return _err("مش مسموحلك تغيّر البيانات دي — العامل يقدر يغيّر الصورة وكلمة السر بس", 403)
        b = _body()
        new_name = (str(b.get("full_name") or "")).strip()
        new_username = (str(b.get("username") or "")).strip()
        if not new_name or not new_username:
            return _err("الاسم واسم المستخدم مطلوبين")
        db = ns["get_db"](); cur = db.cursor()
        try:
            cur.execute("UPDATE users SET full_name=%s, username=%s WHERE id=%s",
                        (new_name[:80], new_username[:40], u["id"]))
            db.commit()
        except ns["psycopg2"].IntegrityError:
            db.rollback(); cur.close()
            return _err("اسم المستخدم ده موجود بالفعل")
        cur.close()
        return _json({"ok": True, "message": "تم تحديث بياناتك"})

    @app.route(API + "profile/password", methods=["POST"])
    def api_profile_password():
        u = ns["current_user"]()
        b = _body()
        old_pw = str(b.get("old_password") or "")
        new_pw = str(b.get("new_password") or "")
        if not new_pw or len(new_pw) < 4:
            return _err("كلمة السر الجديدة قصيرة")
        if not check_password_hash(u["password_hash"], old_pw):
            return _err("كلمة السر الحالية غلط")
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("UPDATE users SET password_hash=%s WHERE id=%s",
                    (generate_password_hash(new_pw), u["id"]))
        db.commit(); cur.close()
        return _json({"ok": True, "message": "تم تحديث كلمة السر"})

    @app.route(API + "profile/avatar", methods=["POST"])
    def api_profile_avatar():
        u = ns["current_user"]()
        b = _body()
        raw = str(b.get("image_base64") or "")
        mime = str(b.get("mime") or "image/jpeg")
        if not mime.startswith("image/"):
            return _err("اختر صورة")
        try:
            data = base64.b64decode(raw, validate=False)
        except Exception:
            return _err("اختر صورة")
        if not data:
            return _err("اختر صورة")
        if len(data) > 5 * 1024 * 1024:
            return _err("الصورة كبيرة (الحد 5 ميجا)")
        data_url = "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("UPDATE users SET avatar=%s WHERE id=%s", (data_url, u["id"]))
        db.commit(); cur.close()
        return _json({"ok": True, "message": "تم تحديث صورتك", "avatar": data_url})

    # ───────────────────────── إغلاق اليوم: مسارات التحضير والإضافي والنصيب اليدوي ─────────────────────────
    # بتنادي نفس دوال app.py (admin_reopen_day / admin_mark_attendance / admin_mark_extra /
    # admin_set_manual_share) — التطبيق بيبعت form عادي + الهيدر X-Requested-With: fetch زي الموقع بالظبط.

    def _forward_admin(view_name):
        u = ns["current_user"]()
        if not _is_admin(u):
            return _err("للمسؤول فقط", 403)
        return ns[view_name]()

    @app.route(API + "admin/reopen-day", methods=["POST"])
    def api_reopen_day():
        return _forward_admin("admin_reopen_day")

    @app.route(API + "admin/mark-attendance", methods=["POST"])
    def api_mark_attendance():
        return _forward_admin("admin_mark_attendance")

    @app.route(API + "admin/mark-extra", methods=["POST"])
    def api_mark_extra():
        return _forward_admin("admin_mark_extra")

    @app.route(API + "admin/set-manual-share", methods=["POST"])
    def api_set_manual_share():
        return _forward_admin("admin_set_manual_share")

    # ───────────────────────── إدارة المستخدمين (للمسؤول الرئيسي) ─────────────────────────
    # نفس منطق admin_users في app.py بس بـ JSON بدل redirect+flash (الدالة الأصلية بترجّع redirect حتى في النجاح)

    def _super_only():
        u = ns["current_user"]()
        if not u or not ns["_is_super_admin"](u):
            return None, _err("هذه الصفحة للمسؤول الرئيسي فقط", 403)
        return u, None

    @app.route(API + "admin/users")
    def api_users_list():
        u, bad = _super_only()
        if bad:
            return bad
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("SELECT id, username, full_name, role, avatar FROM users WHERE role<>'system' "
                    "ORDER BY (role='admin') DESC, full_name")
        rows = cur.fetchall(); cur.close()
        items = [{
            "id": r["id"], "username": str(r["username"] or ""), "full_name": r["full_name"] or "",
            "role": r["role"], "avatar": r["avatar"] or "",
        } for r in rows]
        return _json({"ok": True, "items": items, "current_id": u["id"]})

    @app.route(API + "admin/users/create", methods=["POST"])
    def api_users_create():
        u, bad = _super_only()
        if bad:
            return bad
        b = _body()
        full_name = (b.get("full_name") or "").strip()
        password = b.get("password") or ""
        role = b.get("role") or "worker"
        if role not in ("worker", "admin"):
            role = "worker"
        if not (full_name and password):
            return _err("الاسم وكلمة السر مطلوبين", 400)
        db = ns["get_db"](); cur = db.cursor()
        try:
            new_uid = ns["_next_free_userid"](cur)
            cur.execute("INSERT INTO users(username, full_name, password_hash, role) VALUES(%s,%s,%s,%s)",
                        (new_uid, full_name, ns["generate_password_hash"](password), role))
            db.commit()
        except ns["psycopg2"].IntegrityError:
            db.rollback(); cur.close()
            return _err("حصل تعارض في الرقم — حاول تاني", 409)
        cur.close()
        return _json({"ok": True, "message": f"تم إضافة المستخدم برقم {new_uid}"})

    @app.route(API + "admin/users/delete", methods=["POST"])
    def api_users_delete():
        u, bad = _super_only()
        if bad:
            return bad
        uid = _int(_body().get("user_id"))
        if not uid:
            return _err("مستخدم غير صحيح", 400)
        if uid == u["id"]:
            return _err("مينفعش تحذف حسابك", 400)
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("DELETE FROM users WHERE id=%s", (uid,))
        db.commit(); cur.close()
        return _json({"ok": True, "message": "تم حذف المستخدم"})

    @app.route(API + "admin/users/rename", methods=["POST"])
    def api_users_rename():
        u, bad = _super_only()
        if bad:
            return bad
        b = _body()
        uid = _int(b.get("user_id"))
        new_name = (b.get("full_name") or "").strip()
        if not new_name:
            return _err("الاسم مطلوب", 400)
        db = ns["get_db"](); cur = db.cursor()
        try:
            cur.execute("UPDATE users SET full_name=%s WHERE id=%s AND role<>'system'", (new_name[:80], uid))
            db.commit()
        except ns["psycopg2"].IntegrityError:
            db.rollback(); cur.close()
            return _err("الاسم ده موجود بالفعل", 409)
        cur.close()
        return _json({"ok": True, "message": "تم تعديل الاسم"})

    @app.route(API + "admin/users/reset-password", methods=["POST"])
    def api_users_reset_pw():
        u, bad = _super_only()
        if bad:
            return bad
        b = _body()
        uid = _int(b.get("user_id"))
        new_pw = b.get("password") or ""
        if not new_pw:
            return _err("اكتب كلمة السر الجديدة", 400)
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("UPDATE users SET password_hash=%s WHERE id=%s", (ns["generate_password_hash"](new_pw), uid))
        db.commit(); cur.close()
        return _json({"ok": True, "message": "تم تغيير كلمة السر"})

    # ───────────────────────── إدارة المساحة (للمسؤول الرئيسي) ─────────────────────────
    # نفس بيانات admin_storage وعمليات التنظيف/الأرشفة/حذف النسخ/التحميل في app.py بـ JSON

    @app.route(API + "admin/storage")
    def api_storage():
        u, bad = _super_only()
        if bad:
            return bad
        stats = ns["_table_stats"]()
        limit = ns["_AUTO_ARCHIVE_LIMIT"]
        usage_pct = int(min(100, (stats["db_size"] / limit) * 100)) if limit > 0 else 0
        info = ns["_server_info"]()
        return _json({
            "ok": True,
            "stats": stats,
            "backups": ns["_list_backups"](),
            "limit_h": ns["_fmt_bytes"](limit),
            "usage_pct": usage_pct,
            "keep_days": ns["_AUTO_ARCHIVE_KEEP_DAYS"],
            "server_info": info,
        })

    @app.route(API + "admin/storage/cleanup", methods=["POST"])
    def api_storage_cleanup():
        u, bad = _super_only()
        if bad:
            return bad
        b = _body()
        table = (b.get("table") or "").strip()
        try:
            days = max(0, int(b.get("days") or 0))
        except (TypeError, ValueError):
            days = 0
        valid = {t[0]: t for t in ns["_STORAGE_TABLES"]}
        if table not in valid:
            return _err("جدول غير معروف", 400)
        _tname, _label, date_col = valid[table]
        db = ns["get_db"](); cur = db.cursor()
        if days == 0:
            where_sql, params = "", ()
        elif date_col:
            where_sql = f"WHERE {date_col} < NOW() - INTERVAL '{days} days'"
            params = ()
        else:
            cur.close()
            return _err("الجدول ده مفيهوش عمود تاريخ يقدر يفلتر عليه", 400)
        fname, n = ns["_backup_before_delete"](table, where_sql, params)
        if n == 0:
            cur.close()
            return _json({"ok": True, "message": "لا يوجد سطور مطابقة للحذف", "deleted": 0})
        cur.execute(f"DELETE FROM {table} {where_sql}", params)
        db.commit(); cur.close()
        return _json({"ok": True, "deleted": n,
                      "message": f"تم حذف {n} سطر من ({_label}) وحفظهم في ملف: {fname}"})

    @app.route(API + "admin/storage/delete-backup", methods=["POST"])
    def api_storage_delete_backup():
        u, bad = _super_only()
        if bad:
            return bad
        import os as _os
        name = (_body().get("name") or "").strip()
        if "/" in name or "\\" in name or ".." in name or not name:
            return _err("اسم ملف غير صالح", 400)
        fpath = _os.path.join(ns["_BACKUP_DIR"], name)
        if _os.path.isfile(fpath):
            try:
                _os.remove(fpath)
            except Exception as e:
                return _err(f"خطأ في الحذف: {e}", 500)
        return _json({"ok": True, "message": "تم حذف الملف الاحتياطي"})

    @app.route(API + "admin/storage/auto-archive", methods=["POST"])
    def api_storage_auto_archive():
        u, bad = _super_only()
        if bad:
            return bad
        r = ns["_auto_archive_if_needed"]()
        if r is None:
            msg = "لسه المساحة تحت الحد — مفيش داعي للأرشيف"
        elif r:
            msg = "تم أرشفة السطور القديمة وحذفها"
        else:
            msg = "مفيش سطور قديمة تتأرشف"
        return _json({"ok": True, "message": msg})

    @app.route(API + "admin/storage/download")
    def api_storage_download():
        u, bad = _super_only()
        if bad:
            return bad
        name = (request.args.get("name") or "").strip()
        return ns["admin_storage_download"](name)

    # ───────────────────────── نصيب كل الفريق (للمسؤول الرئيسي) ─────────────────────────
    # نفس admin_all_shares و admin_all_shares_send و admin_all_shares_send_telegram في app.py بـ JSON

    def _shares_bounds(src):
        from datetime import datetime as _dt
        s_arg = (src.get("start_day") or "").strip()
        e_arg = (src.get("end_day") or "").strip()
        try:
            start_d = _dt.strptime(s_arg, "%Y-%m-%d").date()
            end_d = _dt.strptime(e_arg, "%Y-%m-%d").date()
            if end_d < start_d:
                start_d, end_d = end_d, start_d
            half = None
        except ValueError:
            start_d, end_d, half = ns["_period_bounds"]()
        return start_d, end_d, half

    @app.route(API + "admin/all-shares")
    def api_all_shares():
        u, bad = _super_only()
        if bad:
            return bad
        start_d, end_d, half = _shares_bounds(request.args)
        s_iso, e_iso = start_d.isoformat(), end_d.isoformat()
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS worker_adjustments (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            day DATE NOT NULL, amount INTEGER NOT NULL, reason TEXT,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(user_id, day))""")
        rows = ns["_compute_shares_range"](cur, s_iso, e_iso)
        db.commit(); cur.close()
        items = [{
            "id": r["id"], "full_name": r.get("full_name") or "", "avatar": r.get("avatar") or "",
            "days": r.get("days") or 0, "chicks": r.get("chicks") or 0, "money": r.get("money") or 0,
            "bonus": r.get("bonus") or 0, "deduct": r.get("deduct") or 0,
        } for r in rows]
        return _json({
            "ok": True, "items": items, "start_day": s_iso, "end_day": e_iso,
            "period_label": ns["_period_label"](start_d, end_d, half),
        })

    @app.route(API + "admin/all-shares/send", methods=["POST"])
    def api_all_shares_send():
        u, bad = _super_only()
        if bad:
            return bad
        from flask import url_for
        start_d, end_d, half = _shares_bounds(_body())
        s_iso, e_iso = start_d.isoformat(), end_d.isoformat()
        label = ns["_period_label"](start_d, end_d, half)
        db = ns["get_db"](); cur = db.cursor()
        try:
            sent_ids, _bot = ns["_send_period_shares_dm"](cur, s_iso, e_iso, label)
            db.commit(); cur.close()
            try:
                ns["_notify_users"](sent_ids, "رسالة من خدمة العمال", f"حسابك عن {label} وصلك في الدردشة",
                                    url=url_for("chats_list"), type_="general")
            except Exception as _e:
                print("notify shares error:", _e)
            return _json({"ok": True, "message": f"تم إرسال الحساب لـ {len(sent_ids)} شخص من حساب خدمة العمال"})
        except Exception as ex:
            db.rollback(); cur.close()
            return _err("خطأ أثناء الإرسال: " + str(ex), 500)

    @app.route(API + "admin/all-shares/send-telegram", methods=["POST"])
    def api_all_shares_send_telegram():
        u, bad = _super_only()
        if bad:
            return bad
        start_d, end_d, half = _shares_bounds(_body())
        s_iso, e_iso = start_d.isoformat(), end_d.isoformat()
        label = ns["_period_label"](start_d, end_d, half)
        db = ns["get_db"](); cur = db.cursor()
        try:
            ns["_send_period_telegram_report"](cur, s_iso, e_iso, label)
            db.commit(); cur.close()
            return _json({"ok": True, "message": "تم إرسال التقرير لقناة تليجرام"})
        except Exception as ex:
            db.rollback(); cur.close()
            return _err("خطأ أثناء الإرسال لتليجرام: " + str(ex), 500)

    # ───────────────────────── الدردشة (قايمة + محادثة خاصة) ─────────────────────────
    # الدوال الأصلية بتشتغل زي ما هي (chat_messages_api / chat_send / chat_typing / chat_react / chat_edit_msg
    # / chat_delete_msg) — الراوتات هنا بس بتعدّي عليها بتوكن الـ API.

    def _capture_view(view, *args):
        """نفس _run_view في api_v1: يشغّل دالة صفحة ويرجّع بيانات render_template كـ dict"""
        from flask import g
        g._api_capture = {}
        try:
            resp = view(*args)
        finally:
            captured = g._api_capture
            g._api_capture = None
        if captured and "data" in captured:
            return captured["data"], None
        return None, resp

    @app.route(API + "chats")
    def api_chats():
        data, resp = _capture_view(ns["chats_list"])
        if data is None:
            return _err("الطلب مرفوض", 400)
        data = dict(data)
        data["ok"] = True
        data["admin_bot_username"] = str(ns.get("ADMIN_BOT_USERNAME", ""))
        return _json(data)

    @app.route(API + "chat/<int:other_id>/info")
    def api_chat_info(other_id):
        u = ns["current_user"]()
        if not u:
            return _err("غير مسجّل", 401)
        if other_id == u["id"]:
            return _err("مينفعش تدردش مع نفسك", 400)
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("SELECT id, full_name, username, avatar, last_seen, role FROM users WHERE id=%s", (other_id,))
        o = cur.fetchone()
        if not o:
            cur.close()
            return _err("المستخدم غير موجود", 404)
        cur.execute("UPDATE chat_messages SET read_at = NOW() WHERE sender_id=%s AND receiver_id=%s AND read_at IS NULL",
                    (other_id, u["id"]))
        db.commit(); cur.close()
        bot = str(ns.get("ADMIN_BOT_USERNAME", ""))
        return _json({
            "ok": True, "me_id": u["id"],
            "other": {"id": o["id"], "full_name": o["full_name"] or "", "username": str(o["username"] or ""),
                      "role": o["role"], "avatar": o["avatar"] or "", "online": bool(ns["_is_online"](o["last_seen"])),
                      "last_seen": ns["_iso_utc"](o["last_seen"]) if o["last_seen"] else None},
            "is_bot": str(o["username"] or "") == bot, "can_delete": bool(ns["_is_idara"](u)),
        })

    @app.route(API + "chat/<int:other_id>/messages")
    def api_chat_messages(other_id):
        return ns["chat_messages_api"](other_id)

    @app.route(API + "chat/<int:other_id>/send", methods=["POST"])
    def api_chat_send(other_id):
        return ns["chat_send"](other_id)

    @app.route(API + "chat/<int:other_id>/typing", methods=["POST"])
    def api_chat_typing(other_id):
        return ns["chat_typing"](other_id)

    @app.route(API + "chat/<int:other_id>/react/<int:msg_id>", methods=["POST"])
    def api_chat_react(other_id, msg_id):
        return ns["chat_react"](other_id, msg_id)

    @app.route(API + "chat/edit/<int:msg_id>", methods=["POST"])
    def api_chat_edit(msg_id):
        return ns["chat_edit_msg"](msg_id)

    @app.route(API + "chat/<int:other_id>/delete/<int:msg_id>", methods=["POST"])
    def api_chat_delete(other_id, msg_id):
        return ns["chat_delete_msg"](other_id, msg_id)

    # ───────────────────────── دردشة المجموعة ─────────────────────────
    # بتعدّي على دوال app.py الأصلية (group_messages_api / group_send / group_typing / group_react / group_edit_msg
    # / group_delete_msg / group_members_api / group_set_perm / group_toggle_lock) وبتضيف info و rename و avatar بـ JSON.

    @app.route(API + "group/info")
    def api_group_info():
        u = ns["current_user"]()
        if not u:
            return _err("غير مسجّل", 401)
        gs = ns["_get_group_settings"]()
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("SELECT COALESCE(MAX(id),0) AS m FROM group_messages")
        max_id = cur.fetchone()["m"]
        cur.execute("""INSERT INTO group_reads(user_id, last_read_id) VALUES(%s,%s)
                       ON CONFLICT (user_id) DO UPDATE SET last_read_id=EXCLUDED.last_read_id, updated_at=NOW()""",
                    (u["id"], max_id))
        db.commit()
        cur.execute("SELECT COUNT(*) AS c FROM users")
        members = cur.fetchone()["c"]
        cur.execute("SELECT can_delete FROM group_perms WHERE user_id=%s", (u["id"],))
        mp = cur.fetchone(); cur.close()
        is_admin = bool(u["role"] == "admin" or ns["_is_idara"](u))
        return _json({
            "ok": True, "me_id": u["id"], "is_admin": is_admin,
            "my_can_delete": bool(mp and mp["can_delete"]),
            "group": {"name": gs["name"], "avatar": gs["avatar"] or "", "members": members,
                      "is_locked": bool(gs["is_locked"]) if "is_locked" in gs else False},
        })

    @app.route(API + "group/messages")
    def api_group_messages():
        return ns["group_messages_api"]()

    @app.route(API + "group/send", methods=["POST"])
    def api_group_send():
        return ns["group_send"]()

    @app.route(API + "group/typing", methods=["POST"])
    def api_group_typing():
        return ns["group_typing"]()

    @app.route(API + "group/react/<int:msg_id>", methods=["POST"])
    def api_group_react(msg_id):
        return ns["group_react"](msg_id)

    @app.route(API + "group/edit/<int:msg_id>", methods=["POST"])
    def api_group_edit(msg_id):
        return ns["group_edit_msg"](msg_id)

    @app.route(API + "group/delete/<int:msg_id>", methods=["POST"])
    def api_group_delete(msg_id):
        return ns["group_delete_msg"](msg_id)

    @app.route(API + "group/members")
    def api_group_members():
        return ns["group_members_api"]()

    @app.route(API + "group/perms/<int:uid>", methods=["POST"])
    def api_group_perms(uid):
        return ns["group_set_perm"](uid)

    @app.route(API + "group/lock", methods=["POST"])
    def api_group_lock():
        u = ns["current_user"]()
        if not _is_admin(u):
            return _err("للمسؤول فقط", 403)
        return ns["group_toggle_lock"]()

    @app.route(API + "group/rename", methods=["POST"])
    def api_group_rename():
        u = ns["current_user"]()
        if not _is_admin(u):
            return _err("للمسؤول فقط", 403)
        name = (request.form.get("name") or _body().get("name") or "").strip()
        if not name:
            return _err("ادخل اسم", 400)
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("UPDATE group_settings SET name=%s WHERE id=1", (name[:60],))
        db.commit(); cur.close()
        return _json({"ok": True, "message": "تم تحديث اسم المجموعة"})

    @app.route(API + "group/avatar", methods=["POST"])
    def api_group_avatar():
        import base64 as _b64
        u = ns["current_user"]()
        if not _is_admin(u):
            return _err("للمسؤول فقط", 403)
        f = request.files.get("file")
        if not f:
            return _err("اختر صورة", 400)
        data = f.read()
        if len(data) > 5 * 1024 * 1024:
            return _err("الصورة كبيرة (الحد 5 ميجا)", 413)
        mime = f.mimetype or "image/jpeg"
        data_url = "data:" + mime + ";base64," + _b64.b64encode(data).decode("ascii")
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("UPDATE group_settings SET avatar=%s WHERE id=1", (data_url,))
        db.commit(); cur.close()
        return _json({"ok": True, "message": "تم تحديث صورة المجموعة"})

    # ───────────────────────── الفريق (قايمة الهمبرجر) + الدخول بحساب مستخدم ─────────────────────────
    # بيطابق sidebar_workers / is_real_super_admin في app.py (inject_user)

    @app.route(API + "team")
    def api_team():
        u = ns["current_user"]()
        if not u or u["role"] != "admin":
            return _json({"ok": True, "items": [], "can_impersonate": False})
        ru = ns["real_user"]()
        real_super = bool(ns["_is_super_admin"](ru))
        cur_super = bool(ns["_is_super_admin"](u))
        db = ns["get_db"](); cur = db.cursor()
        cur.execute("SELECT id, full_name, username, role, avatar FROM users "
                    "WHERE role IN ('worker','admin') AND role<>'system' "
                    "ORDER BY (role='admin') DESC, full_name")
        rows = cur.fetchall(); cur.close()
        items = []
        for w in rows:
            can_imp = bool(real_super and w["id"] != u["id"]
                           and not (w["role"] == "admin" and str(w["username"]) == "1"))
            items.append({
                "id": w["id"],
                "full_name": w["full_name"] or "",
                "role": w["role"],
                "avatar": w["avatar"] or "",
                "show_admin_tag": bool(w["role"] == "admin" and w["id"] != u["id"] and cur_super),
                "can_impersonate": can_imp,
            })
        return _json({"ok": True, "items": items, "can_impersonate": real_super})

    @app.route(API + "admin/impersonate", methods=["POST"])
    def api_impersonate_check():
        """بيتأكد إن الدخول بحساب المستخدم مسموح (نفس شروط admin_impersonate) ويرجّع بياناته."""
        ru = ns["real_user"]()
        if not ru or not ns["_is_super_admin"](ru):
            return _err("هذه الميزة للمسؤول الرئيسي فقط", 403)
        uid = _int(_body().get("uid"))
        target = ns["_load_user"](uid) if uid else None
        if not target:
            return _err("المستخدم غير موجود", 404)
        if target["role"] == "system":
            return _err("حساب خدمة العمال بيتفتح من صفحة إرسال إشعار فقط", 400)
        role = "admin" if (target["role"] == "admin" or ns["_is_idara"](target)) else target["role"]
        return _json({"ok": True, "id": target["id"], "full_name": target["full_name"] or "",
                      "role": role})

    # الهيدر X-Impersonate: التطبيق بيبعته لما المسؤول الرئيسي يدخل بحساب مستخدم.
    # بيتحط في session للطلب ده بس (مسارات الـ API مبتحفظش كوكي)، فكل الدوال اللي بتستخدم
    # current_user() بتشوف المستخدم المنتحَل زي الموقع بالظبط.
    def _impersonate_before():
        if not request.path.startswith(API):
            return None
        from flask import session
        session.pop("impersonate_id", None)
        raw = (request.headers.get("X-Impersonate") or "").strip()
        if not raw.isdigit():
            return None
        ru = ns["real_user"]()
        if not ru or not ns["_is_super_admin"](ru):
            return None
        target = ns["_load_user"](int(raw))
        if not target or target["role"] == "system":
            return None
        session["impersonate_id"] = target["id"]
        return None

    funcs = app.before_request_funcs.setdefault(None, [])
    funcs.insert(min(1, len(funcs)), _impersonate_before)
