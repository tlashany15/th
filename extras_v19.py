# -*- coding: utf-8 -*-
"""
extras_v19.py — إضافات الإصدار 19
=================================
• فهرس الصور (Media Index) للدردشة الخاصة والمجموعة:
    /chat/<other_id>/media   →  كل صور المحادثة الخاصة
    /group/media             →  كل صور مجموعة الفريق

مش بيرجّع الصور نفسها في الـ HTML (عشان الصفحة تفضل خفيفة)،
بيرجّع أرقام الرسائل بس والصور بتتحمّل من /media/<scope>/<id>
اللي موجود أصلًا في app.py.

طريقة الاستخدام في app.py (سطرين في آخر الملف قبل تشغيل السيرفر):

    import extras_v19
    extras_v19.register(app, get_db=get_db, current_user=current_user,
                        login_required=login_required)
"""

from flask import render_template, redirect, url_for, flash, abort


def register(app, *, get_db, current_user, login_required):
    """يسجّل مسارات فهرس الصور على تطبيق فلاسك الحالي."""

    def _iso(dt):
        try:
            return dt.isoformat()
        except Exception:
            return None

    # ------------------------- صور الدردشة الخاصة -------------------------
    @app.route("/chat/<int:other_id>/media")
    @login_required
    def chat_media_index(other_id):
        u = current_user()
        if other_id == u["id"]:
            return redirect(url_for("chats_list"))
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT id, full_name, username, avatar FROM users WHERE id=%s",
            (other_id,),
        )
        other = cur.fetchone()
        if not other:
            cur.close()
            flash("المستخدم غير موجود", "error")
            return redirect(url_for("chats_list"))
        cur.execute(
            """
            SELECT id, sender_id, created_at
            FROM chat_messages
            WHERE kind='image'
              AND ((sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s))
            ORDER BY id DESC
            LIMIT 600
            """,
            (u["id"], other_id, other_id, u["id"]),
        )
        rows = cur.fetchall()
        cur.close()

        items = [
            {
                "id": r["id"],
                "mine": r["sender_id"] == u["id"],
                "created_at": _iso(r["created_at"]),
                "sender": (u["full_name"] if r["sender_id"] == u["id"] else other["full_name"]),
            }
            for r in rows
        ]
        return render_template(
            "media_index.html",
            scope="chat",
            items=items,
            title=other["full_name"],
            subtitle="فهرس صور المحادثة",
            avatar=other["avatar"],
            back_url=url_for("chat_room", other_id=other_id),
        )

    # ---------------------------- صور المجموعة ----------------------------
    @app.route("/group/media")
    @login_required
    def group_media_index():
        u = current_user()
        if not u:
            abort(403)
        db = get_db()
        cur = db.cursor()
        cur.execute(
            """
            SELECT m.id, m.sender_id, m.created_at, us.full_name AS sender_name
            FROM group_messages m
            LEFT JOIN users us ON us.id = m.sender_id
            WHERE m.kind='image' AND m.deleted=FALSE
            ORDER BY m.id DESC
            LIMIT 600
            """
        )
        rows = cur.fetchall()
        # اسم وصورة المجموعة (لو الدالة موجودة في app.py)
        gname, gavatar = "مجموعة الفريق", None
        try:
            gs = app.view_functions  # noqa: F841  (للتأكد إن app جاهز)
            from app import _get_group_settings  # type: ignore

            g = _get_group_settings()
            gname = g["name"] or gname
            gavatar = g["avatar"]
        except Exception:
            pass
        cur.close()

        items = [
            {
                "id": r["id"],
                "mine": r["sender_id"] == u["id"],
                "created_at": _iso(r["created_at"]),
                "sender": r["sender_name"] or "عضو",
            }
            for r in rows
        ]
        return render_template(
            "media_index.html",
            scope="group",
            items=items,
            title=gname,
            subtitle="فهرس صور المجموعة",
            avatar=gavatar,
            back_url=url_for("group_room"),
        )

    return app
