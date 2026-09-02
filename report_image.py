# -*- coding: utf-8 -*-
"""
report_image.py — بيرسم تقارير التطبيق على شكل صورة منسّقة (بدل الرسائل النصية).

الاستخدام:
    from report_image import render_day_report, render_period_report
    png_bytes = render_day_report(...)   # بيرجّع bytes صورة PNG

مفيش أي حساب أرقام هنا — الملف ده مسؤول عن الشكل بس.
"""

import io
import os

from PIL import Image, ImageDraw, ImageFont

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    # الخط (Cairo) مفيهوش الأشكال المنفصلة (isolated forms) — فبنسيب الحرف
    # الأصلي مكانها عشان ميظهرش مربع فاضي.
    _RESHAPER = arabic_reshaper.ArabicReshaper(configuration={
        "delete_harakat": False,
        "support_ligatures": False,
        "use_unshaped_instead_of_isolated": True,
    })
    _AR_OK = True
except Exception:  # pragma: no cover
    _AR_OK = False

FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "static", "fonts", "Cairo-Variable.ttf")

# ===================== لوحة الألوان =====================
BG_TOP      = (11, 18, 32)
BG_BOTTOM   = (18, 29, 48)
CARD        = (24, 37, 59)
CARD_SOFT   = (30, 45, 70)
LINE        = (46, 66, 97)
TEXT        = (238, 244, 255)
MUTED       = (150, 170, 199)
GOLD        = (247, 196, 92)
GREEN       = (74, 214, 154)
BLUE        = (91, 169, 255)
ORANGE      = (255, 148, 96)
PURPLE      = (176, 148, 255)

W = 1240   # عرض الصورة ثابت — الطول بيتحسب على حسب المحتوى
PAD = 44   # الهامش الجانبي الموحّد


# ===================== أدوات النص العربي =====================
def _shape(txt):
    """يظبط الحروف العربية متوصلة + اتجاه من اليمين للشمال."""
    s = "" if txt is None else str(txt)
    if not _AR_OK:
        return s
    try:
        return get_display(_RESHAPER.reshape(s))
    except Exception:
        return s


_font_cache = {}


