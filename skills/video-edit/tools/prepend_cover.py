#!/usr/bin/env python3
"""把封面拼到已渲染好的 1080p 内容前面（不再解原片，省一次慢解码）。

用法：
  python3 prepend_cover.py <封面png> <内容mp4> <输出mp4>

产物：1.2 秒封面 + 内容。

铁律：拼接清单里的路径必须写绝对路径——相对路径会被 concat demuxer
按清单所在目录解析，拼出来只有封面 1.2 秒（实测教训）。
"""
import os
import subprocess
import sys

COVER = os.path.abspath(sys.argv[1])
CONTENT = os.path.abspath(sys.argv[2])
OUT = os.path.abspath(sys.argv[3])
OUTDIR = os.path.dirname(OUT)
CLIP = os.path.join(OUTDIR, "cover_clip.mp4")
LIST = os.path.join(OUTDIR, "concat_list.txt")


def main():
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-loop", "1", "-t", "1.2", "-i", COVER,
                    "-f", "lavfi", "-t", "1.2", "-i", "anullsrc=r=48000:cl=stereo",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-r", "30",
                    "-c:a", "aac", "-b:a", "128k",
                    "-shortest", CLIP], check=True)
    with open(LIST, "w") as f:
        f.write(f"file '{CLIP}'\nfile '{CONTENT}'\n")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stats",
                    "-f", "concat", "-safe", "0", "-i", LIST,
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-r", "30",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart", OUT], check=True)
    print("成片：", OUT, flush=True)


if __name__ == "__main__":
    main()
