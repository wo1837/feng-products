#!/usr/bin/env python3
"""视频日记封面生成器（竖版 1080x1920）。

版式（1080x1920，PSD 模板实测）：
  底图        全幅照片（用当日视频帧）
  品牌角标    左上：四角黄色引号框（248x248，框位 x=78, y=201）+
              系列名白字（185x202，框位 x=110, y=224），两行排列
  版权        固定文案（默认 ©Copyright 2026），强调色，常规体，
              字宽 263px，x=72，字顶 y=465
  日期        每日变量，白色粗体，字宽 304px，右沿 x=999，字顶 y=225
  天数        每日变量，白色粗体，字宽 432px，右沿 x=1000，字顶 y=312
  标题1       白色常规体，字宽 536px，x=77，字顶 y=1214
  标题2       强调色粗体，字宽 956px，x=73，字顶 y=1365
  文字处理    标题/日期/天数/版权：白字/强调色字 + 黑色软投影（模糊+下移），不加黑描边
              系列名：白字 + 黑色硬描边
  颜色        默认强调色青色 #00FFFC；引号框黄色 #FFFF00

角标与系列名均由代码绘制，不依赖图片素材。

用法：
  python3 make_cover.py --bg frame.png \\
      --title1 第一排标题 --title2 第二排标题 \\
      --date 2026/11/25 --day Day001 --out cover.png
  python3 make_cover.py --bg frame.png --title1 ... --title2 ... \\
      --date ... --day ... --out cover.png \\
      --diary-text 视频日记 --copyright "©Copyright 2026 我的品牌" --accent FF4502
"""
import argparse
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WHITE = (255, 255, 255)
YELLOW = (245, 254, 0)
BLACK = (0, 0, 0)


def hex_rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def fit_size(text, font_path, target_w):
    """按可见字形宽度反推字号：先以 100 号渲染量宽，再等比缩放。"""
    f100 = ImageFont.truetype(font_path, 100)
    tmp = Image.new("L", (2000, 300), 0)
    d = ImageDraw.Draw(tmp)
    d.text((10, 10), text, font=f100, fill=255)
    bbox = tmp.getbbox()
    w0 = bbox[2] - bbox[0]
    return max(10, int(100 * target_w / w0))


def glyph_bbox(text, font_path, size):
    font = ImageFont.truetype(font_path, size)
    tmp = Image.new("L", (1400, size + 80), 0)
    d = ImageDraw.Draw(tmp)
    d.text((10, 10), text, font=font, fill=255)
    bbox = tmp.getbbox()
    return font, bbox[0] - 10, bbox[1] - 10, bbox[2] - bbox[0], bbox[3] - bbox[1]


