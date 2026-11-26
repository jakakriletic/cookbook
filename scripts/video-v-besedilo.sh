#!/usr/bin/env bash
# video-v-besedilo.sh POVEZAVA_ALI_DATOTEKA [IZHODNA_MAPA]
#
# Iz povezave na YouTube/Instagram ali iz lokalne video datoteke pripravi besedilo za agenta:
#   opis.txt          opis (caption) objave
#   *.vtt             podnapisi YouTube (ročni in samodejni), če obstajajo
#   transcript.md     prepis govora (faster-whisper large-v3-turbo) in besedilo s slike (tesseract OCR)
#   sheets/*.jpg      kontaktne sličice za ogled kadrov
# Vse gre v work/video/<id>/ (ni v Gitu). Medije po prevodu v recept izbriši.
#
# Omejitve okolja (glej reference/video-orodja-2026-11-26.md):
#   - Opis in podnapisi potrebujejo samo www.youtube.com oz. www.instagram.com.
#   - Zvok in slika prihajata z dinamičnih CDN gostiteljev (googlevideo.com, cdninstagram.com),
#     ki jih omejeni omrežni seznam ne dovoli; tedaj pošlji datoteko ali jo prenesi na svojem računalniku.
#   - YouTube iz podatkovnega centra pogosto vrne »Sign in to confirm you're not a bot«; pomagajo
#     piškotki (COOKIES=pot/do/cookies.txt) ali zagon na lastnem računalniku.
# Okoljske spremenljivke: ASR_LANG (privzeto samodejno; za slovenščino sl), COOKIES, MODEL.
set -uo pipefail
VIR="$1"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL="${MODEL:-$ROOT/work/modeli/large-v3-turbo}"
YTDLP=(python3 -m yt_dlp --js-runtimes node --no-playlist -t sleep)
[ -n "${COOKIES:-}" ] && YTDLP+=(--cookies "$COOKIES")

if [ -f "$VIR" ]; then
  ID="$(basename "${VIR%.*}")"; OUT="${2:-$ROOT/work/video/$ID}"; mkdir -p "$OUT"
  VIDEO="$VIR"
else
  ID="$(python3 -m yt_dlp --get-id --skip-download "$VIR" 2>/dev/null | head -1)"
  [ -z "$ID" ] && ID="$(echo "$VIR" | sed -E 's#.*/(reel|p|shorts)/([^/?]+).*#\2#; s#.*[?&]v=([^&]+).*#\1#; s#.*youtu\.be/([^?]+).*#\1#')"
  OUT="${2:-$ROOT/work/video/$ID}"; mkdir -p "$OUT"
  echo "== Opis in podnapisi"
  "${YTDLP[@]}" --skip-download --write-info-json --write-description \
    --write-subs --write-auto-subs --sub-langs "sl,sl-orig,en,en-orig,hr,it" --sub-format "vtt/best" \
    -o "$OUT/%(id)s.%(ext)s" "$VIR" 2>&1 | grep -E "ERROR|Writing|Destination" || true
  [ -f "$OUT/$ID.description" ] && cp "$OUT/$ID.description" "$OUT/opis.txt"
  echo "== Prenos zvoka in slike"
  "${YTDLP[@]}" -f "b[height<=720]/bv*[height<=720]+ba/b" -o "$OUT/video.%(ext)s" "$VIR" 2>&1 | grep -E "ERROR|Destination|Merging" || true
  VIDEO="$(ls "$OUT"/video.* 2>/dev/null | head -1)"
fi

if [ -n "${VIDEO:-}" ] && [ -f "$VIDEO" ]; then
  if [ ! -f "$MODEL/model.bin" ]; then
    echo "== Prenos modela large-v3-turbo (enkrat, približno 1,6 GB)"
    python3 -c "from huggingface_hub import snapshot_download as s; s('mobiuslabsgmbh/faster-whisper-large-v3-turbo', local_dir='$MODEL')"
  fi
  echo "== Prepis govora in branje besedila s slike"
  HF_HUB_OFFLINE=1 ASR_LANG="${ASR_LANG:-}" "$ROOT/scripts/video2text.sh" "$VIDEO" "$OUT" "$MODEL"
else
  echo "Zvoka in slike ni bilo mogoče prenesti. Uporabni so opis in podnapisi, če obstajajo;"
  echo "za prepis pošlji video datoteko in zaženi: scripts/video-v-besedilo.sh pot/do/videa.mp4"
fi
echo "== Rezultat v $OUT"; ls "$OUT"
