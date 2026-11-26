#!/usr/bin/env python3
"""SenseVoice 全音频转写（定长分段版）：30 秒一段，规避整段解码的慢速。

用途：转写全文，作为字幕文字的权威来源（段级转写常有错字，须逐句听音校对）。

用法：
  python3 transcribe.py <音频文件> [输出txt] --model-dir <SenseVoice 模型目录>
  # 模型目录也可用环境变量 SENSEVOICE_MODEL_DIR 指定
"""
import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf
import sherpa_onnx

CHUNK = 30  # 秒


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out", nargs="?", default=None)
    ap.add_argument("--model-dir", default=os.environ.get("SENSEVOICE_MODEL_DIR"),
                    help="SenseVoice 模型目录（含 model.int8.onnx 与 tokens.txt）")
    a = ap.parse_args()
    if not a.model_dir:
        ap.error("须指定 --model-dir 或环境变量 SENSEVOICE_MODEL_DIR")
    src = a.src
    out = a.out if a.out else src + ".sv2.txt"
    wav = tempfile.mktemp(suffix=".wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-ar", "16000", "-ac", "1", wav], check=True)
    audio, sr = sf.read(wav, dtype="float32")
    if audio.ndim > 1:
        audio = audio[:, 0]
    print(f"音频: {len(audio)/sr:.0f} 秒", flush=True)

    rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=os.path.join(a.model_dir, "model.int8.onnx"),
        tokens=os.path.join(a.model_dir, "tokens.txt"),
        use_itn=True, num_threads=2,
    )
    step = CHUNK * sr
    lines, full = [], []
    for i in range(0, len(audio), step):
        seg = audio[i:i + step]
        s = rec.create_stream()
        s.accept_waveform(sr, seg)
        rec.decode_stream(s)
        t = s.result.text.strip()
        if t:
            m, sec = divmod(int(i / sr), 60)
            lines.append(f"[{m:02d}:{sec:02d}] {t}")
            full.append(t)
    text = "".join(full)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n=== 全文 ===\n" + text + "\n")
    print(f"段数: {len(lines)}，全文 {len(text)} 字")
    print(f"已输出: {out}")


if __name__ == "__main__":
    main()
