# 口播视频一键剪辑 SKILL（竖版）

每天录一条口播原片，一键剪出竖版成片：去气口 + 四行滚动字幕 + 视频日记封面。
录制一条过，剪辑一条过，不在这上面磨时间。

## 实测成绩

首条成片上线当日 **500 播放，拿到平台推荐**。

## 适合谁

- 每天做口播、知识分享的短视频博主，想把剪辑变成固定流程
- 有自己的 AI 助手（Claude Code、Codex、Cursor、WorkBuddy 等，国内用 WorkBuddy 的多）可执行 Skill 的人
- 认同“顺便做视频”：每天只录一遍，不返工、不精修

## 免费版（本仓库直接下载）

- `SKILL.md`：完整剪辑标准 v1.0，Agent 通用格式（Claude Code、Codex、Cursor、WorkBuddy 等都能用）
- `tools/`：完整可运行工具包，6 个脚本 + 短语文件示例，开箱即用（见下节）
  - 切气口规则：间隔 >0.5s 只留 0.15s 尾巴，≤0.5s 全留
  - 滚动字幕：4 行滚动窗、纯白字 + 黑色投影、大字按句限宽
  - 视频日记封面：固定品牌角标 + 版权行，每日只换日期、天数、标题
  - 铁律：ASS 时间 2 位百分秒、remap 吸附、concat 绝对路径、改版必换文件名
  - 验片清单：新帧抽验 + 全程逐秒字幕核对

环境要求：ffmpeg 8.x、Python 3 + sherpa-onnx + soundfile + Pillow、SenseVoice 中文转写模型、思源黑体。

## 工具包（tools/，免费下载即用）

- `pipe.py`：静音检测 + 分段转写 + 切气口，产出 segments.json
- `transcribe.py`：全音频转写，字幕文字的权威来源
- `gen_subs.py`：四行滚动字幕生成（ASS）
- `render.py`：按切点渲染 1080x1920 内容
- `make_cover.py`：视频日记封面生成（角标、系列名均由代码绘制，不依赖图片素材）
- `prepend_cover.py`：1.2s 封面 + 内容拼成片
- `phrases.example.json`：短语文件格式示例

快速上手（按顺序跑，完整命令见 SKILL.md 工具用法一节）：

```bash
export SENSEVOICE_MODEL_DIR=<SenseVoice 模型目录>
python3 tools/pipe.py 原片.mov work/
python3 tools/transcribe.py work/audio_16k.wav work/transcript.txt
python3 tools/gen_subs.py --segments work/segments.json --phrases work/phrases.json --out work/subs.ass
python3 tools/render.py --video 原片.mov --segments work/segments.json --subs work/subs.ass --out out/content.mp4
python3 tools/make_cover.py --bg work/frame.png --title1 第一排 --title2 第二排 --date 2026/11/25 --day Day001 --out work/cover.png
python3 tools/prepend_cover.py work/cover.png out/content.mp4 out/成片.mp4
```

## 现阶段免费

刚开始，不收费，免费使用。

## 版本

- v1.0（2026-11-25）：首版定版，已用真实口播视频完整跑通并验收
