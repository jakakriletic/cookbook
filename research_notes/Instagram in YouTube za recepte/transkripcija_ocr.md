# Local CPU-only pipeline: cooking video -> speech transcript + keyframes + on-screen-text OCR (2025–2026)

Research context, 26 Nov 2026. Test container: Ubuntu 24.04, 4 vCPU, 15 GB RAM, Python 3.13.18, about 30 GB free disk. The pip and apt registries were reachable. huggingface.co, arxiv.org and YouTube hosts were refused by the session's network proxy (HTTP 403 / DNS not allowed). So no ASR model could be downloaded or run here. Everything that does not need a model was installed and run locally: ffmpeg, tesseract with slv/hrv/ita, the faster-whisper install with import, and the end-to-end script without the ASR step. Items marked "local test" were measured in this container on a synthetic 60 s 720x1280 30 fps H.264 "reel" with four 15 s scenes, Slovenian captions burned in with ffmpeg `drawtext`, and temporal noise. ASR speed figures are taken from published benchmarks or extrapolated, and are labelled as such.

## (a) Speech-to-text engine on CPU: faster-whisper vs whisper.cpp vs openai-whisper vs Parakeet/Canary/others

### Takeaway
Use **faster-whisper 1.2.1** (CTranslate2 4.9.1) with `compute_type="int8"` on CPU. It installs cleanly on Python 3.13, has Silero VAD built in, does word timestamps and language detection, and its int8 CPU speed is roughly on par with whisper.cpp. It is about 4x faster than openai-whisper. For Slovenian, prefer `large-v3-turbo` (or `large-v3` if time allows) over `small`/`medium`. NVIDIA Parakeet-TDT-0.6B-v3 via `onnx-asr` is much faster on CPU and covers Slovenian, Croatian and Italian. Its published Slovenian FLEURS WER is about 24%, against about 18% for Whisper large-v3, so it is a speed fallback, not the accuracy choice.

