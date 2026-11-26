#!/usr/bin/env python3
"""一遍渲染：切气口（逐段 trim+concat）→ 缩到 1080x1920 → 烧字幕 → 可选前面拼 1.2 秒封面。

用法：
  python3 render.py --video raw.mov --segments work/segments.json \\
      --subs work/subs.ass --out out/content.mp4 [--fonts-dir ~/.fonts]
  python3 render.py --video raw.mov --segments work/segments.json \\
      --subs work/subs.ass --out out/final.mp4 --cover work/cover.png

注意：4K HEVC 在普通云主机上解码约 0.09–0.15 倍速，全量渲染一次约 4–12 分钟。
封面也可事后用 prepend_cover.py 拼，避免重复解码原片。
"""
import argparse
import json
import os
import subprocess

COVER_DUR = 1.2


def build_filter(keeps, subs_ass, fonts_dir, with_cover=True):
    n = len(keeps)
    parts = []
    for i, (s, e) in enumerate(keeps):
        parts.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]")
    vconcat = "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vcut]"
    aconcat = "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[acut]"
    parts.append(vconcat)
    parts.append(aconcat)
    parts.append("[vcut]scale=1080:1920,subtitles="
                 + subs_ass.replace(":", "\\:")
                 + ":fontsdir=" + fonts_dir.replace(":", "\\:")
                 + "[vsub]")
    if not with_cover:
        return ";".join(parts), "[vsub]", "[acut]"
    parts.append("[1:v]scale=1080:1920,format=yuv420p,fps=30[cov]")
    parts.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{COVER_DUR}[asil]")
    parts.append("[cov][vsub]concat=n=2:v=1:a=0[vout]")
    parts.append("[asil][acut]concat=n=2:v=0:a=1[aout]")
    return ";".join(parts), "[vout]", "[aout]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="口播原片")
    ap.add_argument("--segments", required=True, help="pipe.py 产出的 segments.json")
    ap.add_argument("--subs", required=True, help="gen_subs.py 产出的 subs.ass")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cover", default=None, help="封面 PNG；不给则只渲染内容")
    ap.add_argument("--fonts-dir", default=os.path.expanduser("~/.fonts"))
    a = ap.parse_args()

    with open(a.segments, encoding="utf-8") as f:
        keeps = json.load(f)["keeps"]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    fc, vmap, amap = build_filter(keeps, os.path.abspath(a.subs), a.fonts_dir,
                                  with_cover=a.cover is not None)
    cmd = ["ffmpeg", "-y", "-v", "error", "-stats",
           "-i", a.video]
    if a.cover:
        cmd += ["-loop", "1", "-t", str(COVER_DUR), "-i", a.cover]
    cmd += ["-filter_complex", fc,
            "-map", vmap, "-map", amap,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", a.out]
    print("渲染中（4K 解码 + 1080p 编码，约几分钟）...", flush=True)
    subprocess.run(cmd, check=True)
    print("成片：", a.out, flush=True)


if __name__ == "__main__":
    main()
