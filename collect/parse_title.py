# -*- coding: utf-8 -*-
"""卓部屋トピックタイトルのパーサー（表記ゆれ耐性の要）
対応: `7/12 21:00-25:00【レギュ】名` / `~`/`～`/`-`混在 / `(木)`曜日 / 複数日`7/11,12,14` /
     `日程すり合わせ【..】` `卓ピタ調整【..】` / `【第一話】7/11【SW2.5】名`(話数枠を除外)
実測: chartavora採集の実タイトル1,186本でテスト（__main__）。
"""
import re, json, sys

EP = re.compile(r"^(第?[0-9０-９一二三四五六七八九十]+話|最終話|前編|後編|中編|完結編|序章|終章)$")
SURI = re.compile(r"すり合わせ|すりあわせ|摺り合わせ|擦り合わせ|日程調整|卓ピタ調整|卓ピタ|日程相談|スケジュール調整|調整中|延期|仮置き|いずれか|[XxＸｘ]{2}")
TIME = re.compile(r"([0-9０-９]{1,2})[:：]([0-9０-９]{2})")
TIME_KANJI = re.compile(r"([0-9０-９]{1,2})\s*時(?:\s*([0-9０-９]{1,2})\s*分)?(?:半)?")
DATE = re.compile(r"([0-9０-９]{1,2})\s*[/／]\s*([0-9０-９]{1,2})")
DATE_KANJI = re.compile(r"([0-9０-９]{1,2})\s*月\s*([0-9０-９]{1,2})\s*日")

def z2h(s):
    return s.translate(str.maketrans("０１２３４５６７８９：／", "0123456789:/"))

def parse(title):
    t = z2h(title.strip())
    out = {"raw": title, "reg": None, "scenario": None, "dates": [], "start": None, "end": None,
           "suriawase": False, "episode": None, "ok": False}
    # 年プレフィックス（2024/4/8等）を除去してから日付を読む
    t = re.sub(r"20[0-9]{2}\s*[/年]\s*", "", t)
    # 【】群からレギュ枠と話数枠を判別（【】が無ければ『』をタイトル括弧として代用）
    braces = [(m.start(), m.end(), m.group(1)) for m in re.finditer(r"【([^】]*)】", t)]
    quote_style = False  # 『』派＝レギュ枠でなく作品タイトル括弧（狂気山脈カテナ班の実例 2026-07-05）
    if not braces:
        braces = [(m.start(), m.end(), m.group(1)) for m in re.finditer(r"『([^』]*)』", t)]
        quote_style = bool(braces)
    reg_span = None
    for s_, e_, inner in braces:
        if EP.match(inner.strip()):
            out["episode"] = inner.strip()
            continue
        reg_span = (s_, e_)
        out["reg"] = inner.strip() or None
    if reg_span:
        after = t[reg_span[1]:].strip() or None
        if quote_style:
            # 『中身』→シナリオ名・後続テキスト(班名等)は添える・レギュ欄は空（逆転表示の修正）
            inner = out["reg"]; out["reg"] = None
            out["scenario"] = (inner + (" " + after if after else "")) if inner else after
        else:
            out["scenario"] = after
        head = t[:reg_span[0]]
    else:
        out["scenario"] = None
        head = t
    # すり合わせ型
    if SURI.search(head) or (not DATE.search(head) and SURI.search(t)):
        out["suriawase"] = True
    # 日付（先頭部から。7/11,12,14 の日only継続にも対応。漢字日付「2月4日」も）
    dates = []
    m0 = DATE.search(head) or DATE_KANJI.search(head)
    if m0:
        month = int(m0.group(1)); day = int(m0.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            dates.append((month, day))
            # 継続 ,12,14 / ・13 / 、15 （時刻の「:」が来たら打ち切り）
            rest = head[m0.end():]
            for cm in re.finditer(r"[,、・]\s*([0-9]{1,2})(?:/([0-9]{1,2}))?", rest):
                if cm.group(2):
                    mm, dd = int(cm.group(1)), int(cm.group(2))
                else:
                    mm, dd = month, int(cm.group(1))
                if 1 <= mm <= 12 and 1 <= dd <= 31:
                    dates.append((mm, dd))
                rest_upto = rest[:cm.start()]
                if ":" in rest_upto:
                    dates = dates[:1]
                    break
    out["dates"] = dates
    # 時刻（開始〜終了。区切りは - ~ ～ 〜 ‐ ぐらいを許容。「21時」「21時30分」表記も）
    times = TIME.findall(head)
    if not times:
        times = [(h, mm or "00") for h, mm in TIME_KANJI.findall(head)]
    if times:
        out["start"] = f"{int(times[0][0])}:{times[0][1]}"
        if len(times) >= 2:
            out["end"] = f"{int(times[1][0])}:{times[1][1]}"
    # 【】の後ろが空＝【】の中身が実質タイトル（レギュ単独運用・シリーズ卓に多い実例）
    if not out["scenario"] and out["reg"]:
        out["scenario"] = out["reg"]
        out["reg_is_name"] = True
    # 成立判定：名前が取れて、（日付あり）or（すり合わせ）。開始時刻は無くても掲載可（時刻未定表示）
    out["ok"] = bool(out["scenario"] and (out["dates"] or out["suriawase"]))
    return out

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "../chartavora_bot/_titles_ar2e.json"
    titles = json.load(open(src, encoding="utf-8"))
    ok, partial, fail = [], [], []
    for t in titles:
        r = parse(t)
        if r["ok"]:
            ok.append(r)
        elif r["reg"] and r["scenario"]:
            partial.append(r)   # レギュ・名は取れたが日時が不明（挙動：すり合わせ扱い or 手動枠）
        else:
            fail.append(r)
    n = len(titles)
    print(f"対象: {n}本")
    print(f"完全認識(日時/すり合わせまで判定OK): {len(ok)}本 ({len(ok)/n*100:.1f}%)")
    print(f"部分認識(レギュ+名のみ・日時不明):   {len(partial)}本 ({len(partial)/n*100:.1f}%)")
    print(f"認識不能:                            {len(fail)}本 ({len(fail)/n*100:.1f}%)")
    print("\n--- 部分認識の例(最大10) ---")
    for r in partial[:10]: print("  ", r["raw"])
    print("\n--- 認識不能の例(最大15) ---")
    for r in fail[:15]: print("  ", r["raw"])
