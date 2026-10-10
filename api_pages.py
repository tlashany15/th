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
