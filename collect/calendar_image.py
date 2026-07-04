# -*- coding: utf-8 -*-
"""カレンダー画像ジェネレータ v2 — スマホ前提の縦長アジェンダ（2026-07-04装丁刷新）
=================================================================
上=「今月のこみぐあい」ミニ月間（どの日に何卓あるか）／下=日付ごとの大きな文字の卓リスト。
配色はボードのスモークガラスと同期。日次webhook投稿(post_calendar.py)の素材。

使い方: python calendar_image.py [-y 2026 -m 7] [-o calendar.png]
"""
import os, json, re, math, datetime, argparse

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- 配色（index.htmlのスモークガラス:rootと同期） ----
BG = "#181b1e"; CARD = "#23262b"; CARD_HI = "#2a2e34"; TX = "#e8e5de"; MUT = "#a09a8e"
GRN = "#a8cbb2"; GRN_DEEP = "#33603f"; GRN2 = "#4f8160"; CLN = "#3a3e45"
SUN = "#e08f83"; SAT = "#96b7e4"; TER = "#e09a6e"; GOLD = "#d8b56a"

# ---- システム色分け（index.htmlのSYS_DEFSと同期） ----
AR2E_REGS = {"ミスリルクレスト", "ミスリルクエスト", "氷原開拓団", "フツウノアリアン", "イジョウナアリアン",
             "ピースメイカー", "アンコールを流星に", "さちあれ", "賽は投げられた", "ダンジョン・トラベラーズ",
             "ネームドエネミー討伐RTA!!", "勇者の首を晒せ", "グルメ卓"}
SYS_DEFS = [
    ("アリアンロッド2E", "#6fae82", re.compile(r"アリアンロッド|AR2E", re.I)),
    ("SW2.5",           "#7ca4d8", re.compile(r"SW2\.?5|ソードワールド", re.I)),
    ("CoC",             "#a08ac8", re.compile(r"CoC|クトゥルフ", re.I)),
    ("サタスペ",         "#d88a80", re.compile(r"サタスペ")),
    ("シノビガミ",       "#8d93b8", re.compile(r"シノビガミ")),
    ("DX3rd",           "#d883a8", re.compile(r"DX3rd|ダブルクロス", re.I)),
    ("ブルアカ",         "#6fb8d8", re.compile(r"ブルアカ")),
    ("ステラナイツ",     "#d8b56a", re.compile(r"ステラナイツ")),
    ("D&D",             "#c87878", re.compile(r"D&D|DnD|ダンジョンズ", re.I)),
    ("Needle",          "#7ab8b4", re.compile(r"Needle|ニードル", re.I)),
]
OTHER = "#9a948a"

def sys_color(s):
    r = (s.get("reg") or "") + " " + (s.get("scenario") or "")
    reg = s.get("reg") or ""
    if reg in AR2E_REGS or any(k in reg for k in AR2E_REGS):
        return SYS_DEFS[0][1]
    for _, c, pat in SYS_DEFS:
        if pat.search(r):
            return c
    return OTHER

def tint(hexc, alpha=0.16):
    """チップ地に色を薄く敷く（ダークパネルへ混色）"""
    r, g, b = int(hexc[1:3], 16), int(hexc[3:5], 16), int(hexc[5:7], 16)
    f = lambda a, b_: int(a * alpha + b_ * (1 - alpha))
    return (f(r, 40), f(g, 44), f(b, 50))

EMOJI = re.compile(r"[\U0001F000-\U0001FAFF☀-➿️]")

def font(size, bold=False, serif=False):
    if serif:
        cands = [r"C:\Windows\Fonts\yumindb.ttf", r"C:\Windows\Fonts\yumin.ttf",
                 "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"]
    else:
        cands = ([r"C:\Windows\Fonts\YuGothB.ttc", r"C:\Windows\Fonts\meiryob.ttc"] if bold else
                 [r"C:\Windows\Fonts\YuGothM.ttc", r"C:\Windows\Fonts\meiryo.ttc"])
        cands += ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else
                  "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
    for p in cands:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default(size)