### Cited Findings
- faster-whisper official CPU benchmark (`small` model, beam 5, 8 threads, Intel Core i7-12700K, 13 min audio): openai/whisper fp32 6m58s / 2335 MB RAM; whisper.cpp fp32 2m05s / 1049 MB; whisper.cpp+OpenVINO 1m45s / 1642 MB; faster-whisper fp32 2m37s / 2257 MB; faster-whisper int8 **1m42s / 1477 MB**; faster-whisper int8 with `batch_size=8` **51 s / 3608 MB** — [SYSTRAN/faster-whisper README](https://github.com/SYSTRAN/faster-whisper)
  - In real-time terms (13 min = 780 s): int8 ≈ 7.6x real time, batched int8 ≈ 15x, openai-whisper ≈ 1.9x. This is computed from the table above.
- faster-whisper install: `pip install faster-whisper`. It needs Python ≥ 3.9, and FFmpeg is **not** required because audio is decoded with PyAV. It supports `vad_filter=True` (Silero), `word_timestamps=True` (`segment.words`), `info.language` / `info.language_probability`, and `BatchedInferencePipeline(model).transcribe(..., batch_size=16)`. `distil-large-v3` is supported, with `condition_on_previous_text=False` in the example — [faster-whisper README](https://github.com/SYSTRAN/faster-whisper)
- Local test (this container): `pip install faster-whisper==1.2.1` in a fresh Python 3.13 venv took 16 s. It pulled ctranslate2 4.9.1, onnxruntime 1.32.0, av 19.0.2, tokenizers 0.23.3, huggingface_hub 2.4.0 and numpy 2.5.5. **The venv takes 418 MB** (ctranslate2.libs 83 MB, onnxruntime 78 MB, av + av.libs 128 MB). `ctranslate2.get_supported_compute_types('cpu')` returned `{int8, int8_float32, int16, float32}`. Latest PyPI versions on 26 Nov 2026 were faster-whisper 1.2.1, ctranslate2 4.9.1, openai-whisper 20250625, pywhispercpp 1.5.1, onnx-asr 0.12.0, silero-vad 6.3 and nemo-toolkit 3.0.0. (Checked with `pip index versions`.) — [PyPI faster-whisper](https://pypi.org/project/faster-whisper/)
- Local test, from the installed faster-whisper source: the built-in model aliases are `tiny`, `base`, `small`, `medium` (each also as `.en`), `large-v1`, `large-v2`, `large-v3`/`large`, `distil-large-v2`, `distil-medium.en`, `distil-small.en`, `distil-large-v3`, `distil-large-v3.5` and `large-v3-turbo`/`turbo`.
  - `turbo` maps to the HF repo `mobiuslabsgmbh/faster-whisper-large-v3-turbo`.
  - The standard models map to `Systran/faster-whisper-<size>`, and `distil-large-v3.5` maps to `distil-whisper/distil-large-v3.5-ct2`.
  - `WhisperModel(..., cpu_threads=0 /* "4 by default" */, num_workers=1, download_root=None, local_files_only=False)`.
  - `WhisperModel.transcribe` takes `multilingual` ("Perform language detection on every segment"), `language_detection_segments=1`, `hotwords` and `initial_prompt`.
  - On `BatchedInferencePipeline.transcribe` the defaults are `vad_filter=True` and `batch_size=8`.
  - — [faster_whisper/utils.py & transcribe.py (SYSTRAN/faster-whisper)](https://github.com/SYSTRAN/faster-whisper)
- OpenAI Whisper model table:

  | Model | Parameters | VRAM | Relative speed vs large (A100) |
  |---|---|---|---|
  | tiny | 39M | ~1 GB | ~10x |
  | base | 74M | ~1 GB | ~7x |
  | small | 244M | ~2 GB | ~4x |
  | medium | 769M | ~5 GB | ~2x |
  | large | 1550M | ~10 GB | 1x |
  | turbo | 809M | ~6 GB | ~8x |

  - `turbo` is "an optimized version of large-v3" with "minimal accuracy loss". It is **not trained for translation**.
  - openai-whisper requires the `ffmpeg` CLI, and its code is "expected to be compatible" with Python 3.8–3.11.
  - — [openai/whisper README](https://github.com/openai/whisper)
- whisper.cpp ggml model sizes (disk / RAM): tiny 75 MiB / ~273 MB; base 142 MiB / ~388 MB; small 466 MiB / ~852 MB; medium 1.5 GiB / ~2.1 GB; large 2.9 GiB / ~3.9 GB.
  - Build: `cmake -B build && cmake --build build -j --config Release`. Models: `sh ./models/download-ggml-model.sh <name>`, which includes `large-v3-turbo`.
  - Quantize: `./build/bin/quantize in.bin out-q5_0.bin q5_0`. Word-level timestamps: `-ml 1`.
  - Silero VAD: `--vad -vm <model>`, downloaded with `./models/download-vad-model.sh silero-v6.2.0`, with tunables `--vad-threshold`, `--vad-min-silence-duration-ms` and others.
  - Python binding: `abdeladim-s/pywhispercpp`, among others.
  - — [ggml-org/whisper.cpp README](https://github.com/ggml-org/whisper.cpp)
- onnx-asr (ONNX Runtime, no PyTorch/NeMo): `pip install onnx-asr[cpu,hub]`, Python 3.11–3.14.
  - Supported models: NeMo Parakeet v2 (English) and v3 (multilingual), Canary v1/v2, GigaAM, Kaldi/Vosk Zipformer, Whisper and others.
  - Long-form audio is handled with VAD, and token-level timestamps are available.
  - CPU RTFx on a Ryzen 9800X3D: **Parakeet v2/v3 = 36**, Canary v2 = 8. On a Cortex-A53: Parakeet 1.0.
  - — [istupakov/onnx-asr README](https://github.com/istupakov/onnx-asr)
- GPU-only data point for large-v3-turbo in faster-whisper: int8, beam 5 on an RTX 2080 Ti, LibriSpeech-clean, 19.6 s, 1545 MB, WER 1.92%. No official CPU benchmark for turbo was found. — [faster-whisper issue #1030](https://github.com/SYSTRAN/faster-whisper/issues/1030)

### Inferences
- **Recommended default for this project:** faster-whisper `large-v3-turbo`, int8, `vad_filter=True`. Pass `language="sl"` / `"hr"` / `"it"` / `"en"` whenever the creator's language is known. Run `small` int8 as a quick first pass, or for English/Italian content where Whisper is already strong.
- **Expected CPU speed on 2–4 cores** (extrapolated from the 8-thread i7-12700K numbers, not measured here):
  - Container vCPUs are usually slower per thread, so assume roughly 2–3x slower on 4 vCPUs and 4–6x slower on 2.
  - `small` int8 (non-batched) ≈ 3–4x real time on 4 vCPU. A 60 s reel takes about 15–25 s plus model load; a 10 min video about 2.5–4 min.
  - `large-v3-turbo` keeps the full 32-layer large-v3 encoder and cuts the decoder to 4 layers. On CPU the encoder dominates, so expect turbo to be about 4–6x slower than `small`: roughly 0.6–1x real time on 4 vCPU. That is about 1–1.5 min for a 60 s reel and 10–17 min for 10 min of speech.
  - `large-v3` (32-layer decoder) is slower still, plausibly 0.3–0.5x real time on 4 vCPU.
  - VAD cuts all of these in proportion to the non-speech share, such as music-only intros.
- **Batched faster-whisper** roughly halves wall time (51 s vs 1m42s) but uses about 2.4x the RAM. With 15 GB RAM that is fine, but on a small container keep `batch_size` at 4–8.
- whisper.cpp is a good choice if you want a single static binary without a Python stack. It needs a C++ build (cmake, g++) and has no advantage in accuracy. openai-whisper pulls in PyTorch (GBs of disk), is about 4x slower on CPU and documents Python ≤ 3.11, so do not use it here.
- distil-whisper models (`distil-large-v3`, `distil-large-v3.5`) are, to my knowledge, trained for **English only**. They do not suit Slovenian, Croatian or Italian. (This is from prior knowledge of the distil-whisper project and was not re-verified in this session.)
- **CT2 model disk sizes.** faster-whisper's Systran repos store fp16 weights, so size ≈ params × 2 bytes (inferred from the parameter counts above, not measured): small ≈ 0.5 GB, medium ≈ 1.5 GB, turbo ≈ 1.6 GB, large-v3 ≈ 3.1 GB. Peak disk for the venv plus one turbo model is about 2–2.5 GB, which fits "a few GB".

### Gaps
- No measured CPU real-time factor for faster-whisper `large-v3-turbo` or `large-v3` on 2–4 cores was found. Web results were GPU-only or unsourced blog numbers. Benchmark it in the target container once huggingface.co is allowed.
- Parakeet-TDT-0.6B-v3 and Canary-1B-v2 model cards (huggingface.co) and the arXiv paper could not be opened from this session, because both hosts were blocked. Their exact ONNX download size, whether automatic language identification exists, and the maximum clip length were not verified.
- Vosk: not researched in depth. I found no evidence of a current Slovenian Vosk model, so it is not recommended.

## (a2) Accuracy for Slovenian (vs Croatian, Italian, English), language detection, word timestamps, VAD

### Takeaway
Whisper large-v3's Slovenian WER is about 18% on FLEURS and about 17% on Common Voice 15, roughly 4–5x worse than English (4.1%) or Italian (3.0%). Croatian sits in between at 10.8%. Expect usable but imperfect Slovenian transcripts: wrong case endings and mangled rare words are common. Numbers and units spoken aloud should be cross-checked against on-screen OCR. Parakeet v3 is worse on Slovenian at about 24% FLEURS WER.

### Cited Findings
- Whisper large-v3 WER read from the official language-breakdown chart (values extracted from the SVG's text labels):

  | Language | FLEURS WER | Common Voice 15 WER |
  |---|---|---|
  | Italian | 3.0% | 5.5% |
  | English | 4.1% | 9.3% |
  | Slovak | 9.2% | 23.4% |
  | Czech | 10.1% | 9.0% |
  | Croatian | 10.8% | not in CV15 chart |
  | Serbian | 11.6% | 15.7% |
  | Bosnian | 13.0% | — |
  | **Slovenian** | **18.3%** | **16.8%** |

  — [openai/whisper language-breakdown.svg](https://github.com/openai/whisper/blob/main/language-breakdown.svg)
  - Caveat: the chart plots both large-v3 and large-v2 bars but carries one set of numeric labels (61 labels for 61 FLEURS languages). These are presumed to be the large-v3 values.
- Parakeet-TDT-0.6B-v3 FLEURS WER: Croatian 12.46%, Slovenian 24.03%, Czech 11.01%, as reported by the paper's per-language table. The model card gives an average of 11.97% over 25 languages, using greedy decoding with no LM. — [arXiv 2509.14128 (Canary-1B-v2 & Parakeet-TDT-0.6B-v3)](https://arxiv.org/pdf/2509.14128); [nvidia/parakeet-tdt-0.6b-v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)
  - These came from a search-engine summary. arxiv.org and huggingface.co were blocked here, so the table could not be opened directly.
  - A GGUF build (Parakeet-Air) reports similar numbers on its own setup: Croatian 12.92% and Slovenian 24.44%. — [webAI-Official/Parakeet-Air](https://huggingface.co/webAI-Official/Parakeet-Air)
- A community Whisper-large-v3 Slovenian fine-tune (BuzzASR) reports FLEURS 17.52% WER / 4.98% CER, and zero-shot large-v3 CER of 5.43% on FLEURS. Its Common Voice 25 WER of 1.8% likely reflects in-domain training data. — [BuzzASR/slovenian model card](https://huggingface.co/BuzzASR/slovenian) (via search snippet)
- A vendor comparison (ElevenLabs marketing) lists Whisper large-v3 at 26.7% WER for Slovenian. The test set is not stated, so treat it as unverified. — [ElevenLabs Slovenian STT](https://elevenlabs.io/speech-to-text/slovenian)
- faster-whisper language detection exposes `info.language` and `info.language_probability`. By default it uses only the first 30 s window (`language_detection_segments=1`); `multilingual=True` detects the language per segment. — [faster-whisper README & source](https://github.com/SYSTRAN/faster-whisper)
- faster-whisper VAD:
  - The Silero model ships inside the wheel as `faster_whisper/assets/silero_vad_v6.onnx` (1.2 MB), so **VAD needs no download**. (Local test.)
  - The README says the default only removes silence > 2 s, and you can tune it with `vad_parameters=dict(min_silence_duration_ms=500)`.
  - Defaults in `vad.py`: `threshold=0.5`, `min_speech_duration_ms=0`, `min_silence_duration_ms=2000`, `speech_pad_ms=400`.
  - — [faster-whisper README & vad.py](https://github.com/SYSTRAN/faster-whisper)

### Inferences
- **Set the language explicitly** whenever possible (`language="sl"`). Auto-detection on a 15–30 s reel that starts with music, or with a few Slovenian words, can plausibly flip to Croatian, Serbian or Slovak. Those are close languages with much more Whisper training data, and they have better WER, so the model is "attracted" to them. Log `language_probability` and re-run with a forced language when p < ~0.8.
- **Prompting with domain vocabulary** may help with Slovenian inflected culinary terms such as "žlica, ščepec, smetana, °C, dag". Use `initial_prompt="Recept: 200 g moke, 2 žlici sladkorja, pečemo pri 180 °C."` or `hotwords`. This is not benchmarked.
- **Music handling.** Use `vad_filter=True` with a lower `min_silence_duration_ms` (300–500) and `condition_on_previous_text=False`. This combination is the usual mitigation for Whisper hallucinating text such as subtitle credits or "thanks for watching" over music. Silero can still treat singing as speech. Inferred, not tested.
- For quantities and temperatures, the on-screen OCR is more reliable than ASR on Slovenian. The agent should treat ASR numbers as hints and OCR numbers as primary when both exist.

### Gaps
- Per-language WER for `large-v3-turbo` on Slovenian is not published in the sources found. Its degradation relative to large-v3 on low-resource languages is therefore unknown.
- Whisper paper Appendix D tables (FLEURS WER per model size, tiny→large-v2, for Slovenian) could not be opened (arxiv.org blocked). It is unknown how much worse `small`/`medium` are on Slovenian. They are expected to be substantially worse than large.
- No benchmark on *cooking-video* audio (music beds, kitchen noise) in Slovenian was found.

## (a3) Where models are downloaded from; pre-download and offline caching

### Takeaway
All Whisper/CT2/ggml/Parakeet models come from the Hugging Face Hub. Allow `huggingface.co` plus the Xet storage hosts `cas-bridge.xethub.hf.co`, `cas-server.xethub.hf.co` and `transfer.xethub.hf.co`, and optionally the legacy LFS CDN hosts. Download once with `hf download ... --local-dir`, then run with `HF_HUB_OFFLINE=1` and a local path. pip (pypi.org / files.pythonhosted.org) and apt are separate and were already reachable.

### Cited Findings
- Hugging Face staff asked users behind firewalls to allowlist `cas-bridge.xethub.hf.co`, `transfer.xethub.hf.co` and `cas-server.xethub.hf.co`. — [HF forum: list of download redirections to whitelist](https://discuss.huggingface.co/t/how-to-get-a-list-of-all-huggingface-download-redirections-to-whitelist/30486)
  - EU-region variants (`cas-server.xethub-eu.hf.co`, `transfer.xethub-eu.hf.co`) are under a different parent domain. That is per a community analysis, not official HF documentation.
- Hub `resolve/` URLs redirect to `cas-bridge.xethub.hf.co` after the LFS→Xet migration. — [HF blog: Migrating the Hub from Git LFS to Xet](https://huggingface.co/blog/migrating-the-hub-to-xet)
- Even with `HF_HUB_DISABLE_XET=1`, one user saw the client still contact `cas-bridge.xethub.hf.co`. — [HF forum: CAS service error with HF_HUB_DISABLE_XET=1](https://discuss.huggingface.co/t/cas-service-error-when-downloading-gated-models-on-databricks-even-with-hf-hub-disable-xet-1/164793)
- An enterprise air-gap allowlist (Cloudera) lists all three xethub hosts. — [Cloudera ML Model Hub air-gap allowlist](https://docs.cloudera.com/machine-learning/1.5.5/model-hub/topics/ml-model-hub-air-gap-installation.html)
- whisper.cpp downloads `ggml-*.bin` from huggingface.co (repo `ggerganov/whisper.cpp`) and VAD models from `huggingface.co/ggml-org/whisper-vad`. — [whisper.cpp README](https://github.com/ggml-org/whisper.cpp)
- faster-whisper downloads CTranslate2 models from the HF Hub (Systran org), or loads them from a local directory. — [faster-whisper README](https://github.com/SYSTRAN/faster-whisper)
- onnx-asr loads models from HF or local directories. — [onnx-asr README](https://github.com/istupakov/onnx-asr)
- Local test: in this session `huggingface.co:443` was refused by the egress proxy (HTTP 403). `WhisperModel('small')` failed with `ProxyError 403 Forbidden`, so **the environment must allow HF before first use**.
- Local test: `hf download REPO --local-dir DIR [--include PATTERN]` is available in huggingface_hub 2.4.0. faster-whisper downloads only `config.json`, `preprocessor_config.json`, `model.bin`, `tokenizer.json` and vocabulary files.

### Inferences
- Exact hostnames to request:
  - `huggingface.co`
  - `cas-bridge.xethub.hf.co`, `cas-server.xethub.hf.co`, `transfer.xethub.hf.co`
  - Legacy LFS CDN: `cdn-lfs.huggingface.co`, `cdn-lfs-us-1.hf.co`. These are only needed for repos not yet on Xet. Hostnames are from the forum thread and prior knowledge, so verify against a live redirect.
- Pre-download commands:
  ```bash
  pip install faster-whisper==1.2.1            # brings huggingface_hub (hf CLI)
  hf download Systran/faster-whisper-small --local-dir /opt/models/fw-small
  hf download mobiuslabsgmbh/faster-whisper-large-v3-turbo --local-dir /opt/models/fw-turbo
  export HF_HUB_OFFLINE=1                       # never touch the network afterwards
  python -c "from faster_whisper import WhisperModel; WhisperModel('/opt/models/fw-turbo', device='cpu', compute_type='int8')"
  ```
  Alternative: `WhisperModel('large-v3-turbo', download_root='/opt/models', local_files_only=True)` after the first online run.
- Store models outside `work/` and outside Git, because they are 0.5–3 GB, for example in `~/.cache/huggingface` or `/opt/models`.
- Observed side note: during this session the proxy also refused `www.youtube.com`, `redirector.googlevideo.com`, `rr1---sn-….googlevideo.com` and `i.ytimg.com` (triggered by a concurrent process). YouTube media comes from per-node `*.googlevideo.com` hosts, and cloud environment allowlists here accept exact hostnames only, not wildcards. Video download may therefore need unrestricted network access, or the user supplies the file. This is relevant to the download researchers.

### Gaps
- No current official Hugging Face page listing all download hostnames was found. The list above is assembled from staff forum replies and third-party docs (2025).

## (b) ffmpeg: audio extraction, keyframes, de-duplication, contact sheets

### Takeaway
One ffmpeg decode pass is enough. Sample at `fps=1`, drop near-duplicates with `mpdecimate`, then `split` into (1) colour frames for a vision model, (2) grayscale 2x-upscaled frames for OCR and (3) timestamped `tile` contact sheets. Scene detection with `select='gt(scene,0.3)'` is fragile. In the local test it missed every cut, so use it only as a complement, with a lower threshold.

### Cited Findings (all local tests in this container, ffmpeg 6.1.1-3ubuntu5 from Ubuntu 24.04 apt)
- Audio to Whisper format: `ffmpeg -i in.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le audio.wav`. It took 0.26 s for 60 s of video and produced 1.9 MB.
- `fps=1,mpdecimate=hi=64*48:lo=64*24:frac=0.5` reduced 60 frames to **4, exactly one per scene**, despite per-frame noise. The decode pass took about 6.9 s for 60 s of 720x1280 30 fps video on 4 vCPU. The synthetic video has heavy noise, so it is expensive to decode.
- Scene detection `-vf "select='gt(scene,0.3)'" -fps_mode vfr` found **0 of 3 cuts**. `metadata=print:key=lavfi.scene_score` showed scores at the cuts of only **0.12, 0.10 and 0.09**, and `scdet=threshold=10` also found none.
  - Cause: cuts between similarly bright shots with noise produce low scene scores. Real footage with stronger cuts scores higher, but the threshold must be tuned (0.1–0.2), or frame sampling should be used instead.
- Keyframe-only decode: `ffmpeg -skip_frame nokey -i in.mp4 -fps_mode vfr key_%04d.jpg` took **0.37 s** (about 18x faster than a full decode) and gave 8 frames. Keyframe placement depends on the encoder (GOP), so it is a cheap pre-scan, not a content-aware selection.
- Contact sheet: `-vf "fps=1/5,scale=360:-2,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='%{pts\:hms}':x=8:y=8:fontsize=22:fontcolor=yellow:box=1:boxcolor=black@0.6,tile=4x3:padding=4:color=white" -frames:v 1 sheet.jpg` produced a **1452x1928 JPEG of 90 KB** covering 12 timestamped frames.
- `-frame_pts 1` after `fps=1` names files by the second of the video (`t_000015.jpg` = 0:15), which keeps the OCR timestamps aligned with the ASR timestamps.
- PySceneDetect 0.7.3 is current on PyPI as an alternative scene detector (`pip install scenedetect`). It was not tested here. — [PyPI scenedetect](https://pypi.org/project/scenedetect/)

### Inferences
- Recommended frame policy for recipe videos: `fps=1` plus `mpdecimate` as the primary method, because captions change on a time scale of seconds. For long 10–15 min videos, use `fps=0.5`. Optionally add a scene pass at `gt(scene,0.15)` to catch fast cuts shorter than 1 s.
- Vertical 9:16 sheets get tall fast. Vision models downscale large images, so burned-in text on sheets becomes unreadable. Use sheets only for visual context (plating, technique, texture), and send OCR text plus a few full-resolution frames for detail.
- For a 10 min video with about 600 sampled frames, expect mpdecimate to keep roughly 100–300 frames in a typical talking-head or cooking video. This is a guess and depends on camera movement. Handheld footage defeats mpdecimate; then raise `hi`/`lo`, or sample at `fps=0.5`.

### Gaps
- ffmpeg.org documentation pages were not fetched (the host is likely blocked); filter syntax was verified by actually running it.
- No real Instagram or YouTube cooking video could be tested (YouTube hosts blocked). Scene-score distributions on real reels are unknown.

## (c) OCR of burned-in captions: tesseract vs PaddleOCR / RapidOCR / EasyOCR; de-duplication

### Takeaway
**Tesseract 5.3.4 from Ubuntu apt with `slv+hrv+ita+eng`** works offline and is small (about 3–4 MB per language). It read Slovenian diacritics (č, š, ž) and °C correctly once frames were converted to grayscale and upscaled 2x, at about 0.2–0.5 s per frame on CPU. PaddleOCR's PP-OCRv5 Latin model (Slovenian and Croatian included) via RapidOCR/ONNX is the stronger option for stylised captions on busy backgrounds. It needs extra model downloads and was not tested here.

### Cited Findings
- Local test: `apt-get install tesseract-ocr tesseract-ocr-slv tesseract-ocr-hrv tesseract-ocr-ita` on Ubuntu 24.04 installed tesseract **5.3.4-1build5**. Language packs are version **1:4.1.0-2**.
  - traineddata sizes: slv 3.0 MB, hrv 4.1 MB, ita 2.7 MB, eng 4.1 MB, osd 10.6 MB.
  - `tesseract --list-langs` lists `eng hrv ita osd slv`.
  - — [Ubuntu packages: tesseract-ocr-slv (noble)](https://packages.ubuntu.com/noble/tesseract-ocr-slv)
- Local test, caption accuracy:
  - On the bottom 35% crop, upscaled 2x and grayscale, `-l slv+eng --psm 6` read "200 g moke tip 500", "Pecite 25 min na 180 °C" and "3 žlice sladkorja in ščep soli" exactly, at 0.18–0.26 s per image.
  - `-l eng` alone gave "3 **z**lice sladkorja in **S**cep soli", losing the diacritics. **The `slv` model is required for č/š/ž.**
- Local test, preprocessing matters:
  - On a brown background, the raw 720 px colour frame returned **nothing**.
  - Grayscale gave "200'g moke: tip 500". Grayscale + 2x Lanczos upscale gave "200 g moke tip 500" (correct).
  - A white-text threshold mask also worked, but turned "°C" into `"C`.
  - On a full 1440 px gray frame with `--psm 11` (sparse text) and 4 languages, the reads were all correct except "°C" → "°G", which the script normalises.
  - Speed was 0.35–0.48 s per frame with 4 languages.
- PP-OCRv5 multilingual recognition: the Latin-script model `latin_PP-OCRv5_mobile_rec` lists Croatian (`hr`) and Slovenian (`sl`) among its Latin languages. It is described as covering about 32 Latin languages and scores 84.7 on PaddleOCR's internal Latin benchmark, with no per-language breakdown. — [PaddleOCR PP-OCRv5 multi-language docs](https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html)
- A community ONNX repackaging runs the PP-OCRv5 Latin model with RapidOCR on CPU, with "no PaddlePaddle, no CUDA". It uses `latin/latin_PP-OCRv5_mobile_rec.onnx` plus `ppocrv5_latin_dict.txt` with a detection model. — [monkt/paddleocr-onnx](https://huggingface.co/monkt/paddleocr-onnx) (via search snippet)
- Current PyPI versions (26 Nov 2026): rapidocr 3.10.0, rapidocr-onnxruntime 1.2.3, paddleocr 3.7.0 and easyocr 1.7.2 (checked with `pip index versions`). — [PyPI rapidocr](https://pypi.org/project/rapidocr/)

### Inferences
- **Recommended OCR stack:** tesseract first. It is tiny, apt-installable and needs no model hosts, which suits the restricted network. Escalate to RapidOCR with the PP-OCRv5 Latin ONNX models if captions are stylised (outlines, gradients, curved or animated text) and tesseract misses them. EasyOCR pulls in PyTorch (large disk) and is the least attractive on a disk-limited CPU box.
- **De-duplication:**
  1. `mpdecimate` removes identical frames.
  2. Per-line fuzzy de-duplication drops a line if `difflib.SequenceMatcher` ratio > 0.85 against any line already seen.
  3. Keep the **first timestamp** of each line.
  4. Drop lines with < 60% alphanumerics, and words with tesseract confidence < 60.

  This kept exactly 4 unique caption lines from the test reel.
- Text cut off at the frame edge cannot be recovered. In the test, the caption "Čokoladna krema: 150 ml smetane" was rendered wider than the frame, and OCR returned "koladna krema: 150 ml smeta". This is a test artefact, but real reels also crop captions on the sides. The vision model or ASR has to fill the gap, and the recipe should mark it "za dopolnitev", not guessed.
- Normalise common OCR slips for recipe units after OCR: `°G/°c/°O → °C`, `0` vs `O` in "100 g", `l` vs `1` in "1 l".

### Gaps
- No head-to-head CPU benchmark of tesseract vs RapidOCR vs PaddleOCR on Slovenian burned-in captions was found. RapidOCR/PaddleOCR install size and per-frame CPU time were not measured, because their model hosts were not reachable or not tested.
- Whether RapidOCR 3.x auto-downloads models from a host other than huggingface.co (for example ModelScope) was not verified. It matters for the allowlist.

## (d) End-to-end script and timings (60 s reel, 10 min video, 2–4 CPU cores)

### Takeaway
A single bash + Python script was written and tested locally. It runs one ffmpeg pass (audio + deduplicated frames + OCR frames + contact sheets), tesseract TSV OCR with fuzzy de-duplication and faster-whisper ASR, and merges everything into `transcript.md` with `[mm:ss]` timestamps. Without ASR it processed the 60 s test reel in **9.2–9.4 s on 4 vCPU**. With `small` int8 ASR, expect about 30–45 s per 60 s reel; with `large-v3-turbo`, about 1.5–2 min. These ASR figures are extrapolated.

### Cited Findings
- Local test, the script below with `ASR=0` on the 60 s synthetic reel:
  - Total 9.2–9.4 s. The ffmpeg pass took about 7 s; OCR took 2.0 s for 4 unique frames with 4 languages.
  - Output: 4 unique timestamped caption lines; 1 contact sheet; audio.wav 1.9 MB; frames 632 KB; OCR frames 1.6 MB.
  - `bash -n` syntax check passed.
- ASR timing basis: faster-whisper `small` int8 at 7.6x real time and batched int8 at 15x on 8 threads of an i7-12700K. — [faster-whisper README](https://github.com/SYSTRAN/faster-whisper)

Install (Ubuntu 24.04; venv 418 MB measured, apt packages not measured; roughly 0.5–0.7 GB in total without models):
```bash
sudo apt-get install -y --no-install-recommends ffmpeg tesseract-ocr tesseract-ocr-slv tesseract-ocr-hrv tesseract-ocr-ita fonts-dejavu-core
python3 -m venv ~/venv-asr && ~/venv-asr/bin/pip install faster-whisper==1.2.1   # 418 MB venv, Python 3.13 OK
# once HF is allowed:
~/venv-asr/bin/hf download mobiuslabsgmbh/faster-whisper-large-v3-turbo --local-dir /opt/models/fw-turbo
# run (offline):
HF_HUB_OFFLINE=1 PY=~/venv-asr/bin/python ASR_LANG=sl bash video2text.sh reel.mp4 work/reel1 /opt/models/fw-turbo
```

`video2text.sh` (tested end-to-end except the ASR block, which could not download a model here):
```bash
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

# 2) one decode pass: 1 fps -> drop near-duplicates (mpdecimate) -> (a) colour frames for viewing,
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
```

Actual test output (`transcript.md`, OCR section) on the synthetic reel:
```
[00:00] 200 g moke tip 500
[00:15] Pecite 25 min na 180 °C
[00:30] 3 žlice sladkorja in ščep soli
[00:45] koladna krema: 150 ml smeta      <- caption itself was wider than the frame in the test video
```

### Inferences
Approximate wall-clock times. Only the 60 s non-ASR figures were measured; everything else is extrapolated.

| Step | 60 s reel, 4 vCPU | 60 s reel, 2 vCPU | 10 min video, 4 vCPU | 10 min video, 2 vCPU |
|---|---|---|---|---|
| Audio extract | 0.3 s (measured) | <1 s | 2–3 s | 3–5 s |
| ffmpeg frames pass (1080p source) | 5–10 s (7 s measured at 720p) | 10–20 s | 1–2 min | 2–4 min |
| Tesseract OCR (0.35–0.5 s/frame) | 2–10 s (4–20 unique frames) | 4–20 s | 1–2.5 min (150–300 frames) | 2–5 min |
| ASR faster-whisper `small` int8 | 15–25 s + ~2 s load | 30–50 s | 2.5–4 min | 5–8 min |
| ASR `large-v3-turbo` int8 | ~1–1.5 min | ~2–3 min | ~10–17 min | ~20–35 min |
| ASR Parakeet v3 (onnx-asr) | a few s | ~10 s | ~1–2 min | ~2–4 min |
| **Total (turbo)** | **~1.5–2 min** | **~3–4 min** | **~13–22 min** | **~25–45 min** |

- For long videos, VAD typically removes intro, outro and music-only parts. Batched inference (`BatchedInferencePipeline`, `batch_size=4–8`) should roughly halve ASR time, at about 2.4x the RAM.
- Practical two-tier strategy for the agent:
  1. Run `small` (or Parakeet v3) to get a quick draft and language ID.
  2. Re-run `large-v3-turbo` with the forced language only for Slovenian or Croatian videos, or when the draft is poor.
  3. Always run OCR, because amounts and temperatures often appear only on screen.
- All intermediate files (audio.wav, frames, OCR frames, sheets) belong in `work/` (git-ignored per project rules). Only the final `transcript.md` and a source note go into `reference/`.

### Gaps
- No ASR run was possible in this session (huggingface.co blocked), so the ASR block of the script is untested at runtime. Its API calls match the installed faster-whisper 1.2.1 source: `info.duration_after_vad`, `vad_parameters`, `language`, `condition_on_previous_text`.
- Timings for real 1080x1920 Instagram/YouTube files and real Slovenian speech remain to be measured once HF and the video sources are reachable.
