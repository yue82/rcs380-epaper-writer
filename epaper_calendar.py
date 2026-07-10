#!/usr/bin/env python3
"""カレンダーの当日予定を 400x300 2色 e-paper 用に書くための画像を作成する。
1日タイムラインを9-14時、14-19時の左右2カラムで描く。

予定データ: JSON (list of {"title","start","end","allDay"})。start/end は ISO8601。
左カラム=9-14時、右カラム=14-19時。予定は継続時間ぶんの高さの帯。
--demo でダミー、--today 基準日、--now 更新時刻(HH:MM)、--out 出力PNG。
"""
import argparse
import datetime as dt
import json

from PIL import Image, ImageDraw, ImageFont

W, H = 400, 300
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
WEEKJP = ["月", "火", "水", "木", "金", "土", "日"]

DAY_START, DAY_END = 9, 19           # 表示する時間帯
SPLIT = (DAY_START + DAY_END) // 2    # 左右カラムの境界 = 14時
HDR_H = 30
ALLDAY_H = 16                         # 終日予定を出す帯の高さ (終日予定がある日のみ)


def fnt(bold, size):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def parse_dt(s):
    return dt.datetime.fromisoformat(s)


def ellipsize(d, text, font, max_w):
    if d.textlength(text, font=font) <= max_w:
        return text
    while text and d.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


def hour_float(t):
    return t.hour + t.minute / 60.0


def assign_slots(evs):
    """同一カラム内で時間が重なる予定に横スロット(0/1)を割り当てる (最大2)。"""
    slots = []  # (end_hourfloat, slot_index)
    result = {}
    active = []
    for e in sorted(evs, key=lambda e: e["_s"]):
        active = [a for a in active if a[0] > e["_s"]]
        used = {a[1] for a in active}
        slot = 0 if 0 not in used else (1 if 1 not in used else len(used))
        result[id(e)] = (slot, None)
        active.append((e["_e"], slot))
    # 各予定の同時最大スロット数を求めて幅を決める
    maxslot = {}
    for e in evs:
        cnt = 1
        for o in evs:
            if o is e:
                continue
            if o["_s"] < e["_e"] and e["_s"] < o["_e"]:
                cnt += 1
        maxslot[id(e)] = min(cnt, 2)
    for e in evs:
        s, _ = result[id(e)]
        result[id(e)] = (min(s, 1), maxslot[id(e)])
    return result


def draw_column(d, evs, col_x, col_w, start_h, end_h, body_top):
    label_w = 22
    ev_x0 = col_x + label_w
    ev_x1 = col_x + col_w - 3
    span = end_h - start_h
    ppx = (H - body_top - 4) / span   # px per hour
    f_hour = fnt(False, 12)
    f_time = fnt(False, 11)
    f_ev = fnt(False, 13)

    def y_of(hf):
        return body_top + (hf - start_h) * ppx

    # 時間目盛りと横線 (点線にして予定枠と区別)
    for h in range(start_h, end_h + 1):
        y = int(y_of(h))
        for x in range(ev_x0, ev_x1, 4):
            d.point((x, y), fill=0)
        d.text((col_x + 1, y - 6), f"{h}", font=f_hour, fill=0)

    # 予定帯 (左端に太い黒帯 + 細枠。時間線の点線と明確に区別)
    slots = assign_slots(evs)
    for e in evs:
        y0 = max(body_top, int(y_of(e["_s"])))
        y1 = min(H - 2, int(y_of(e["_e"])))
        if y1 - y0 < 15:
            y1 = y0 + 15
        slot, nslot = slots[id(e)]
        w_each = (ev_x1 - ev_x0) / max(nslot, 1)
        bx0 = int(ev_x0 + slot * w_each) + 1
        bx1 = int(ev_x0 + (slot + 1) * w_each) - 1
        d.rectangle([bx0, y0 + 1, bx1, y1 - 1], outline=0, width=1)
        d.rectangle([bx0, y0 + 1, bx0 + 3, y1 - 1], fill=0)  # 左アクセント帯
        st = e["_t"]
        tstr = f"{st.hour:02d}:{st.minute:02d}"
        d.text((bx0 + 7, y0 + 2), tstr, font=f_time, fill=0)
        title = ellipsize(d, e["title"], f_ev, bx1 - bx0 - 10)
        d.text((bx0 + 7, y0 + 14), title, font=f_ev, fill=0)


