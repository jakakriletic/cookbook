# Orodja za Instagram Reels in YouTube — 26. 11. 2026

Uporabnik bo pošiljal povezave na Reels in YouTube videe s tehnikami, ki jih je treba prevesti v knjigo. Raziskava: `reports/Instagram in YouTube za recepte.md` (zapiski v `research_notes/Instagram in YouTube za recepte/`).

## Uporaba
- `scripts/video-v-besedilo.sh POVEZAVA` — opis, podnapisi in (če omrežje dovoli) prenos medija ter prepis. Za slovenski govor `ASR_LANG=sl`.
- `scripts/video-v-besedilo.sh pot/do/videa.mp4` — lokalna datoteka (npr. ki jo pošlje uporabnik): prepis govora (faster-whisper large-v3-turbo, int8, CPU) in branje besedila s slike (tesseract slv+hrv+ita+eng), kontaktne sličice v `sheets/` za vizualni pregled.
- Rezultati v `work/video/<id>/` (ni v Gitu); medije po prevodu izbriši. V knjigo gre samo predelan recept z virom.
- Količine in temperature iz napisov v sliki (OCR) imajo prednost pred prepisom govora.

## Okolje `cookbook`
- Dovoljeni gostitelji za video: www.youtube.com, consent.youtube.com, i.ytimg.com, www.instagram.com; za model: huggingface.co, cas-bridge/cas-server/transfer.xethub.hf.co, us.aws.cdn.hf.co.
- Namestitveni skript okolja: tesseract (slv, hrv, ita), ffmpeg, yt-dlp[default,curl-cffi], faster-whisper, huggingface_hub, av<16 (av 19 ne deluje s faster-whisper 1.2.1). Model (1,6 GB) se prenese ob prvi uporabi v `work/modeli/`.

## Preizkusi 26. 11. 2026
- Lokalna veriga: testni 9-sekundni video s sintetiziranim slovenskim govorom in napisi — OCR brezhiben (»300 g moke«, »Pečica 180 °C«), prepis govora razumljiv kljub umetnemu glasu; skupaj 10 s.
- YouTube (Short ydQx5pOdMwE): »Sign in to confirm you're not a bot« že pri opisu in podnapisih (IP podatkovnega centra). Zaobhajanja z menjavanjem odjemalcev nisem poskušal.
- Instagram (3 Reelsi uporabnika): opis in metapodatki prek www.instagram.com brez prijave; mediji s scontent-ord5-1/-2.cdninstagram.com (dodana kot točna gostitelja). Prenos, prepis in OCR delujejo; obdelava 40–75 s na Reel. Če nov Reel uporabi drug CDN gostitelj, ga pokaže `yt-dlp -J` (polje url formatov) in ga je treba dodati.

## Odprte možnosti (odločitev uporabnika)
1. Uporabnik pošlje video datoteko (najzanesljivejše).
2. Remote Control: prenos z yt-dlp na uporabnikovem računalniku (domači IP), obdelava tukaj.
3. Piškotki sekundarnega računa YouTube/Instagram (`COOKIES=cookies.txt`) — tveganje blokade računa; pogoji storitev samodejni prenos prepovedujejo.
4. Neomejeno omrežje za prenos medija s CDN — bot-preverjanje YouTuba ostane.
