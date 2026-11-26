#!/usr/bin/env python3
"""滚动字幕生成器：字幕布滚动模式（纯白字）。

版式（1080x1920）：左对齐 4 行滚动窗，上一句小字 / 当前句大字＋▶ /
下一句小字 / 下下一句小字（偏暗），每句开始时整窗向上滑一格（0.3 秒），
纯白字 + 黑色投影（Outline 0、Shadow 4），不加黑边。
大字按句限宽：140px 放不下的句按比例缩小（7 字句约 115px），不断句、不溢出。

短语文件 phrases.json（每句 ≤8 字，时间为原片时间轴，按转写段落逐字比例内插）：
  [{"text": "第一句", "start": 0.97, "end": 2.05}, ...]

用法：
  python3 gen_subs.py --segments work/segments.json --phrases work/phrases.json \\
      --out work/subs.ass [--fonts-dir ~/.fonts]

铁律：
  - ASS 时间一律 2 位百分秒（3 位毫秒会被 libass 误读成百分秒，字幕错位、串句、消失）
  - 短语起止落在被剪掉的静音里时，映射到下一保留段的起点（吸附规则），
    否则事件 Start > End 直接不渲染。
"""
import argparse
import json
import os

from PIL import ImageFont as _IF

# 位置（1080x1920）：左对齐 x=82，四档顶边 y：上一句 1080 / 当前句 1190 /
# 下一句 1360 / 下下一句 1480（小字高约 72px，大字高约 126px）
X = 82
SLOT_Y = [1080, 1190, 1360, 1480]
FS_SMALL = 80
FS_BIG = 140
GLIDE_MS = 300
DIM_ALPHA = "&H66&"  # 下下一句偏暗

# 大字按句限宽：▶ + 文本从 x=82 起，右缘留 40px，投影再占 4px；
# 140px 放不下的句按比例缩小，下限 110px。
_BIG_BUDGET = 954


