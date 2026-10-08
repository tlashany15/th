# -*- coding: utf-8 -*-
"""
api_v1.py — طبقة API لتطبيق الأندرويد (JSON + توكن).

مبدأ الشغل:
- الملف ده "إضافة" فقط: مبيعدّلش على أي صفحة أو مسار موجود في الموقع.
- كل المسارات تحت /api/v1/ — والموقع القديم يفضل شغال زي ما هو.
- الحسابات (النصيب، إغلاق اليوم، التقارير) بتتعمل بنفس دوال الموقع بالظبط،
  فالأرقام في التطبيق = الأرقام في الموقع، من غير ما ننسخ المعادلات.

التفعيل: آخر app.py يتضاف سطرين:
    import api_v1
    api_v1.init_api(app, globals())
"""
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import (request, g, session, make_response, has_request_context,
                   get_flashed_messages)
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import check_password_hash

TOKEN_MAX_AGE = 60 * 60 * 24 * 30  # 30 يوم
_DEFAULT_SECRET = "change-me-please-very-secret"
API_PREFIX = "/api/v1/"


def _ser(o):
    """تحويل أي نوع مش JSON عادي (تواريخ، Decimal...) لنص/رقم."""
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o) if o % 1 else int(o)
    if isinstance(o, (set, tuple)):
        return list(o)
    if isinstance(o, bytes):
        return None
    return str(o)


