#!/usr/bin/env bash
# video2text.sh VIDEO OUTDIR [WHISPER_MODEL]
# CPU-only: ffmpeg (audio + deduplicated frames + contact sheets) -> tesseract OCR -> faster-whisper ASR
# Env: OCR_LANGS (default slv+hrv+ita+eng), ASR=0 to skip speech, ASR_LANG (e.g. sl; empty = auto-detect),
#      PY (python with faster-whisper installed), HF_HUB_OFFLINE=1 after models are cached.
set -euo pipefail
IN="$1"; OUT="${2:-out}"; MODEL="${3:-small}"
OCR_LANGS="${OCR_LANGS:-slv+hrv+ita+eng}"; ASR="${ASR:-1}"; ASR_LANG="${ASR_LANG:-}"; PY="${PY:-python3}"
mkdir -p "$OUT/frames" "$OUT/ocr" "$OUT/sheets"
FONT=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf

# 1) audio: 16 kHz mono PCM WAV (what Whisper/Parakeet expect)
ffmpeg -loglevel error -y -i "$IN" -vn -ac 1 -ar 16000 -c:a pcm_s16le "$OUT/audio.wav"

# 2) one decode pass: 1 fps -> drop near-duplicates (mpdecimate) -> (a) clean frames for OCR,
#    (b) grayscale 2x-upscaled copies for tesseract, (c) timestamped 4x4 contact sheets for a vision model.
#    File name = second of the video.
ffmpeg -loglevel error -y -i "$IN" -filter_complex \
 "[0:v]fps=1,mpdecimate=hi=64*48:lo=64*24:frac=0.5,split=3[a][o][b];\
  [a]scale=720:-2[f];\
  [o]scale=1440:-2:flags=lanczos,format=gray[g];\
  [b]scale=320:-2,drawtext=fontfile=$FONT:text='%{pts\:hms}':x=6:y=6:fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.6,tile=4x4:padding=4:color=white[s]" \
 -map "[f]" -fps_mode vfr -frame_pts 1 "$OUT/frames/t_%06d.jpg" \
 -map "[g]" -fps_mode vfr -frame_pts 1 -q:v 2 "$OUT/ocr/t_%06d.jpg" \
 -map "[s]" -fps_mode vfr "$OUT/sheets/sheet_%03d.jpg"

# 3) OCR + 4) ASR + merge
OUT="$OUT" OCR_LANGS="$OCR_LANGS" ASR="$ASR" ASR_LANG="$ASR_LANG" MODEL="$MODEL" "$PY" -I - <<'PYEOF'
import csv, difflib, glob, io, os, re, subprocess, time
out, langs = os.environ["OUT"], os.environ["OCR_LANGS"]
def hms(s): s = int(s); return f"{s//60:02d}:{s%60:02d}"

# OCR: tesseract TSV, keep words with conf >= 60, rebuild lines, dedupe across frames
t0, seen, ocr = time.time(), [], []
for fp in sorted(glob.glob(f"{out}/ocr/t_*.jpg")):
    sec = int(re.search(r"t_(\d+)", fp).group(1))
    tsv = subprocess.run(["tesseract", fp, "stdout", "-l", langs, "--psm", "11", "tsv"],
                         capture_output=True, text=True).stdout
    lines = {}
    for r in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if r["text"] and r["text"].strip() and float(r["conf"]) >= 60:
            lines.setdefault((r["block_num"], r["par_num"], r["line_num"]), []).append(r["text"])
    for words in lines.values():
        line = " ".join(words).strip()
        line = re.sub(r"°\s?[GCcO0]\b", "°C", line)  # common OCR slip on degree units
        if len(line) < 3 or sum(c.isalnum() for c in line) < 0.6 * len(line.replace(" ", "")):
            continue
        key = line.lower()
        if any(difflib.SequenceMatcher(None, key, k).ratio() > 0.85 for k in seen):
            continue
        seen.append(key); ocr.append((sec, line))
t_ocr = time.time() - t0

# ASR: faster-whisper, int8 on CPU, Silero VAD to skip music/silence
speech, info_txt, t_asr = [], "ASR skipped", 0.0
if os.environ.get("ASR", "1") == "1":
    from faster_whisper import WhisperModel
    t0 = time.time()
    model = WhisperModel(os.environ["MODEL"], device="cpu", compute_type="int8",
                         cpu_threads=os.cpu_count() or 4)
    segs, info = model.transcribe(f"{out}/audio.wav", language=os.environ.get("ASR_LANG") or None,
                                  beam_size=5, vad_filter=True,
                                  vad_parameters=dict(min_silence_duration_ms=500),
                                  condition_on_previous_text=False)
    speech = [(s.start, s.text.strip()) for s in segs]
    t_asr = time.time() - t0
    info_txt = f"language={info.language} p={info.language_probability:.2f} duration={info.duration:.0f}s speech={info.duration_after_vad:.0f}s"

with open(f"{out}/transcript.md", "w", encoding="utf-8") as f:
    f.write(f"# Transcript\n\nASR: {info_txt}\n\n## Speech\n")
    f.writelines(f"[{hms(t)}] {txt}\n" for t, txt in speech)
    f.write("\n## On-screen text (OCR, deduplicated)\n")
    f.writelines(f"[{hms(t)}] {txt}\n" for t, txt in ocr)
    f.write("\n## Contact sheets\n")
    f.writelines(f"- {p}\n" for p in sorted(glob.glob(f"{out}/sheets/*.jpg")))
print(f"OCR {len(ocr)} unique lines in {t_ocr:.1f}s; ASR {t_asr:.1f}s; -> {out}/transcript.md")
PYEOF