def render_day(events, today, now_str):
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)

    # ヘッダ帯
    d.rectangle([0, 0, W, HDR_H], fill=0)
    d.text((6, 4), f"{today.month}/{today.day}({WEEKJP[today.weekday()]})",
           font=fnt(True, 20), fill=255)
    upd = f"更新 {now_str}"
    fu = fnt(False, 13)
    d.text((W - 6 - d.textlength(upd, font=fu), 9), upd, font=fu, fill=255)

    # 当日の時間帯予定を左右カラム (境界 SPLIT 時) に振り分け
    allday = []
    left, right = [], []
    for e in events:
        if e.get("allDay"):
            allday.append(e)
            continue
        st = parse_dt(e["start"])
        if st.date() != today:
            continue
        en = parse_dt(e["end"]) if e.get("end") else st + dt.timedelta(hours=1)
        rec = {"title": e["title"], "_t": st,
               "_s": hour_float(st), "_e": hour_float(en)}
        (left if st.hour < SPLIT else right).append(rec)

    # 終日予定があればヘッダ直下に帯を1本追加し、その分だけ本体を下げる
    body_top = HDR_H + 2
    if allday:
        band_y0, band_y1 = HDR_H + 1, HDR_H + 1 + ALLDAY_H
        d.rectangle([0, band_y0, W, band_y1], outline=0, width=1)
        f_ad = fnt(True, 12)
        label = "終日: " + " / ".join(e["title"] for e in allday)
        label = ellipsize(d, label, f_ad, W - 8)
        d.text((4, band_y0 + 1), label, font=f_ad, fill=0)
        body_top = band_y1 + 2

    draw_column(d, left, 0, W // 2, DAY_START, SPLIT, body_top)
    d.line([(W // 2, body_top), (W // 2, H)], fill=0, width=1)  # 中央仕切り
    draw_column(d, right, W // 2 + 1, W // 2 - 1, SPLIT, DAY_END, body_top)
    return img


DEMO = [
    ("朝会 / スタンドアップ", "T09:30", "T10:00"),
    ("設計レビュー (会議室A)", "T11:00", "T12:00"),
    ("ランチ 田中さん", "T12:30", "T13:30"),
    ("メール処理", "T11:15", "T11:45"),
    ("顧客デモ 打ち合わせ", "T15:00", "T16:30"),
    ("1on1 佐藤さん", "T17:00", "T17:30"),
    ("チーム定例", "T17:00", "T18:00"),
]
DEMO_ALLDAY = ["健康診断"]


def expand_demo(today):
    out = []
    for title, s, e in DEMO:
        out.append({"title": title,
                    "start": f"{today.isoformat()}{s}:00",
                    "end": f"{today.isoformat()}{e}:00",
                    "allDay": False})
    for title in DEMO_ALLDAY:
        out.append({"title": title,
                    "start": f"{today.isoformat()}T00:00:00",
                    "end": f"{today.isoformat()}T00:00:00",
                    "allDay": True})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events")
    ap.add_argument("--today")
    ap.add_argument("--now", default=None, help="更新時刻 HH:MM")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("-o", "--out", default="calendar.png")
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    now_str = args.now or dt.datetime.now().strftime("%H:%M")
    events = expand_demo(today) if args.demo else json.load(open(args.events, encoding="utf-8"))

    img = render_day(events, today, now_str)
    img.save(args.out)
    print(f"saved {args.out} events={len(events)} today={today} now={now_str}")


if __name__ == "__main__":
    main()