def _font(size, weight="Regular"):
    key = (size, weight)
    if key in _font_cache:
        return _font_cache[key]
    f = ImageFont.truetype(FONT_PATH, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    _font_cache[key] = f
    return f


def _num(v):
    """أرقام بفواصل الآلاف (بأرقام إنجليزية عشان تبان واضحة)."""
    try:
        return f"{int(round(float(v or 0))):,}"
    except (TypeError, ValueError):
        return "0"


def _text_w(d, txt, font):
    b = d.textbbox((0, 0), txt, font=font)
    return b[2] - b[0]


def _draw(d, x, y, txt, font, fill=TEXT, anchor="mm"):
    """
    رسم نص بنقطة ارتساء (anchor) — ده اللي بيخلّي كل النصوص متظبطة
    رأسيًا وأفقيًا من غير أي تخمين في المسافات.
    anchor: mm = متمركز، rm = محدد من اليمين، lm = من الشمال.
    """
    d.text((x, y), _shape(txt), font=font, fill=fill, anchor=anchor)


def _center(d, cx, cy, txt, font, fill=TEXT):
    _draw(d, cx, cy, txt, font, fill, "mm")


def _rtl(d, x_right, cy, txt, font, fill=TEXT):
    _draw(d, x_right, cy, txt, font, fill, "rm")


def _ltr(d, x_left, cy, txt, font, fill=TEXT):
    _draw(d, x_left, cy, txt, font, fill, "lm")


def _fit_font(d, txt, max_w, size, weight="Bold", min_size=18):
    """يصغّر حجم الخط لحد ما النص يدخل في العرض المتاح (منع التداخل)."""
    s = _shape(txt)
    while size > min_size:
        f = _font(size, weight)
        if _text_w(d, s, f) <= max_w:
            return f
        size -= 1
    return _font(min_size, weight)


def _ellipsize(d, txt, max_w, font):
    """يقصّ النص الطويل بنقط لو مش داخل في العمود."""
    s = _shape(txt)
    if _text_w(d, s, font) <= max_w:
        return str(txt)
    t = str(txt)
    while len(t) > 1 and _text_w(d, _shape(t + "…"), font) > max_w:
        t = t[:-1]
    return t + "…"


def _gradient_bg(h):
    img = Image.new("RGB", (W, h), BG_TOP)
    top = Image.new("RGB", (1, h))
    px = top.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
    img.paste(top.resize((W, h)), (0, 0))
    return img


def _card(d, box, fill=CARD, radius=26, outline=LINE, width=2):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _accent_top(d, box, color):
    """شريط لون رفيع فوق الكارت في النص — أنضف من الشريط الجانبي."""
    x0, y0, x1, y1 = box
    cx = (x0 + x1) / 2
    d.rounded_rectangle((cx - 34, y0 + 10, cx + 34, y0 + 16), radius=3, fill=color)


# ===================== الهيدر =====================
HEADER_TOP = 36
HEADER_H = 196
CONTENT_Y = HEADER_TOP + HEADER_H + 34   # 266


def _header(d, title, subtitle, badge=None):
    box = (PAD, HEADER_TOP, W - PAD, HEADER_TOP + HEADER_H)
    _card(d, box, fill=CARD_SOFT, radius=32)
    cx = W / 2
    tf = _fit_font(d, title, W - PAD * 2 - 80, 52, "Bold", 34)
    _center(d, cx, HEADER_TOP + 62, title, tf, TEXT)

    sub = str(subtitle or "")
    bad = str(badge or "")
    line = sub if (not bad or _shape(bad) == _shape(sub)) else f"{sub}  •  {bad}"
    lf = _fit_font(d, line, W - PAD * 2 - 120, 28, "SemiBold", 20)
    lw = _text_w(d, _shape(line), lf) + 56
    cy = HEADER_TOP + 142
    d.rounded_rectangle((cx - lw / 2, cy - 26, cx + lw / 2, cy + 26), radius=26,
                        fill=(38, 58, 90))
    _center(d, cx, cy, line, lf, BLUE)


# ===================== الودجت =====================
def _stat_tile(d, box, label, value, color, note=None):
    _card(d, box, fill=CARD, radius=24)
    _accent_top(d, box, color)
    x0, y0, x1, y1 = box
    cx = (x0 + x1) / 2
    inner = (x1 - x0) - 40
    lf = _fit_font(d, label, inner, 26, "SemiBold", 17)
    vf = _fit_font(d, value, inner, 46, "Bold", 26)
    if note:
        _center(d, cx, y0 + 48, label, lf, MUTED)
        _center(d, cx, y0 + 96, value, vf, color)
        _center(d, cx, y0 + 136, note, _font(22, "Regular"), MUTED)
    else:
        _center(d, cx, y0 + 52, label, lf, MUTED)
        _center(d, cx, y0 + 108, value, vf, color)


def _stats_grid(d, y, tiles, tile_h=166, gap=22):
    """شبكة عمودين (من اليمين للشمال)."""
    col_w = (W - PAD * 2 - gap) / 2
    for i, t in enumerate(tiles):
        r, c = divmod(i, 2)
        x1 = (W - PAD) - c * (col_w + gap)
        x0 = x1 - col_w
        y0 = y + r * (tile_h + gap)
        _stat_tile(d, (x0, y0, x1, y0 + tile_h), t[0], t[1], t[2],
                   t[3] if len(t) > 3 else None)
    rows = (len(tiles) + 1) // 2
    return y + rows * (tile_h + gap) - gap


def _section_title(d, y, txt, color=GOLD):
    """عنوان القسم في النص."""
    cx = W / 2
    _center(d, cx, y + 24, txt, _font(34, "Bold"), TEXT)
    d.rounded_rectangle((cx - 70, y + 62, cx + 70, y + 67), radius=3, fill=color)
    return y + 94


# ===================== الجدول =====================
HEAD_H = 62
ROW_H = 74


def _table_h(n_rows):
    return HEAD_H + max(1, n_rows) * ROW_H + 12


def _people_table(d, y, people, cols):
    """
    جدول نصيب كل واحد.
    cols = [(العنوان, key, لون, نسبة العرض)]
    """
    table_w = W - PAD * 2
    total_h = _table_h(len(people))
    _card(d, (PAD, y, W - PAD, y + total_h), fill=CARD, radius=26)

    # حدود الأعمدة من اليمين للشمال
    widths = [table_w * c[3] for c in cols]
    edges = []
    x_right = W - PAD
    for wd in widths:
        edges.append((x_right - wd, x_right))
        x_right -= wd

    # رأس الجدول
    d.rounded_rectangle((PAD + 2, y + 2, W - PAD - 2, y + HEAD_H), radius=24, fill=(33, 50, 78))
    d.rectangle((PAD + 2, y + HEAD_H - 24, W - PAD - 2, y + HEAD_H), fill=(33, 50, 78))
    for (cx0, cx1), c in zip(edges, cols):
        _center(d, (cx0 + cx1) / 2, y + HEAD_H / 2, c[0], _font(25, "Bold"), MUTED)
    # فواصل رأسية خفيفة
    for (cx0, _cx1) in edges[1:]:
        d.line((cx0, y + HEAD_H + 6, cx0, y + total_h - 10), fill=(38, 56, 84), width=1)

    ry = y + HEAD_H
    for i, p in enumerate(people):
        if i % 2 == 1:
            d.rectangle((PAD + 3, ry, W - PAD - 3, ry + ROW_H), fill=(28, 43, 67))
        elif i:
            d.line((PAD + 26, ry, W - PAD - 26, ry), fill=LINE, width=1)
        mid = ry + ROW_H / 2
        for j, ((cx0, cx1), c) in enumerate(zip(edges, cols)):
            val = str(p.get(c[1], "") or "")
            if j == 0:  # عمود الاسم: رقم ترتيب + الاسم من اليمين
                d.ellipse((cx1 - 62, mid - 17, cx1 - 28, mid + 17), fill=(40, 60, 92))
                _center(d, cx1 - 45, mid + 1, str(i + 1), _font(21, "Bold"), GOLD)
                nf = _font(28, "SemiBold")
                avail = (cx1 - 78) - (cx0 + 16)
                _rtl(d, cx1 - 78, mid, _ellipsize(d, val, avail, nf), nf, TEXT)
            else:
                f = _fit_font(d, val, (cx1 - cx0) - 20, 28, "Bold", 18)
                _center(d, (cx0 + cx1) / 2, mid, val, f, c[2])
        ry += ROW_H

    if not people:
        _center(d, W / 2, y + HEAD_H + ROW_H / 2, "مفيش حضور مسجّل",
                _font(28, "Regular"), MUTED)

    return y + total_h


# ===================== الإجمالي والفوتر =====================
TOTAL_H = 122


def _total_bar(d, y, label, value, color=GREEN):
    box = (PAD, y, W - PAD, y + TOTAL_H)
    _card(d, box, fill=(26, 46, 44) if color is GREEN else CARD_SOFT,
          radius=28, outline=color, width=2)
    mid = y + TOTAL_H / 2
    _rtl(d, W - PAD - 34, mid, label, _font(31, "Bold"), TEXT)
    _ltr(d, PAD + 34, mid, value, _font(48, "Bold"), color)
    return y + TOTAL_H


def _footer(d, y, txt):
    _center(d, W / 2, y + 34, txt, _font(23, "Regular"), MUTED)
    return y + 66


def _finish(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ===================== تقرير إغلاق اليوم =====================
def render_day_report(day, no_deduct_tasmeen, no_deduct_bayad,
                      tasmeen_after, bayad_after, people, total_money_label,
                      day_label=None, extra_tasmeen=0, extra_bayad=0):
    """
    people: [{"name":..., "farm":"تسمين/بياض", "extra":bool, "chicks":int, "money":str}]
    """
    nd_t = int(no_deduct_tasmeen or 0)
    nd_b = int(no_deduct_bayad or 0)
    af_t = int(tasmeen_after or 0)
    af_b = int(bayad_after or 0)

    tile_h, gap = 166, 22
    grid_h = 3 * (tile_h + gap) - gap
    h = (CONTENT_Y + grid_h + 26 + 94 + _table_h(len(people))
         + 24 + TOTAL_H + 66 + 20)
    img = _gradient_bg(int(h))
    d = ImageDraw.Draw(img)

    _header(d, "تقرير إغلاق اليوم", day_label or str(day), badge=str(day))

    y = CONTENT_Y
    y = _stats_grid(d, y, [
        ("بياض بدون خصم",  _num(nd_b), BLUE),
        ("تسمين بدون خصم", _num(nd_t), PURPLE),
        ("بياض بعد الخصم",  _num(af_b), GREEN),
        ("تسمين بعد الخصم", _num(af_t), ORANGE),
        ("إجمالي بدون خصم", _num(nd_t + nd_b), GOLD),
        ("إجمالي بعد الخصم", _num(af_t + af_b), GREEN),
    ], tile_h=tile_h, gap=gap)

    y = _section_title(d, y + 26, f"نصيب كل واحد ({len(people)})")
    y = _people_table(d, y, [
        {
            "name": p["name"],
            "farm": (p.get("farm") or "—") + (" + إضافي" if p.get("extra") else ""),
            "chicks": _num(p.get("chicks")),
            "money": str(p.get("money") or "—"),
        } for p in people
    ], cols=[
        ("الاسم", "name", TEXT, 0.38),
        ("القسم", "farm", MUTED, 0.22),
        ("الكتاكيت", "chicks", BLUE, 0.18),
        ("النصيب", "money", GOLD, 0.22),
    ])

    y = _total_bar(d, y + 24, "إجمالي نصيب الفريق اليوم", total_money_label)
    _footer(d, y, "التقرير بيتبعت تلقائي بعد إغلاق اليوم")
    return _finish(img)


# ===================== تقرير المدة (نصيب كل الفريق) =====================
def render_period_report(label, no_deduct_total, total_chicks, chick_price,
                         total_money_label, people, range_label=None):
    """
    people: [{"name":..., "days":int, "chicks":int, "money":str}]
    """
    tile_h, gap = 166, 22
    grid_h = 2 * (tile_h + gap) - gap
    h = (CONTENT_Y + grid_h + 26 + 94 + _table_h(len(people))
         + 24 + TOTAL_H + 66 + 20)
    img = _gradient_bg(int(h))
    d = ImageDraw.Draw(img)

    _header(d, "حساب نصيب كل الفريق", label, badge=range_label)

    y = CONTENT_Y
    y = _stats_grid(d, y, [
        ("الإجمالي بدون خصم في المدة", _num(no_deduct_total), GOLD),
        ("إجمالي كتاكيت الفريق", _num(total_chicks), BLUE),
        ("سعر الألف كتكوت", _num(chick_price), PURPLE),
        ("عدد المستحقين", _num(len(people)), GREEN),
    ], tile_h=tile_h, gap=gap)

    y = _section_title(d, y + 26, f"نصيب كل واحد ({len(people)})")
    y = _people_table(d, y, [
        {
            "name": p["name"],
            "days": f"{_num(p.get('days'))} يوم",
            "chicks": _num(p.get("chicks")),
            "money": str(p.get("money") or "—"),
        } for p in people
    ], cols=[
        ("الاسم", "name", TEXT, 0.42),
        ("الأيام", "days", MUTED, 0.16),
        ("الكتاكيت", "chicks", BLUE, 0.18),
        ("الحساب", "money", GOLD, 0.24),
    ])

    y = _total_bar(d, y + 24, "إجمالي حساب الفريق في المدة", total_money_label)
    _footer(d, y, "التقرير بيتبعت من صفحة نصيب كل الفريق")
    return _finish(img)
