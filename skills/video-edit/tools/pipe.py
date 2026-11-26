#!/usr/bin/env python3
"""口播剪辑管线：静音检测 -> 分段转写 -> 切气口 -> 生成切后字幕时间轴。

用法：
  python3 pipe.py <视频> <工作目录> --model-dir <SenseVoice 模型目录>
  # 模型目录也可用环境变量 SENSEVOICE_MODEL_DIR 指定

产物（写进 <工作目录>）：audio_16k.wav, segments.json, keeplist.txt, subs.srt
阈值：静音判定 noise=-40dB 最短 0.3s；气口 >0.5s 切到只留 0.15s；<=0.5s 全留。
注意：转写只给段级时间戳，字幕时间以语音段边界为准；SenseVoice 模型只加载一次。
文字以全音频转写（transcribe.py）为准，段级转写常有错字，须逐句听音校对。
"""
import argparse
import json
import os
import re
import subprocess
import sys

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {r.stderr[-2000:]}")
    return r


def probe_duration(path):
    r = run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path])
    return float(r.stdout.strip())


def extract_audio(video, wav):
    run([FFMPEG, "-y", "-v", "error", "-i", video, "-ar", "16000", "-ac", "1", wav])


def detect_silences(video):
    r = subprocess.run([FFMPEG, "-i", video, "-af", "silencedetect=noise=-40dB:d=0.3",
                        "-f", "null", "-"], capture_output=True, text=True)
    starts = re.findall(r"silence_start: ([\d.]+)", r.stderr)
    ends = re.findall(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", r.stderr)
    return [(float(s), float(e)) for s, (e, _d) in zip(starts, ends)]


def build_segments(duration, silences, min_seg=0.2, min_gap=0.15):
    segs = []
    cur = 0.0
    for s, e in silences:
        if s - cur >= min_seg:
            segs.append([cur, s])
        cur = e
    if duration - cur >= min_seg:
        segs.append([cur, duration])
    merged = []
    for sg in segs:
        if merged and sg[0] - merged[-1][1] < min_gap:
            merged[-1][1] = sg[1]
        else:
            merged.append(sg)
    return merged


def transcribe_segments(wav, segments, model_dir):
    import soundfile as sf
    import sherpa_onnx
    audio, sr = sf.read(wav, dtype="float32")
    if audio.ndim > 1:
        audio = audio[:, 0]
    rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=os.path.join(model_dir, "model.int8.onnx"),
        tokens=os.path.join(model_dir, "tokens.txt"),
        use_itn=True, num_threads=2)
    out = []
    for s, e in segments:
        i0, i1 = int(s * sr), int(e * sr)
        st = rec.create_stream()
        st.accept_waveform(sr, audio[i0:i1])
        rec.decode_stream(st)
        out.append({"start": round(s, 3), "end": round(e, 3),
                    "text": st.result.text.strip()})
    return out


def cut_plan(segments, cut_thresh=0.5, keep_gap=0.15):
    """返回 keep 区间 [(start, end)] 和 old->new 时间映射。"""
    keeps = []
    for i, (s, e) in enumerate(segments):
        if i + 1 < len(segments):
            gap = segments[i + 1][0] - e
            tail = keep_gap if gap > cut_thresh else gap
        else:
            tail = 0.0
        keeps.append((s, e + tail))
    mapping = []
    t = 0.0
    for s, e in keeps:
        mapping.append((s, e, t))
        t += e - s
    new_duration = t

    def remap(x):
        for s, e, ns in mapping:
            if s <= x <= e:
                return ns + (x - s)
        for s, e, ns in mapping:
            if x < s:
                return ns
        return new_duration

    return keeps, remap, new_duration


def fmt_srt(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("work")
    ap.add_argument("--model-dir", default=os.environ.get("SENSEVOICE_MODEL_DIR"),
                    help="SenseVoice 模型目录（含 model.int8.onnx 与 tokens.txt）")
    a = ap.parse_args()
    if not a.model_dir:
        ap.error("须指定 --model-dir 或环境变量 SENSEVOICE_MODEL_DIR")
    video, work = a.video, a.work
    os.makedirs(work, exist_ok=True)
    dur = probe_duration(video)
    print(f"时长: {dur:.1f}s", flush=True)
    wav = os.path.join(work, "audio_16k.wav")
    extract_audio(video, wav)
    sil = detect_silences(video)
    print(f"静音段: {len(sil)}", flush=True)
    segs = build_segments(dur, sil)
    print(f"语音段: {len(segs)}", flush=True)
    transcribed = transcribe_segments(wav, segs, a.model_dir)
    keeps, remap, new_dur = cut_plan(segs)
    print(f"切后时长: {new_dur:.1f}s（原 {dur:.1f}s，去掉 {dur - new_dur:.1f}s）", flush=True)
    with open(os.path.join(work, "segments.json"), "w", encoding="utf-8") as f:
        json.dump({"duration": dur, "new_duration": new_dur,
                   "segments": transcribed, "keeps": keeps}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(work, "keeplist.txt"), "w") as f:
        for s, e in keeps:
            f.write(f"{s:.3f} {e:.3f}\n")
    with open(os.path.join(work, "subs.srt"), "w", encoding="utf-8") as f:
        n = 1
        for seg in transcribed:
            if not seg["text"]:
                continue
            ns, ne = remap(seg["start"]), remap(seg["end"])
            f.write(f"{n}\n{fmt_srt(ns)} --> {fmt_srt(ne)}\n{seg['text']}\n\n")
            n += 1
    print("产物已写入", work, flush=True)


if __name__ == "__main__":
    main()
