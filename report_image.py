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

W = 1240  # عرض الصورة ثابت — الطول بيتحسب على حسب عدد الأسماء


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
    return d.textbbox((0, 0), txt, font=font)[2]


def _rtl(d, x_right, y, txt, font, fill=TEXT):
    """يكتب نص محدد من اليمين (x_right = الحد اليمين للنص)."""
    s = _shape(txt)
    d.text((x_right - _text_w(d, s, font), y), s, font=font, fill=fill)


def _ltr(d, x_left, y, txt, font, fill=TEXT):
    d.text((x_left, y), _shape(txt), font=font, fill=fill)


def _center(d, cx, y, txt, font, fill=TEXT):
    s = _shape(txt)
    d.text((cx - _text_w(d, s, font) / 2, y), s, font=font, fill=fill)


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


def _accent_bar(d, box, color, radius=26):
    """شريط لون رقيق على يمين الكارت."""
    x0, y0, x1, y1 = box
    d.rounded_rectangle((x1 - 10, y0 + 8, x1 - 4, y1 - 8), radius=4, fill=color)


def _header(d, title, subtitle, badge=None):
    _card(d, (40, 36, W - 40, 210), fill=CARD_SOFT, radius=32)
    cx = W / 2
    _center(d, cx, 56, title, _font(52, "Bold"), TEXT)
    _center(d, cx, 126, subtitle, _font(30, "Regular"), MUTED)
    d.rounded_rectangle((cx - 80, 178, cx + 80, 184), radius=3, fill=GOLD)
    if badge and _shape(badge) != _shape(subtitle):
        bs = _shape(badge)
        bf = _font(24, "SemiBold")
        bw = _text_w(d, bs, bf) + 40
        d.rounded_rectangle((cx - bw / 2, 160, cx + bw / 2, 206), radius=23, fill=(38, 58, 90))
        d.text((cx - _text_w(d, bs, bf) / 2, 168), bs, font=bf, fill=BLUE)


def _stat_tile(d, box, label, value, color, note=None):
    _card(d, box, fill=CARD, radius=24)
    _accent_bar(d, box, color)
    x0, y0, x1, y1 = box
    cx = (x0 + x1) / 2
    _center(d, cx, y0 + 20, label, _font(27, "SemiBold"), MUTED)
    _center(d, cx, y0 + 60, value, _font(46, "Bold"), color)
    if note:
        _center(d, cx, y0 + 120, note, _font(23, "Regular"), MUTED)


def _stats_grid(d, y, tiles, tile_h=160, gap=22):
    """شبكة عمودين (من اليمين للشمال)."""
    col_w = (W - 80 - gap) // 2
    for i, t in enumerate(tiles):
        r = i // 2
        c = i % 2
        x1 = (W - 40) - c * (col_w + gap)
        x0 = x1 - col_w
        y0 = y + r * (tile_h + gap)
        _stat_tile(d, (x0, y0, x1, y0 + tile_h), t[0], t[1], t[2], t[3] if len(t) > 3 else None)
    rows = (len(tiles) + 1) // 2
    return y + rows * (tile_h + gap)


def _section_title(d, y, txt, color=GOLD):
    _rtl(d, W - 44, y, txt, _font(34, "Bold"), TEXT)
    d.rounded_rectangle((W - 200, y + 52, W - 40, y + 57), radius=3, fill=color)
    return y + 78