def ass_time(sec):
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", required=True, help="pipe.py 产出的 segments.json")
    ap.add_argument("--phrases", required=True, help="短语 JSON：[{text, start, end}]，原片时间")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fonts-dir", default=os.path.expanduser("~/.fonts"))
    a = ap.parse_args()

    phrases = [(p["text"], float(p["start"]), float(p["end"]))
               for p in json.load(open(a.phrases, encoding="utf-8"))]
    big_font = _IF.truetype(os.path.join(a.fonts_dir, "SourceHanSansSC-Bold.otf"), FS_BIG)
    big_fs = []
    for t, _, _ in phrases:
        w = big_font.getlength("▶ " + t)
        big_fs.append(FS_BIG if w <= _BIG_BUDGET else max(110, int(FS_BIG * _BIG_BUDGET / w)))

    d = json.load(open(a.segments, encoding="utf-8"))
    keeps = d["keeps"]
    new_duration = d["new_duration"]

    # 原片时间 -> 剪后时间
    spans = []
    cum = 0.0
    for ks, ke in keeps:
        spans.append((ks, ke, cum))
        cum += ke - ks

    def cut(t):
        for ks, ke, base in spans:
            if ks <= t <= ke:
                return base + (t - ks)
        # 落在被剪掉的缝里：贴到最近的保留段边界
        if t < spans[0][0]:
            return 0.0
        prev_end = spans[0][1]
        prev_new = spans[0][2] + (spans[0][1] - spans[0][0])
        for ks, ke, base in spans[1:]:
            if prev_end <= t <= ks:
                return prev_new
            prev_end, prev_new = ke, base + (ke - ks)
        return new_duration

    starts = [cut(s) for _, s, _ in phrases]
    ends = [cut(e) for _, _, e in phrases]
    n = len(phrases)
    # T[i] = 第 i 句开始（剪后）；T[n] = 片尾
    T = starts + [new_duration]
    # 校验：单调
    for i in range(n):
        assert T[i] < T[i + 1], f"phrase {i} not monotonic: {T[i]} vs {T[i+1]}"
    print("phrases:", n, "cut span:", round(T[0], 2), "->", round(T[n], 2), flush=True)

    lines = []
    lines.append("[Script Info]")
    lines.append("ScriptType: v4.00+")
    lines.append("PlayResX: 1080")
    lines.append("PlayResY: 1920")
    lines.append("ScaledBorderAndShadow: yes")
    lines.append("")
    lines.append("[V4+ Styles]")
    lines.append("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
    lines.append("Style: Sub,Source Han Sans SC,80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,4,7,82,40,0,1")
    lines.append("")
    lines.append("[Events]")
    lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")

    def ev(start, end, text):
        if end - start < 0.05:
            return
        lines.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Sub,,0,0,0,,{text}")

    for i, (text, _, _) in enumerate(phrases):
        t_prev2 = T[i - 2] if i >= 2 else None
        t_prev1 = T[i - 1] if i >= 1 else None
        t_cur = T[i]
        t_next = T[i + 1]
        t_next2 = T[i + 2] if i + 2 <= n else None
        g = GLIDE_MS / 1000.0

        # 下下一句（偏暗小字）：从下方滑入 slot3
        if t_prev2 is not None:
            y_from = SLOT_Y[3] + 90
            ev(t_prev2, t_prev1,
               "{\\alpha&HFF&\\move(%d,%d,%d,%d,0,%d)\\t(0,%d,\\alpha%s)}%s" % (
                   X, y_from, X, SLOT_Y[3], GLIDE_MS, GLIDE_MS, DIM_ALPHA, text))
        # 下一句（小字）：slot3 -> slot2，偏暗 -> 全白
        if t_prev1 is not None:
            if i == 1:
                # 首屏：直接从下方滑入 slot2
                ev(t_prev1, t_cur,
                   "{\\alpha&HFF&\\move(%d,%d,%d,%d,0,%d)\\t(0,%d,\\alpha&H00&)}%s" % (
                       X, SLOT_Y[2] + 90, X, SLOT_Y[2], GLIDE_MS, GLIDE_MS, text))
            else:
                ev(t_prev1, t_cur,
                   "{\\alpha%s\\move(%d,%d,%d,%d,0,%d)\\t(0,%d,\\alpha&H00&)}%s" % (
                       DIM_ALPHA, X, SLOT_Y[3], X, SLOT_Y[2], GLIDE_MS, GLIDE_MS, text))
        # 当前句（大字＋▶）：slot2 -> slot1，字号 80 -> 按句限宽的大字
        if i == 0:
            ev(t_cur, t_next, "{\\fs%d\\pos(%d,%d)}▶ %s" % (big_fs[i], X, SLOT_Y[1], text))
        else:
            ev(t_cur, t_next,
               "{\\fs%d\\move(%d,%d,%d,%d,0,%d)\\t(0,%d,\\fs%d)}▶ %s" % (
                   FS_SMALL, X, SLOT_Y[2], X, SLOT_Y[1], GLIDE_MS, GLIDE_MS, big_fs[i], text))
        # 上一句（小字）：slot1 -> slot0，字号 按句限宽的大字 -> 80
        if t_next2 is not None:
            ev(t_next, t_next2,
               "{\\fs%d\\move(%d,%d,%d,%d,0,%d)\\t(0,%d,\\fs%d)}%s" % (
                   big_fs[i], X, SLOT_Y[1], X, SLOT_Y[0], GLIDE_MS, GLIDE_MS, FS_SMALL, text))
        # 退出：slot0 向上滑出并淡出
        if t_next2 is not None:
            ev(t_next2, t_next2 + g,
               "{\\move(%d,%d,%d,%d,0,%d)\\t(0,%d,\\alpha&HFF&)}%s" % (
                   X, SLOT_Y[0], X, SLOT_Y[0] - 90, GLIDE_MS, GLIDE_MS, text))

    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote", a.out, "events:", sum(1 for L in lines if L.startswith("Dialogue")), flush=True)


if __name__ == "__main__":
    main()