def init_api(app, ns):
    """ns = globals() بتاعة app.py (عشان نستخدم دوالها من غير import دائري)."""

    # ---------- أدوات مساعدة ----------
    def _json(data, status=200):
        body = json.dumps(data, default=_ser, ensure_ascii=False)
        resp = make_response(body, status)
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
        return resp

    def _err(msg, status=400):
        return _json({"ok": False, "error": msg}, status)

    def _serializer():
        return URLSafeTimedSerializer(app.secret_key, salt="api-v1-token")

    def _is_admin(u):
        return bool(u and (u["role"] == "admin" or ns["_is_idara"](u)))

    # ---------- التقاط بيانات render_template ----------
    # الدوال القديمة بتنتهي بـ render_template(اسم، **بيانات). بنستبدل
    # render_template في app.py بنسخة: لو الطلب جاي من API بتحتفظ بالبيانات
    # بدل ما تبني HTML، ولو طلب عادي بتشتغل زي الأصل تماماً.
    _orig_render = ns["render_template"]

    def _render_or_capture(template_name, **ctx):
        if has_request_context() and getattr(g, "_api_capture", None) is not None:
            g._api_capture = {"template": template_name, "data": ctx}
            return ""
        return _orig_render(template_name, **ctx)

    ns["render_template"] = _render_or_capture

    def _run_view(view, *args):
        """يشغّل دالة صفحة قديمة ويرجّع بياناتها كـ JSON."""
        g._api_capture = {}
        try:
            resp = view(*args)
        finally:
            captured = g._api_capture
            g._api_capture = None
        # لو الدالة عملت redirect (صلاحيات / مدخلات غلط) نحوّله لخطأ JSON
        status = getattr(resp, "status_code", 200)
        if 300 <= status < 400:
            msgs = get_flashed_messages()
            return _err(msgs[0] if msgs else "الطلب مرفوض", 400)
        if captured and "data" in captured:
            return _json({"ok": True, **captured["data"]})
        # دوال بترجّع JSON مباشرة (زي close-day)
        return resp

    # ---------- المصادقة ----------
    def _api_before():
        if not request.path.startswith(API_PREFIX):
            return None
        # نخلّي دوال الموقع تردّ JSON بدل redirect لما تدعم ده
        request.environ["HTTP_X_REQUESTED_WITH"] = "fetch"
        if request.path == API_PREFIX + "login":
            return None
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return _err("غير مسجّل دخول", 401)
        try:
            uid = _serializer().loads(auth[7:].strip(), max_age=TOKEN_MAX_AGE)["uid"]
        except SignatureExpired:
            return _err("انتهت الجلسة، سجّل دخول تاني", 401)
        except (BadSignature, KeyError, TypeError):
            return _err("توكن غير صالح", 401)
        user = ns["_load_user"](uid)
        if not user or user["role"] == "system":
            return _err("الحساب غير موجود", 401)
        # الدوال القديمة بتقرا المستخدم من session — نملاه لهذا الطلب بس
        session["user_id"] = user["id"]
        return None

    # لازم تشتغل قبل _boot (وضع الصيانة/last_seen بيعتمدوا على session)
    app.before_request_funcs.setdefault(None, []).insert(0, _api_before)

    @app.after_request
    def _api_after(resp):
        if request.path.startswith(API_PREFIX):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    # مسارات الـ API متحفظش كوكي جلسة خالص (التوكن هو الهوية الوحيدة)
    _orig_save = app.session_interface.save_session

    def _save_session(app_, session_, response):
        if has_request_context() and request.path.startswith(API_PREFIX):
            return None
        return _orig_save(app_, session_, response)

    app.session_interface.save_session = _save_session

    # ---------- /api/v1/login ----------
    @app.route(API_PREFIX + "login", methods=["POST"])
    def api_login():
        if app.secret_key == _DEFAULT_SECRET:
            return _err("السيرفر محتاج SECRET_KEY سري في إعدادات Vercel قبل ما التطبيق يشتغل", 500)
        data = request.get_json(silent=True) or {}
        identifier = str(data.get("identifier") or data.get("username") or "").strip()
        password = str(data.get("password") or "")
        if not identifier or not password:
            return _err("اكتب الاسم وكلمة السر", 400)
        db = ns["get_db"]()
        cur = db.cursor()
        row = None
        if identifier.isdigit():
            cur.execute("SELECT * FROM users WHERE username=%s", (identifier,))
            row = cur.fetchone()
        if not row:
            cur.execute("SELECT * FROM users WHERE LOWER(TRIM(full_name))=LOWER(TRIM(%s)) "
                        "ORDER BY id ASC LIMIT 1", (identifier,))
            row = cur.fetchone()
        if not row:
            cur.execute("SELECT * FROM users WHERE username=%s", (identifier,))
            row = cur.fetchone()
        cur.close()
        if row and row["role"] == "system":
            return _err("الحساب ده حساب نظام — مينفعش الدخول بيه", 403)
        if not row or not check_password_hash(row["password_hash"], password):
            return _err("الاسم أو كلمة السر غير صحيحة", 401)
        token = _serializer().dumps({"uid": row["id"]})
        return _json({"ok": True, "token": token, "expires_in": TOKEN_MAX_AGE,
                      "user": {"id": row["id"], "full_name": row["full_name"],
                               "role": row["role"]}})

    # ---------- /api/v1/me ----------
    @app.route(API_PREFIX + "me")
    def api_me():
        u = ns["current_user"]()
        return _json({"ok": True, "user": {
            "id": u["id"], "full_name": u["full_name"], "role": u["role"],
            "is_admin": _is_admin(u)}})

    # ---------- نصيبي ----------
    @app.route(API_PREFIX + "my-share")
    def api_my_share():
        u = ns["current_user"]()
        return _run_view(ns["worker_stats"], u["id"])

    # ---------- لوحة الحضور اليومي (الرئيسية) ----------
    # بنفس دالة dashboard بتاعة الموقع، فالأرقام مطابقة تماماً. بنضيف بس تاريخ اليوم واسم اليوم.
    @app.route(API_PREFIX + "dashboard")
    def api_dashboard():
        resp = _run_view(ns["dashboard"])
        if getattr(resp, "status_code", 200) != 200:
            return resp
        try:
            data = json.loads(resp.get_data(as_text=True))
        except Exception:
            return resp
        t = date.today()
        data["today"] = t.isoformat()
        data["weekday"] = ns["weekday_ar"](t)
        return _json(data)

    # ---------- السجل / أعداد بعد الخصم ----------
    # بنفس دالة history بتاعة الموقع، ونرتّب الشكل اللي التطبيق محتاجه (الأيام المغلقة بس).
    @app.route(API_PREFIX + "history")
    def api_history():
        resp = _run_view(ns["history"])
        if getattr(resp, "status_code", 200) != 200:
            return resp
        try:
            data = json.loads(resp.get_data(as_text=True))
        except Exception:
            return resp
        u = ns["current_user"]()
        is_admin = bool(u and u["role"] == "admin")
        periods = []
        for p in data.get("periods", []):
            closed = [d for d in p.get("days", []) if d.get("has_data")]
            if not closed and not p.get("is_current"):
                continue
            days = []
            for d in reversed(closed):          # الأحدث فوق
                names = d.get("names") or []
                farms = d.get("attendee_farms") or []
                t_names, b_names = [], []
                for i, nm in enumerate(names):
                    fm = farms[i] if i < len(farms) else ""
                    (b_names if fm == "bayad" else t_names).append(nm)
                t_after = int(d.get("tasmeen_after") or 0)
                b_after = int(d.get("bayad_after") or 0)
                total = int(d.get("total") or 0)
                if (t_after + b_after) == 0 and total:
                    if t_names and not b_names:
                        t_after = total
                    elif b_names and not t_names:
                        b_after = total
                days.append({"date": d["date"], "day_num": d["day_num"], "weekday": d["weekday"],
                             "tasmeen_after": t_after, "bayad_after": b_after,
                             "extra_tasmeen": int(d.get("extra_tasmeen") or 0),
                             "extra_bayad": int(d.get("extra_bayad") or 0),
                             "total": total,
                             "tasmeen_names": t_names, "bayad_names": b_names})
            all_days = p.get("days", [])
            periods.append({
                "label": p.get("label", ""),
                "first_day": all_days[0]["day_num"] if all_days else 1,
                "last_day": all_days[-1]["day_num"] if all_days else 15,
                "start": closed[0]["date"] if closed else "",
                "end": closed[-1]["date"] if closed else "",
                "is_current": bool(p.get("is_current")),
                "closed_count": len(closed),
                "sum_tasmeen": sum(int(d.get("tasmeen_after") or 0) for d in closed),
                "sum_bayad": sum(int(d.get("bayad_after") or 0) for d in closed),
                "days": days,
            })
        return _json({"ok": True, "is_admin": is_admin, "periods": periods})

    # ---------- تصفير فترة (مسؤول فقط) — نفس منطق admin_reset_period ----------
    @app.route(API_PREFIX + "admin/reset-period", methods=["POST"])
    def api_reset_period():
        u = ns["current_user"]()
        if not (u and u["role"] == "admin"):
            return _err("الصلاحية دي للمسؤول فقط", 403)
        body = request.get_json(silent=True) or {}
        start_d = str(body.get("start") or "").strip()
        end_d = str(body.get("end") or "").strip()
        if not (start_d and end_d):
            return _err("فترة غير صالحة", 400)
        db = ns["get_db"]()
        cur = db.cursor()
        try:
            cur.execute("DELETE FROM vaccinations WHERE day BETWEEN %s AND %s", (start_d, end_d))
            cur.execute("DELETE FROM attendance   WHERE day BETWEEN %s AND %s", (start_d, end_d))
            cur.execute("DELETE FROM day_closures WHERE day BETWEEN %s AND %s", (start_d, end_d))
            cur.execute("""DELETE FROM period_summaries
                           WHERE make_date(year, month, CASE WHEN half=1 THEN 1 ELSE 16 END) BETWEEN %s AND %s""",
                        (start_d, end_d))
            db.commit()
        except Exception as e:
            db.rollback()
            return _err("خطأ أثناء التصفير: " + str(e), 500)
        finally:
            cur.close()
        return _json({"ok": True, "message": "تم تصفير الفترة من " + start_d + " إلى " + end_d})

    # ---------- السجل / أعداد بدون خصم (مسؤول) ----------
    @app.route(API_PREFIX + "admin/gross-log")
    def api_gross_log():
        resp = _run_view(ns["admin_gross_log"])
        if getattr(resp, "status_code", 200) != 200:
            return resp
        try:
            data = json.loads(resp.get_data(as_text=True))
        except Exception:
            return resp
        rows = [{"date": str(r.get("day"))[:10],
                 "tasmeen": int(r.get("no_deduct_tasmeen") or 0),
                 "bayad": int(r.get("no_deduct_bayad") or 0),
                 "no_deduct": int(r.get("no_deduct_total") or 0),
                 "total": int(r.get("total_count") or 0)}
                for r in data.get("rows", [])]
        return _json({"ok": True, "current": data.get("current_period", {}),
                      "past": data.get("past_periods", []), "rows": rows})

    # ---------- تصفير «بدون خصم» لمدة (مسؤول) — نفس منطق admin_gross_clear_period ----------
    @app.route(API_PREFIX + "admin/gross-clear", methods=["POST"])
    def api_gross_clear():
        import calendar as _cal
        u = ns["current_user"]()
        if not _is_admin(u):
            return _err("الصلاحية دي للمسؤول فقط", 403)
        body = request.get_json(silent=True) or {}
        try:
            y = int(body.get("year") or 0)
            m = int(body.get("month") or 0)
            half = int(body.get("half") or 0)
        except (TypeError, ValueError):
            return _err("مدخلات غير صالحة", 400)
        if not (y and 1 <= m <= 12 and half in (1, 2)):
            return _err("مدخلات غير صالحة", 400)
        last_day = _cal.monthrange(y, m)[1]
        if half == 1:
            s_d = date(y, m, 1).isoformat()
            e_d = date(y, m, min(15, last_day)).isoformat()
        else:
            s_d = date(y, m, 16).isoformat()
            e_d = date(y, m, last_day).isoformat()
        db = ns["get_db"]()
        cur = db.cursor()
        try:
            cur.execute("UPDATE day_closures SET no_deduct_total=0, no_deduct_tasmeen=0, no_deduct_bayad=0 "
                        "WHERE day BETWEEN %s AND %s", (s_d, e_d))
            db.commit()
        except Exception as ex:
            db.rollback()
            return _err("خطأ: " + str(ex), 500)
        finally:
            cur.close()
        return _json({"ok": True, "message": "تم تصفير الأعداد بدون خصم للمدة"})

    # ---------- بيانات قايمة الهمبرجر (صلاحيات + وضع الصيانة) ----------
    @app.route(API_PREFIX + "menu")
    def api_menu():
        u = ns["current_user"]()
        return _json({"ok": True,
                      "role": u["role"],
                      "is_super_admin": bool(ns["_is_super_admin"](u)),
                      "maintenance_on": bool(ns["_maintenance_on"]())})

    # ---------- إيقاف/تشغيل البرنامج للصيانة (المسؤول الرئيسي فقط) ----------
    @app.route(API_PREFIX + "maintenance", methods=["POST"])
    def api_maintenance():
        u = ns["current_user"]()
        if not ns["_is_super_admin"](u):
            return _err("الصلاحية دي للمسؤول الرئيسي فقط", 403)
        db = ns["get_db"]()
        cur = db.cursor()
        cur.execute("UPDATE system_settings SET maintenance_mode = NOT maintenance_mode, "
                    "updated_at = NOW() WHERE id = 1 RETURNING maintenance_mode")
        row = cur.fetchone()
        db.commit()
        cur.close()
        return _json({"ok": True, "maintenance_on": bool(row["maintenance_mode"]) if row else False})

    # ---------- تسجيل الحضور (تسمين / بياض) ----------
    # نفس منطق check_in في الموقع، بس بيرجّع JSON بدل redirect.
    @app.route(API_PREFIX + "check-in", methods=["POST"])
    def api_check_in():
        u = ns["current_user"]()
        today = date.today().isoformat()
        if ns["is_day_closed"](today):
            return _err("اليوم مغلق من المسؤول — لا يمكن تسجيل حضور جديد", 409)
        data = request.get_json(silent=True) or {}
        farm = data.get("farm") if data.get("farm") in ("tasmeen", "bayad") else "tasmeen"
        db = ns["get_db"]()
        cur = db.cursor()
        try:
            cur.execute("INSERT INTO attendance(user_id, day, farm) VALUES(%s,%s,%s)",
                        (u["id"], today, farm))
            db.commit()
            msg = "تم تسجيل حضورك اليوم"
        except ns["psycopg2"].IntegrityError:
            db.rollback()
            cur.execute("UPDATE attendance SET farm=%s WHERE user_id=%s AND day=%s",
                        (farm, u["id"], today))
            db.commit()
            msg = "تم تحديث نوع الحضور"
        finally:
            cur.close()
        return _json({"ok": True, "message": msg, "farm": farm})

    # ---------- إغلاق اليوم (للمسؤول) ----------
    @app.route(API_PREFIX + "admin/close-day", methods=["GET", "POST"])
    def api_close_day():
        u = ns["current_user"]()
        if not _is_admin(u):
            return _err("للمسؤول فقط", 403)
        if request.method == "GET":
            return _run_view(ns["admin_close_page"])
        # POST: الدالة القديمة بتقرا request.form وبترجّع JSON لو الهيدر fetch
        return _run_view(ns["admin_close_day"])

    # ---------- التقارير (للمسؤول) ----------
    @app.route(API_PREFIX + "admin/range-report", methods=["GET", "POST"])
    def api_range_report():
        u = ns["current_user"]()
        if not _is_admin(u):
            return _err("للمسؤول فقط", 403)
        return _run_view(ns["admin_range_report"])