def _people_table(d, y, people, cols, row_h=74):
    """
    جدول نصيب كل واحد.
    people: list of dict — الأعمدة بتتحدد من cols = [(العنوان, key, لون, نسبة العرض)]
    """
    pad = 40
    table_w = W - pad * 2
    head_h = 58
    total_h = head_h + max(1, len(people)) * row_h + 14
    _card(d, (pad, y, W - pad, y + total_h), fill=CARD, radius=26)

    # حساب حدود الأعمدة من اليمين للشمال
    widths = [int(table_w * c[3]) for c in cols]
    edges = []
    x_right = W - pad
    for wd in widths:
        edges.append((x_right - wd, x_right))
        x_right -= wd

    # رأس الجدول
    d.rounded_rectangle((pad + 2, y + 2, W - pad - 2, y + head_h), radius=24, fill=(33, 50, 78))
    d.rectangle((pad + 2, y + head_h - 22, W - pad - 2, y + head_h), fill=(33, 50, 78))
    for (cx0, cx1), c in zip(edges, cols):
        _center(d, (cx0 + cx1) / 2, y + head_h / 2 - 20, c[0], _font(26, "Bold"), MUTED)

    ry = y + head_h
    for i, p in enumerate(people):
        if i % 2 == 1:
            d.rectangle((pad + 3, ry, W - pad - 3, ry + row_h), fill=(28, 43, 67))
        else:
            d.line((pad + 24, ry, W - pad - 24, ry), fill=LINE, width=1)
        for j, ((cx0, cx1), c) in enumerate(zip(edges, cols)):
            val = p.get(c[1], "")
            fnt = _font(29, "Bold" if j > 0 else "SemiBold")
            if j == 0:  # عمود الاسم — محدد من اليمين
                # رقم الترتيب
                nf = _font(22, "Bold")
                d.ellipse((cx1 - 44, ry + row_h / 2 - 17, cx1 - 10, ry + row_h / 2 + 17),
                          fill=(40, 60, 92))
                _center(d, cx1 - 27, ry + row_h / 2 - 17, str(i + 1), nf, GOLD)
                _rtl(d, cx1 - 58, ry + row_h / 2 - 21, val, fnt, TEXT)
            else:
                _center(d, (cx0 + cx1) / 2, ry + row_h / 2 - 21, val, fnt, c[2])
        ry += row_h

    if not people:
        _center(d, W / 2, y + head_h + 18, "مفيش حضور مسجّل", _font(28, "Regular"), MUTED)

    return y + total_h


def _total_bar(d, y, label, value, color=GREEN):
    _card(d, (40, y, W - 40, y + 118), fill=(26, 46, 44) if color is GREEN else CARD_SOFT,
          radius=28, outline=color, width=2)
    _rtl(d, W - 76, y + 34, label, _font(32, "Bold"), TEXT)
    _ltr(d, 76, y + 24, value, _font(52, "Bold"), color)
    return y + 118


def _footer(d, y, txt):
    _center(d, W / 2, y + 16, txt, _font(24, "Regular"), MUTED)
    return y + 60


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

    rows = max(1, len(people))
    h = 250 + 3 * 182 + 78 + (58 + rows * 74 + 14) + 20 + 118 + 70
    img = _gradient_bg(h)
    d = ImageDraw.Draw(img)

    _header(d, "تقرير إغلاق اليوم", day_label or str(day), badge=str(day))

    y = 250
    y = _stats_grid(d, y, [
        ("بياض بدون خصم",  _num(nd_b), BLUE),
        ("تسمين بدون خصم", _num(nd_t), PURPLE),
        ("بياض بعد الخصم",  _num(af_b), GREEN),
        ("تسمين بعد الخصم", _num(af_t), ORANGE),
        ("إجمالي بدون خصم", _num(nd_t + nd_b), GOLD),
        ("إجمالي بعد الخصم", _num(af_t + af_b), GREEN),
    ], tile_h=160)

    y = _section_title(d, y + 6, f"نصيب كل واحد ({len(people)})")
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

    y = _total_bar(d, y + 20, "إجمالي نصيب الفريق اليوم", total_money_label)
    _footer(d, y, "التقرير بيتبعت تلقائي بعد إغلاق اليوم")
    return _finish(img)


# ===================== تقرير المدة (نصيب كل الفريق) =====================
def render_period_report(label, no_deduct_total, total_chicks, chick_price,
                         total_money_label, people, range_label=None):
    """
    people: [{"name":..., "days":int, "chicks":int, "money":str}]
    """
    rows = max(1, len(people))
    h = 250 + 2 * 182 + 78 + (58 + rows * 74 + 14) + 20 + 118 + 70
    img = _gradient_bg(h)
    d = ImageDraw.Draw(img)

    _header(d, "حساب نصيب كل الفريق", label, badge=range_label)

    y = 250
    y = _stats_grid(d, y, [
        ("الإجمالي بدون خصم في المدة", _num(no_deduct_total), GOLD),
        ("إجمالي كتاكيت الفريق", _num(total_chicks), BLUE),
        ("سعر الألف كتكوت", _num(chick_price), PURPLE),
        ("عدد المستحقين", _num(len(people)), GREEN),
    ], tile_h=160)

    y = _section_title(d, y + 6, f"نصيب كل واحد ({len(people)})")
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

    y = _total_bar(d, y + 20, "إجمالي حساب الفريق في المدة", total_money_label)
    _footer(d, y, "التقرير بيتبعت من صفحة نصيب كل الفريق")
    return _finish(img)