def ellipsis(draw, text, f, maxw):
    text = EMOJI.sub("", text or "").strip()
    if draw.textlength(text, font=f) <= maxw:
        return text
    while text and draw.textlength(text + "…", font=f) > maxw:
        text = text[:-1]
    return text + "…"

def time_band(st):
    """開始時刻→asa(5-11)/hiru(12-17)/yoru(18-4)。ボード(index.html timeBand)と同期"""
    try:
        n = int(str(st).split(":")[0]) % 24
    except (ValueError, IndexError):
        return ""
    return "asa" if 5 <= n <= 11 else "hiru" if 12 <= n <= 17 else "yoru"

ASA_C = "#e09a6e"; HIRU_C = "#d8b56a"; YORU_C = "#96a4d8"

def draw_time_icon(dr, band, x, y, s, bg):
    if band == "asa":
        r = s * 0.42
        cxc, cyc = x + s / 2, y + s * 0.68
        dr.pieslice([cxc - r, cyc - r, cxc + r, cyc + r], 180, 360, fill=ASA_C)
        dr.rounded_rectangle([x, cyc - 1, x + s, cyc + 1.6], 1, fill=ASA_C)
        for dx, dy in ((0, -1), (-1, -0.55), (1, -0.55)):
            x2, y2 = cxc + dx * r * 1.15, cyc - r * 0.9 + dy * r * 0.75
            x1, y1 = cxc + dx * r * 0.75, cyc - r * 0.6 + dy * r * 0.35
            dr.line([x1, y1, x2, y2], fill=ASA_C, width=2)
    elif band == "hiru":
        cxc, cyc = x + s / 2, y + s / 2
        r = s * 0.26
        dr.ellipse([cxc - r, cyc - r, cxc + r, cyc + r], fill=HIRU_C)
        for i in range(8):
            a = math.pi / 4 * i
            dr.line([cxc + math.cos(a) * r * 1.5, cyc + math.sin(a) * r * 1.5,
                     cxc + math.cos(a) * r * 2.0, cyc + math.sin(a) * r * 2.0], fill=HIRU_C, width=2)
    elif band == "yoru":
        dr.ellipse([x + 1, y + 1, x + s - 1, y + s - 1], fill=YORU_C)
        off = s * 0.30
        dr.ellipse([x + 1 + off, y + 1 - off * 0.6, x + s - 1 + off, y + s - 1 - off * 0.6], fill=bg)

WD = ["月", "火", "水", "木", "金", "土", "日"]  # datetime.weekday()順

def wd_color(dt):
    return SUN if dt.weekday() == 6 else SAT if dt.weekday() == 5 else MUT