def shadow_text(base, text, font_path, size, fill, x, glyph_top_y):
    """在 base 上按字形顶 y 精确定位画一行字：黑字层模糊+下移作软投影，再画彩字。"""
    font, gx0, gy0, w, h = glyph_bbox(text, font_path, size)
    pad = size // 4 + 10
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.text((pad - gx0, pad - gy0), text, font=font, fill=(0, 0, 0, 255))
    blur = max(2, size // 12)
    off = max(2, size // 20)
    shadow = layer.filter(ImageFilter.GaussianBlur(blur))
    # 字形包围盒左上在 layer 内正好是 (pad, pad)，所以粘贴点 = 目标 - pad
    base.alpha_composite(shadow, (x - pad, glyph_top_y - pad + off))
    top = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    td = ImageDraw.Draw(top)
    td.text((pad - gx0, pad - gy0), text, font=font, fill=fill + (255,))
    base.alpha_composite(top, (x - pad, glyph_top_y - pad))
    return w


def shadow_text_right(base, text, font_path, size, fill, right_x, glyph_top_y):
    """右对齐版本：先量宽再算 x。"""
    font, gx0, gy0, w, h = glyph_bbox(text, font_path, size)
    return shadow_text(base, text, font_path, size, fill, right_x - w, glyph_top_y)


def draw_corner_brackets(base, x, y, size=248, arm=46, stroke=9, yellow=YELLOW):
    """画四角黄色引号框：每个角一个 L 形，臂长 arm、线宽 stroke，外沿 1px 黑边。

    实测（PSD 模板导出）：248x248 框内，臂长 46px、线宽 9px、黄色 (245,254,0)。
    """
    d = ImageDraw.Draw(base)
    for ox, oy, dx, dy in [(x, y, 1, 1), (x + size - 1, y, -1, 1),
                           (x, y + size - 1, 1, -1), (x + size - 1, y + size - 1, -1, -1)]:
        # 黑底 L 比黄 L 每边大 1px、外移 1px，形成 1px 描边
        for (a, s, fill, off) in [(arm + 2, stroke + 2, BLACK + (255,), 1),
                                  (arm, stroke, yellow + (255,), 0)]:
            bx, by = ox - dx * off, oy - dy * off
            # 横臂
            hx0 = bx if dx > 0 else bx - a + 1
            hy0 = by if dy > 0 else by - s + 1
            d.rectangle([hx0, hy0, hx0 + a - 1, hy0 + s - 1], fill=fill)
            # 竖臂
            vx0 = bx if dx > 0 else bx - s + 1
            vy0 = by if dy > 0 else by - a + 1
            d.rectangle([vx0, vy0, vx0 + s - 1, vy0 + a - 1], fill=fill)


def draw_series_name(base, text, font_path, x, y, w, h):
    """画系列名（默认“视频日记”）：两行排列，白字 + 黑色硬描边，居中于 w x h 框内。

    与 shadow_text 同一套定位法：先量字形包围盒，再把字层贴到目标字顶，
    保证墨迹顶边精确落在 y 与 y + h - 字形高。
    """
    half = len(text) // 2
    lines = [text[:half], text[half:]] if len(text) >= 2 else [text]
    size = fit_size(lines[0], font_path, w)
    stroke = max(3, size // 12)
    # 每行按自己的字形高算顶边（不同汉字的墨迹高差几 px，共用一行会偏）
    tops = []
    for i, line in enumerate(lines):
        if i == 0:
            tops.append(y)
        else:
            _, _, _, _, gh = glyph_bbox(line, font_path, size)
            tops.append(y + h - gh)
    _, _, _, _, gh = glyph_bbox(lines[0], font_path, size)
    pad = size // 4 + 10
    tops = [y, y + h - gh]
    for line, top in zip(lines, tops):
        font, gx0, gy0, lw, lh = glyph_bbox(line, font_path, size)
        layer = Image.new("RGBA", (lw + pad * 2, lh + pad * 2), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.text((pad - gx0, pad - gy0), line, font=font, fill=WHITE + (255,),
                stroke_width=stroke, stroke_fill=BLACK + (255,))
        lx = x + (w - lw) // 2
        base.alpha_composite(layer, (lx - pad, top - pad))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bg", required=True, help="底图：1080x1920 当日视频帧")
    ap.add_argument("--title1", required=True)
    ap.add_argument("--title2", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--day", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fonts-dir", default=os.path.expanduser("~/.fonts"))
    ap.add_argument("--diary-text", default="视频日记", help="左上系列名")
    ap.add_argument("--copyright", default="©Copyright 2026",
                    help="版权行文案")
    ap.add_argument("--accent", default="00FFFC", help="强调色 hex，如 00FFFC")
    a = ap.parse_args()

    reg = os.path.join(a.fonts_dir, "SourceHanSansSC-Regular.otf")
    bold = os.path.join(a.fonts_dir, "SourceHanSansSC-Bold.otf")
    accent = hex_rgb(a.accent)

    base = Image.open(a.bg).convert("RGBA")
    assert base.size == (1080, 1920), base.size

    # 固定：黄框角标 + 系列名
    draw_corner_brackets(base, 78, 201)
    draw_series_name(base, a.diary_text, bold, 110, 224, 185, 202)

    # 版权（固定）：强调色常规体，宽 263，x=72，字顶 y=465
    s = fit_size(a.copyright, reg, 263)
    shadow_text(base, a.copyright, reg, s, accent, 72, 465)
    # 日期（每日变量）：白色粗体，宽 304，右沿 999，字顶 y=225
    s = fit_size(a.date, bold, 304)
    shadow_text_right(base, a.date, bold, s, WHITE, 999, 225)
    # 天数（每日变量）：白色粗体，宽 432，右沿 1000，字顶 y=312
    s = fit_size(a.day, bold, 432)
    shadow_text_right(base, a.day, bold, s, WHITE, 1000, 312)
    # 标题1：白色常规体，宽 536，x=77，字顶 y=1214
    s = fit_size(a.title1, reg, 536)
    shadow_text(base, a.title1, reg, s, WHITE, 77, 1214)
    # 标题2：强调色粗体，宽 956，x=73，字顶 y=1365
    s = fit_size(a.title2, bold, 956)
    shadow_text(base, a.title2, bold, s, accent, 73, 1365)

    base.convert("RGB").save(a.out)
    print("saved", a.out, os.path.getsize(a.out), "bytes")


if __name__ == "__main__":
    main()