def render(data, year, month, out):
    sessions = data.get("sessions", [])
    bydate = {}
    for s in sessions:
        for d in s.get("dates", []):
            try:
                dt = datetime.date.fromisoformat(d["date"])
            except Exception:
                continue
            if dt.year == year and dt.month == month:
                bydate.setdefault(dt.day, []).append((d.get("start") or "", d.get("end") or "", s))
    for v in bydate.values():
        v.sort(key=lambda x: x[0])
    suri = [s for s in sessions if s.get("suriawase")]
    today = datetime.date.today()

    # ---- 縦長レイアウト採寸 ----
    W = 1080; PAD = 46
    f_title = font(50, serif=True); f_sub = font(24)
    f_mini_d = font(22, True); f_mini_c = font(20, True); f_dow = font(22, True)
    f_dayh = font(34, True); f_name = font(31, True); f_meta = font(24); f_badge = font(21, True)
    f_foot = font(22)

    first = datetime.date(year, month, 1)
    ndays = (datetime.date(year + (month == 12), month % 12 + 1, 1) - first).days
    lead = (first.weekday() + 1) % 7  # 日曜始まり
    weeks = -(-(lead + ndays) // 7)

    mini_cell = (W - PAD * 2 - 6 * 6) // 7
    mini_h = 34 + weeks * (mini_cell + 6) + 18
    head_h = 118
    ses_row = 96; day_head = 56; day_gap = 14
    agenda_h = sum(day_head + len(v) * (ses_row + 8) + day_gap for v in bydate.values())
    suri_h = (64 + len(suri) * (ses_row + 8)) if suri else 0
    foot_h = 76
    H = head_h + mini_h + 30 + agenda_h + suri_h + foot_h

    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    # 色むら＋天の飾り帯
    ov = Image.new("RGB", (W, H), BG)
    od = ImageDraw.Draw(ov)
    od.ellipse([-300, -260, 560, 380], fill="#1d2422")
    od.ellipse([W - 420, H - 500, W + 300, H + 200], fill="#20201c")
    img = Image.blend(img, ov, 0.5)
    dr = ImageDraw.Draw(img)
    for x in range(W):
        t = abs(x / W - .5)
        dr.line([(x, 0), (x, 5)], fill=(GOLD if t < .04 else (GRN2 if t < .35 else GRN_DEEP)))

    # ---- ヘッダ ----
    dr.text((PAD, 28), f"{month}月の卓予定", font=f_title, fill=GRN)
    right = f"{data.get('guild','')}　{data.get('updated','')}更新"
    dr.text((W - PAD - dr.textlength(right, font=f_sub), 52), right, font=f_sub, fill=MUT)

    # ---- ミニ月間（こみぐあい） ----
    y0 = head_h
    for i, w in enumerate(["日", "月", "火", "水", "木", "金", "土"]):
        x = PAD + i * (mini_cell + 6)
        c = SUN if i == 0 else SAT if i == 6 else MUT
        dr.text((x + mini_cell / 2 - dr.textlength(w, font=f_dow) / 2, y0), w, font=f_dow, fill=c)
    y0 += 34
    for day in range(1, ndays + 1):
        idx = lead + day - 1
        r, c = divmod(idx, 7)
        x = PAD + c * (mini_cell + 6); y = y0 + r * (mini_cell + 6)
        n = len(bydate.get(day, []))
        fill = CARD if n == 0 else tint("#6fae82", min(.16 + .18 * n, .7))
        is_today = (today.year, today.month, today.day) == (year, month, day)
        dr.rounded_rectangle([x, y, x + mini_cell, y + mini_cell], 10, fill=fill,
                             outline=TER if is_today else CLN, width=3 if is_today else 1)
        dc = SUN if c == 0 else SAT if c == 6 else (TX if n else MUT)
        dr.text((x + 8, y + 5), str(day), font=f_mini_d, fill=dc)
        if n:
            label = f"{n}卓"
            dr.text((x + mini_cell - 10 - dr.textlength(label, font=f_mini_c), y + mini_cell - 30),
                    label, font=f_mini_c, fill=GRN)

    # ---- アジェンダ（日付ごとの卓リスト） ----
    yy = y0 + weeks * (mini_cell + 6) + 18 + 30
    for day in sorted(bydate):
        dt = datetime.date(year, month, day)
        past = dt < today
        wd = WD[dt.weekday()]
        hcol = wd_color(dt)
        label = f"{month}/{day}（{wd}）"
        dr.text((PAD, yy + 8), label, font=f_dayh, fill=hcol if not past else CLN)
        if (today.year, today.month, today.day) == (year, month, day):
            bx = PAD + dr.textlength(label, font=f_dayh) + 14
            dr.rounded_rectangle([bx, yy + 14, bx + 76, yy + 46], 8, fill=TER)
            dr.text((bx + 12, yy + 17), "今日", font=f_badge, fill="#1a1410")
        yy += day_head
        for st, en, s in bydate[day]:
            col = sys_color(s)
            row_bg = tint(col, .13) if not past else CARD
            dr.rounded_rectangle([PAD, yy, W - PAD, yy + ses_row], 14, fill=row_bg, outline=CLN, width=1)
            dr.rounded_rectangle([PAD, yy, PAD + 7, yy + ses_row], 3, fill=col if not past else CLN)
            tx = TX if not past else MUT
            bd = time_band(st)
            nx = PAD + 24
            if bd:
                draw_time_icon(dr, bd, nx, yy + 16, 26, row_bg)
                nx += 38
            name_w = W - PAD - nx - 150
            dr.text((nx, yy + 8), ellipsis(dr, s.get("scenario") or "？", f_name, name_w), font=f_name, fill=tx)
            meta = f"{st}{'-' + en if en else ''}"
            if s.get("reg") and not s.get("reg_is_name"):
                meta += f"　【{s['reg']}】"
            if s.get("gm"):
                meta += f"　GM: {s['gm']}"
            dr.text((nx, yy + 54), ellipsis(dr, meta, f_meta, name_w + 130), font=f_meta, fill=MUT)
            if s.get("open") and not past:
                bw = 110
                dr.rounded_rectangle([W - PAD - bw - 14, yy + 12, W - PAD - 14, yy + 46], 10,
                                     fill=tint("#6fae82", .3))
                dr.text((W - PAD - bw + 2, yy + 16), "募集中", font=f_badge, fill=GRN)
            yy += ses_row + 8
        yy += day_gap

    # ---- すり合わせ ----
    if suri:
        dr.rectangle([PAD, yy + 8, PAD + 14, yy + 26], fill="#d8b47e")
        dr.text((PAD + 24, yy), "日程すり合わせ中", font=f_dayh, fill="#d8b47e")
        yy += 64
        for s in suri:
            col = sys_color(s)
            dr.rounded_rectangle([PAD, yy, W - PAD, yy + ses_row], 14, fill=CARD, outline="#5c4f35", width=1)
            dr.rounded_rectangle([PAD, yy, PAD + 7, yy + ses_row], 3, fill=col)
            dr.text((PAD + 24, yy + 8), ellipsis(dr, s.get("scenario") or "？", f_name, W - PAD * 2 - 190),
                    font=f_name, fill=TX)
            meta = "日付はこれから" + (f"　GM: {s['gm']}" if s.get("gm") else "")
            dr.text((PAD + 24, yy + 54), ellipsis(dr, meta, f_meta, W - PAD * 2 - 60), font=f_meta, fill=MUT)
            if s.get("open"):
                bw = 110
                dr.rounded_rectangle([W - PAD - bw - 14, yy + 12, W - PAD - 14, yy + 46], 10,
                                     fill=tint("#6fae82", .3))
                dr.text((W - PAD - bw + 2, yy + 16), "募集中", font=f_badge, fill=GRN)
            yy += ses_row + 8

    # ---- フッタ ----
    n_open = sum(1 for s in sessions if s.get("open"))
    foot = f"掲載 {len(sessions)}卓（募集中 {n_open}）／詳細・最新はボードへ"
    dr.text((PAD, yy + 20), foot, font=f_foot, fill=MUT)
    url = "namezu.github.io/henkyo-session-board"
    dr.text((W - PAD - dr.textlength(url, font=f_foot), yy + 20), url, font=f_foot, fill=GRN)

    img.save(out)
    print(f"🖼 カレンダー画像: {out} ({W}x{H})")
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    today = datetime.date.today()
    ap.add_argument("-y", type=int, default=today.year)
    ap.add_argument("-m", type=int, default=today.month)
    ap.add_argument("-i", default=os.path.join(HERE, "sessions.json"))
    ap.add_argument("-o", default=os.path.join(HERE, "calendar.png"))
    a = ap.parse_args()
    with open(a.i, encoding="utf-8") as f:
        data = json.load(f)
    render(data, a.y, a.m, a.o)
