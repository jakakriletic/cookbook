# Extracting YouTube videos and Shorts from a headless, allowlist-proxied cloud container (state: 26 Nov 2026)

Scope: getting (a) metadata and description, (b) manual, automatic and auto-translated subtitles, (c) audio for local transcription, (d) thumbnails and frames from a YouTube or Shorts link. The setting is a headless Linux container on a datacenter IP whose HTTPS proxy allows only exact hostnames.

Note on verification: "local inspection" means I read the installed package source in this container (yt-dlp 2026.10.26 at `/usr/local/lib/python3.13/site-packages/yt_dlp/`, and the youtube-transcript-api 1.2.5 wheel downloaded from PyPI). "Local test" means a curl or pip command run from this container on 2026-11-26. **No end-to-end download from YouTube could be run.** The session proxy refuses `www.youtube.com` (CONNECT 403), and WebFetch fails on it too, so none of the commands below have been tested against YouTube from here.

## 1. yt-dlp in 2026: version, install, flags for metadata, subtitles, audio and thumbnails, Shorts

### Takeaway
Use the newest stable yt-dlp (**2026.11.23**) installed as `pip install -U "yt-dlp[default]"`, which pulls in `yt-dlp-ejs`, together with a JavaScript runtime. Deno is the default runtime. Node 22, already in this container, works with `--js-runtimes node`. Without a JS runtime, YouTube extraction is "deprecated" and falls back to a single client (`visionos`). Shorts URLs (`/shorts/ID`) and `youtu.be/ID` are handled by the normal YouTube extractor.

### Cited Findings
- The latest yt-dlp on PyPI is 2026.11.23. The previous releases are 2026.10.26, 2026.10.21, 2026.8.19 and so on. Current helper packages: `yt-dlp-ejs` 0.8.0, `bgutil-ytdlp-pot-provider` 2.0.2, `youtube-transcript-api` 1.2.5, `deno` 2.9.8 (also on PyPI), `curl-cffi` 0.17.0. — local test: `pip index versions …` on 2026-11-26 against [PyPI yt-dlp](https://pypi.org/project/yt-dlp/)
- This container already has yt-dlp 2026.10.26, ffmpeg (`/usr/bin/ffmpeg`), Node v22.23.4 and Python 3.13. It has no deno, no yt-dlp-ejs and no youtube-transcript-api. — local test, 2026-11-26
- 2026.11.23 YouTube changes: "Add `ios_producer` player client", "Temporarily remove `web` from default clients", "Use `tv` as default `player_js_variant`", "Fix `web_embedded` client policies and deprioritize". In 2026.10.21: "Add `tv_samsung` client", "Set `tv_samsung` as a default client". In 2026.08.19: "Add `visionos` player client", "Remove `android_vr` from default clients". In 2026.10.26, minimum Python is 3.11. — [yt-dlp releases](https://github.com/yt-dlp/yt-dlp/releases)
- A third-party guide says that on 17 Aug 2026 many users suddenly got 403 errors, that yt-dlp dropped the affected client from its defaults, and that the fix shipped in 2026.08.19. This shows how fast the defaults change, so always update first. — [VideoProc guide (secondary source)](https://www.videoproc.com/resource/yt-dlp-not-working.htm)
- "To download from YouTube, yt-dlp needs to solve JavaScript challenges presented by YouTube using an external JavaScript runtime." Supported runtimes: deno ≥ 2.3.0 (recommended, **only one enabled by default**), node ≥ 22.0.0 (`--js-runtimes node`), quickjs (`--js-runtimes quickjs`, older versions can take minutes), bun (deprecated). For pip installs: `pip install -U "yt-dlp[default]"`. Alternatives: `--remote-components ejs:npm` (deno or bun only) or `ejs:github` (downloads from github.com/yt-dlp/ejs). — [yt-dlp wiki: EJS](https://github.com/yt-dlp/yt-dlp/wiki/EJS)
- In installed 2026.10.26, the default clients are `('tv_samsung', 'visionos', 'web')`. With no JS runtime they are `('visionos',)`. With login cookies they are `('web_embedded', 'tv_samsung', 'web')`, and for Premium `('web_creator', 'tv_samsung', 'web')`. Without a runtime, yt-dlp warns: "YouTube extraction without a JS runtime has been deprecated, and some formats may be missing." — local inspection of `yt_dlp/extractor/youtube/_video.py` (lines 143–147, 2969–3000), [GitHub source](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/youtube/_video.py)
- The yt-dlp README lists ffmpeg/ffprobe as "Required for merging separate video and audio files" and yt-dlp-ejs as "Required for full YouTube support". curl_cffi is "recommended". — [yt-dlp README](https://github.com/yt-dlp/yt-dlp/blob/master/README.md)
- Subtitle flags (README):
  - `--write-subs`, `--write-auto-subs` (alias `--write-automatic-subs`), `--list-subs`
  - `--sub-format FORMAT` ("e.g. "srt" or "ass/srt/best"")
  - `--sub-langs LANGS` ("can be regex" or "all", e.g. `--sub-langs "en.*,ja"`, `--sub-langs all,-live_chat`)
  - `--convert-subs` (ass, lrc, srt, vtt)

  — [yt-dlp README](https://github.com/yt-dlp/yt-dlp/blob/master/README.md)
- YouTube subtitle formats known to the extractor: `('json3', 'srv1', 'srv2', 'srv3', 'ttml', 'srt', 'vtt')`. Auto-translated tracks are requested with a `tlang` parameter unless `--extractor-args "youtube:skip=translated_subs"` is set. The original speech-recognition track gets an extra **`-orig`** label (e.g. `en-orig`, "so that it can be distinguished"). — local inspection of `_video.py` (line 142, lines ~4244–4330)
- Other youtube extractor args (README):
  - `lang`: preferred translated title/description
  - `skip=hls,dash,translated_subs`
  - `player_client` (`default`, `all`, `-client` to exclude)
  - `player_skip=webpage,configs,js,initial_data`: fewer requests but possibly missing formats
  - `po_token=CLIENT.CONTEXT+TOKEN` with contexts `gvs`, `player`, `subs`
  - `fetch_pot=auto|always|never`
  - `innertube_host`, `visitor_data`

  — [yt-dlp README](https://github.com/yt-dlp/yt-dlp/blob/master/README.md)
- Shorts: the YouTube `_VALID_URL` matches `(v|embed|e|shorts|live)/` paths and bare `youtu.be/xxxx`. The test cases include `https://www.youtube.com/shorts/BGQWPY4IigY`. — local inspection of `_video.py` (lines 99, 108, 1140)
- Thumbnails: yt-dlp builds candidates as `https://i.ytimg.com/vi{_webp}/{video_id}/{name}.{jpg|webp}` for these names: `maxresdefault, hq720, sddefault, hqdefault, 0, mqdefault, default, sd1–3, hq1–3, mq1–3, 1, 2, 3`. A source comment says "the *1,*2,*3 thumbnails … are not the custom thumbnail", meaning they are auto-generated stills from the video. — local inspection of `_video.py` (lines 4113–4124)
- Audio presets: `-t mp3` = `-f 'ba[acodec^=mp3]/ba/b' -x --audio-format mp3`; `-t aac` is similar. — [yt-dlp README](https://github.com/yt-dlp/yt-dlp/blob/master/README.md)

### Inferences
- **Recommended install** (not run against YouTube here):
  ```bash
  python3 -m pip install -U "yt-dlp[default]"          # 2026.11.23 + yt-dlp-ejs; replaces the older 2026.10.26
  python3 -m pip install -U deno                        # optional: makes deno (default runtime) available; otherwise use --js-runtimes node
  python3 -m pip install -U youtube-transcript-api      # 1.2.5, fallback for transcripts only
  # optional, only if PO tokens turn out to be needed:
  python3 -m pip install -U bgutil-ytdlp-pot-provider   # 2.0.2; script mode needs node>=22 or deno>=2
  ```
  Everything installs from PyPI, so github.com is not needed. Do not use `--remote-components ejs:github`.
- **Suggested config file** (`~/.config/yt-dlp/config` or `--config-location`):
  ```
  --js-runtimes node          # only if deno is not installed (Node 22.23.4 is present)
  --no-playlist
  -t sleep                    # = --sleep-subtitles 5 --sleep-requests 0.75 --sleep-interval 10 --max-sleep-interval 20
  -o work/yt/%(id)s.%(ext)s
  ```
- **(a) Metadata and description, no media hosts touched:**
  ```bash
  yt-dlp --skip-download --write-info-json --write-description "URL"
  # or to stdout: yt-dlp -J --skip-download "URL" > info.json
  ```
  The `.info.json` holds title, channel, upload_date, duration, description, chapters, tags, the `subtitles` and `automatic_captions` maps and the thumbnails list.
- **(b) Subtitles** (only www.youtube.com is needed; see section 4):
  ```bash
  yt-dlp --list-subs --skip-download "URL"           # inspect first
  yt-dlp --skip-download --write-subs --write-auto-subs \
         --sub-langs "sl,sl-orig,en,en-orig" --sub-format "vtt/json3/best" "URL"
  ```
  - Request explicit languages, not `all`. Each auto-translated language is a separate request, which is a likely rate-limit trigger.
  - If the video's spoken language is neither sl nor en, add `<lang>-orig`. The language code is in `info.json` (`language`).
  - Add `--extractor-args "youtube:skip=translated_subs"` when only the original-language track is needed.
  - json3 has word-level timing; vtt is easiest to turn into plain text.
- **(c) Audio for local transcription** (needs googlevideo hosts; see section 4):
  ```bash
  yt-dlp -f "ba[ext=m4a]/ba/b" -x --audio-format m4a "URL"     # or -t mp3
  ```
  Then transcribe locally (e.g. Whisper or faster-whisper; not researched here).
- **(d) Thumbnails and frames:**
  ```bash
  yt-dlp --skip-download --write-thumbnail --convert-thumbnails jpg "URL"   # best thumbnail from i.ytimg.com
  yt-dlp --skip-download --write-all-thumbnails "URL"                       # includes auto stills 1/2/3, hq1-3 …
  ```
  Arbitrary frames at chosen timestamps need the video stream from googlevideo, e.g. `--download-sections "*00:01:10-00:01:12"` plus `ffmpeg -ss … -frames:v 1`. Without googlevideo, only the i.ytimg.com stills are reachable.
- Shorts: pass the `/shorts/ID` URL unchanged. For youtube-transcript-api, extract the 11-character ID yourself.

### Gaps
- The exact nightly install command (`pip install -U --pre "yt-dlp[default]"`) was not re-checked in this session. The README section on release channels was truncated in my fetch.
- I could not determine which formats work without a JS runtime in 2026.11.23 (the EJS wiki does not say), or whether metadata and subtitles alone need the runtime. The code suggests the `visionos` fallback still returns a player response, and therefore caption URLs, but this was not tested.
- `ios_producer` (new in 2026.11.23) and the post-11.23 default list were not inspected. Only the 2026.10.26 source is installed locally.

## 2. "Sign in to confirm you're not a bot" from datacenter IPs: causes, status, fixes; subtitles-only vs media download

### Takeaway
The bot check is driven mainly by **IP reputation**: datacenter and cloud IPs are flagged, and YouTube has done this "for years". Within yt-dlp, the fixes are to update, install a JS runtime, slow down, add cookies from a throwaway account, and add a PO-token provider. None of these guarantees success from a flagged datacenter IP. Only a residential or other non-datacenter IP reliably fixes it. Subtitles and metadata are lighter (no googlevideo traffic, and no Subs PO token on the default clients) than media download, which also has to pass GVS PO-token enforcement.

### Cited Findings
- A yt-dlp contributor on IP blocking: "it hasn't started blocking by IP, it has been doing that for years at this point". IP blocks usually show up as "Video is unavailable" or "Sign in to confirm" errors. In that thread (#16747, May 2026), the maintainer `bashonly` pointed to the missing-JS-runtime warning ("Heed the warning"), and the issue was closed as a question. — [yt-dlp issue #16747](https://github.com/yt-dlp/yt-dlp/issues/16747)
- When every client's player response fails, yt-dlp raises "All player responses are invalid. Your IP is likely being blocked by Youtube". — local inspection of `_video.py` (line 3186)
- The PO Token Guide says a missing PO token "may return HTTP Error 403", and "accounts or IPs may be blocked". Tokens are needed in three places: **GVS** (media streaming), **Player** (innertube player requests) and **Subs** (subtitle requests). Table:
  - `web`: Subs and GVS (only SABR formats)
  - `web_safari`: GVS (its HLS formats currently need no GVS token)
  - `mweb`: GVS
  - `tv`: none (but formats are DRM'd without cookies)
  - `tv_simply`: GVS
  - `web_embedded`: none (embeddable videos only)
  - `android`, `ios`: GVS or Player (no account cookies)
  - `android_vr`: none ("made for kids" unavailable)

  Premium accounts need no GVS token. Manual token extraction "is no longer recommended". Recommended providers: **bgutil-ytdlp-pot-provider** and **yt-dlp-getpot-wpc**. Enforcement "still rolling out"; the wiki was last edited 12 Jul 2026. — [yt-dlp wiki: PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)
- The installed 2026.10.26 client policies differ from the wiki table:
  - `SUBS_PO_TOKEN_POLICY` is `required=False` for every client, including `web`.
  - The new default clients `tv_samsung` and `visionos` have GVS `required=False` for https, dash and hls.
  - `web`, `web_safari` and `mweb` require GVS tokens for https and dash.

  Subtitle PO tokens are detected per video: yt-dlp logs "Some {client} subtitles require a PO Token which was not provided. They will be discarded". youtube-transcript-api raises `PoTokenRequired` when a caption URL contains `&exp=xpe`. — local inspection of `yt_dlp/extractor/youtube/_base.py` INNERTUBE_CLIENTS and `_video.py` lines 3195–3225; `youtube_transcript_api/_transcripts.py` line 135. This **conflicts** with the [PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide) table ("web: Subs"). The most likely explanation is that the Subs requirement is now conditional on the `exp=xpe` URL flag, not static.
- bgutil-ytdlp-pot-provider 2.0.2:
  - Install: `python3 -m pip install -U bgutil-ytdlp-pot-provider`, plus either a Docker server (`docker run … -p 127.0.0.1:4416:4416 brainicism/bgutil-ytdlp-pot-provider`) or script mode with node ≥ 22 or deno ≥ 2.0.0 on PATH.
  - Extractor args: `youtubepot-bgutilhttp:base_url=http://127.0.0.1:4416` and `youtubepot-bgutilscript:server_home=…`.
  - Requires yt-dlp ≥ 2025.05.22.
  - Limits: a PO token "does not guarantee bypassing 403 errors or bot checks", and "does not bypass IP-based login restrictions". On datacenter IPs you may also need cookies (issue #37).

  — [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider)
- yt-dlp on cookies:
  - "By using your account with yt-dlp, you run the risk of it being banned (temporarily or permanently)."
  - Cookies are only *needed* for private, age-restricted and members-only content.
  - "YouTube rotates account cookies frequently on open YouTube browser tabs". To export them safely: log in in a private window, open only `youtube.com/robots.txt`, export the youtube.com cookies, then close the window. Do not use `--cookies-from-browser` for this.
  - OAuth login no longer works.
  - In "Exporting YouTube cookies", the wiki also suggests the `mweb` client with a PO token if the default clients fail.

  — [yt-dlp wiki: Extractors](https://github.com/yt-dlp/yt-dlp/wiki/Extractors)
- In a third-party report, the same cookies worked from a residential laptop but failed from a cloud server; routing through a residential proxy fixed it. The `ios` client ignores cookies (no cookie support, confirmed by the PO Token Guide). — [DEV Community: cloud video service (secondary)](https://dev.to/osovsky/i-was-building-a-cloud-video-service-youtube-turned-me-into-an-ip-trafficker-1l9o); [DEV: yt-dlp in Docker (secondary)](https://dev.to/nareshipme/fixing-yt-dlp-in-docker-n-challenge-ejs-scripts-deno-2x-and-the-playerclientios-cookie-trap-54d6). Several results come from proxy vendors, e.g. [CyberYozh blog](https://app.cyberyozh.com/blog/youtube-vpn-proxy-detected/), so treat their framing with caution.
- youtube-transcript-api: YouTube "has started blocking most IPs that are known to belong to cloud providers (AWS, Google Cloud Platform, Azure…)"; the suggested workaround is rotating residential proxies. — [youtube-transcript-api on PyPI](https://pypi.org/project/youtube-transcript-api/)

### Inferences
- **Order of fixes for this container:**
  1. Upgrade to `yt-dlp[default]` 2026.11.23 and enable a JS runtime (deno, or `--js-runtimes node`).
  2. Keep the default `player_client` (now no-PO-token clients such as tv_samsung and visionos).
  3. Add `-t sleep`.
  4. If you get "Sign in to confirm…", add `--cookies cookies.txt` from a **throwaway** Google account, exported with the private-window method.
  5. If formats are missing or return 403, add bgutil in script mode (`--extractor-args "youtubepot-bgutilscript:server_home=…"`; check its README for the exact 2.x arg).
  6. If it still fails, the IP is the problem: run on the user's own computer (residential IP) or use a residential proxy.
- **Subtitles and metadata only vs media:**
  - Subtitles and metadata need only the player response and a timedtext request on www.youtube.com.
  - The current default clients do not require Subs or GVS PO tokens, so a working setup only has to get past the IP or bot check.
  - Media additionally needs googlevideo access, faces GVS enforcement on web clients, and is far more rate-limited. On a datacenter IP, expect subtitles and metadata to succeed more often than media.
- Changing `player_client` by hand (e.g. `--extractor-args "youtube:player_client=tv_samsung,web_safari"`) is a diagnostic step, not a fix. The defaults change monthly, so hard-coding clients in a config file goes stale.

### Gaps
- No official yt-dlp or YouTube statement quantifies how datacenter IPs are treated in late 2026. The evidence is maintainer comments plus secondary reports.
- I could not confirm whether the bgutil provider itself works from a datacenter IP, or which hostnames it needs. Its README does not list them. From prior knowledge, it contacts `www.youtube.com` and a Google attestation endpoint (`jnn-pa.googleapis.com`), but this is **unverified**.

## 3. youtube-transcript-api (Python): version, cloud IPs, proxies, auto-generated and translated transcripts

### Takeaway
Version **1.2.5** (5 Nov 2026) is a lightweight, transcript-only fallback. It talks only to `www.youtube.com` (plus `consent.youtube.com` in the EU) and supports listing, auto-generated tracks and YouTube machine translation. However, it is explicitly expected to fail from cloud IPs (`RequestBlocked`/`IpBlocked`) unless routed through a (residential) proxy, and cookie authentication is currently not available.

### Cited Findings
- Latest is 1.2.5, released Nov 5, 2026. API:
  ```python
  from youtube_transcript_api import YouTubeTranscriptApi
  ytt_api = YouTubeTranscriptApi()
  ytt_api.fetch(video_id)                              # takes the ID, not the URL
  tl = ytt_api.list(video_id)
  tl.find_transcript(['sl', 'en'])
  tl.find_generated_transcript(['sl', 'en'])
  t.translate('sl')                                    # YouTube machine translation
  ```
  — [PyPI youtube-transcript-api](https://pypi.org/project/youtube-transcript-api/)
- Proxy configuration:
  - `WebshareProxyConfig(proxy_username=…, proxy_password=…)` defaults to rotating residential proxies and accepts `filter_ip_locations`.
  - `GenericProxyConfig(http_url=…, https_url=…)` handles HTTP, HTTPS or SOCKS proxies.
  - "using a proxy doesn't guarantee that you won't be blocked".
  - Cookie auth: "this feature is currently not available", because YouTube changes broke it.

  — [PyPI youtube-transcript-api](https://pypi.org/project/youtube-transcript-api/)
- Hosts and client used by 1.2.5:
  - `WATCH_URL` on `https://www.youtube.com/watch`
  - `INNERTUBE_API_URL = "https://www.youtube.com/youtubei/v1/player?key={api_key}"`
  - `INNERTUBE_CONTEXT = {"client": {"clientName": "ANDROID", "clientVersion": "20.10.38"}}`
  - consent form posted to `https://consent.youtube.com/s`

  Errors defined: `RequestBlocked`, `IpBlocked(RequestBlocked)`, `AgeRestricted`, `TranscriptsDisabled`, `PoTokenRequired` (raised if `&exp=xpe` is in the caption URL; message: "If this happens, please open a GitHub issue!"). Formatters: `JSONFormatter`, `TextFormatter`, `SRTFormatter`, `WebVTTFormatter`, `PrettyPrintFormatter`. `fetch(preserve_formatting=False)`. — local inspection of the 1.2.5 wheel (`_settings.py`, `_errors.py`, `_transcripts.py`, `formatters.py`), [GitHub repo](https://github.com/jdepoix/youtube-transcript-api)

### Inferences
- Minimal fallback script:
  ```python
  from youtube_transcript_api import YouTubeTranscriptApi
  from youtube_transcript_api.formatters import TextFormatter
  api = YouTubeTranscriptApi()                       # optionally proxy_config=GenericProxyConfig(...)
  tl = api.list(VIDEO_ID)
  try:
      t = tl.find_transcript(['sl', 'en'])           # manual first, then generated
  except Exception:
      t = next(iter(tl))
      if t.is_translatable:
          t = t.translate('sl')
  text = TextFormatter().format_transcript(t.fetch())
  ```
- In this setup, the container's HTTPS proxy is already the egress path. `GenericProxyConfig` would only matter if a separate residential proxy were added. That would require allowlisting that proxy's hostname and is a paid third-party service, so it is not recommended for a personal cookbook without the user's decision.
- Because the library uses a hard-coded ANDROID client version, it can break whenever YouTube changes that client. yt-dlp is updated much more often (several releases per month), so yt-dlp should be primary and this library secondary.

### Gaps
- No numbers on rate limits or how long an IP ban lasts for this library. The docs only say self-hosted IPs can also be blocked "if they make too many requests".
- Not tested from this container (www.youtube.com is not allowed by the current proxy).

## 4. Exact hostnames needed; subtitles with only www.youtube.com?; audio without a *.googlevideo.com wildcard?

### Takeaway
**Metadata, description and subtitles: `www.youtube.com` is enough.** All yt-dlp innertube calls, the watch page and the player JS go there. Add `consent.youtube.com` for EU consent redirects, and `i.ytimg.com` for thumbnails and auto-stills. **Audio and video need `rrN---sn-XXXX.googlevideo.com` hosts.** These are dynamic, per-video and per-region edge hostnames that cannot be listed exactly, so **media download is not feasible under an exact-host allowlist**. The workarounds are to run the download outside this proxy (on the user's computer, or in an environment with unrestricted network) or to have the user supply the file.

### Cited Findings
- Local proxy test, 2026-11-26, from this container:
  - `www.youtube.com`, `youtube.com`, `m.youtube.com`, `i.ytimg.com`, `rr1---sn-4g5e6nsz.googlevideo.com` and `redirector.googlevideo.com` were refused ("CONNECT tunnel failed, response 403").
  - `youtubei.googleapis.com` was reachable: Google answered HTTP/2 405 to `GET /`.
  - The WebFetch tool also could not resolve `www.youtube.com` ("outside the session's allowed network domains").

  — local test
- In yt-dlp 2026.10.26, every player client (`web, web_safari, mweb, tv, tv_samsung, tv_simply, visionos, web_embedded, android, android_vr, ios, web_creator`) has `INNERTUBE_HOST = 'www.youtube.com'`, and API URLs are built as `https://{host}/youtubei/v1/{ep}`. The host can be overridden with `--extractor-args "youtube:innertube_host=…"`, and the README names alternatives such as `youtubei.googleapis.com`. `ytcfg.setdefault('INNERTUBE_HOST', 'www.youtube.com')`. `web_music` uses `music.youtube.com`. — local inspection of `yt_dlp/extractor/youtube/_base.py` (lines 135, 433, 731–751, 859); [yt-dlp README](https://github.com/yt-dlp/yt-dlp/blob/master/README.md)
- Thumbnails come from `https://i.ytimg.com/vi{_webp}/{id}/{name}.{ext}`. An EU consent redirect to `https://consent.youtube.com/m?continue=…` appears in yt-dlp's test data, and youtube-transcript-api posts consent to `https://consent.youtube.com/s`. — local inspection of `_video.py` (line 4121), `_redirect.py` (line 209), and youtube_transcript_api `_transcripts.py`
- Media hostnames follow the `rrN---sn-<id>.googlevideo.com` pattern and vary per request and region (e.g. `rr2---sn-pouxga5o-vu2l.googlevideo.com`, `r2---sn-a5meknl6.googlevideo.com`). Network vendors tell admins to allow the whole `googlevideo.com` domain. Blocking one edge hostname breaks playback mid-stream. — [urlscan.io sample](https://urlscan.io/result/01982eb0-e08c-729e-b986-63a60c9b6261); [Pi-hole forum](https://discourse.pi-hole.net/t/googlevideo-com-is-being-blocked/18113); [SonicWall KB](https://www.sonicwall.com/support/knowledge-base/youtube-fails-to-play-videos-after-adding-to-allowed-domains-list-in-cfs/kA1VN0000000LCX0A2); [Arch Linux forum](https://bbs.archlinux.org/viewtopic.php?id=282687)
- Download failures appear as googlevideo.com HTTP 503 or 403 errors, e.g. yt-dlp issue #16747 (May 2026). — [yt-dlp issue #16747](https://github.com/yt-dlp/yt-dlp/issues/16747)

### Inferences
- **Minimal allowlist by goal** (exact hostnames):

  | Goal | Hostnames |
  |---|---|
  | Metadata + description + manual/auto/translated subtitles (yt-dlp or youtube-transcript-api) | `www.youtube.com`, `consent.youtube.com` (recommended, EU consent) |
  | Thumbnails / auto stills (`1.jpg`, `2.jpg`, `3.jpg`, `hq1–3` …) | + `i.ytimg.com` |
  | Install and updates | PyPI (`pypi.org`, `files.pythonhosted.org`); package registries are usually open by default in this cloud product. `github.com` only if you use `--remote-components ejs:github` (not needed with pip `yt-dlp[default]`) |
  | Audio/video, arbitrary frames | `*.googlevideo.com` — **not possible** with exact hosts |
  | Not needed for anonymous use | `accounts.google.com`, `www.google.com`, `youtubei.googleapis.com` (only via `innertube_host=`), `m.youtube.com`/`youtube.com`/`youtu.be` (URLs are parsed locally and normalised to `www.youtube.com`) |

- Subtitle download with only `www.youtube.com` should work. Caption `baseUrl`s returned by the player API point to `www.youtube.com/api/timedtext?…`; both tools use that URL unchanged with an added `fmt`. This could not be confirmed live here, so test it once the host is allowed.
- **Audio without a wildcard, ranked:**
  1. Run yt-dlp on the user's own computer (residential IP, no proxy), e.g. through a Remote Control folder, and hand the audio file to the cloud session. This also avoids the datacenter bot check.
  2. Switch this cloud environment to "unrestricted" network. The datacenter-IP bot check remains.
  3. Have the user send the audio or video file directly.
  4. Paid third-party transcript or download APIs. Not recommended: extra cost, privacy concerns, and the same ToS issue.

  Enumerating `rr…sn-…` hosts in advance cannot work, because yt-dlp gets new edge hostnames in each player response.
- `youtubei.googleapis.com` is reachable here but cannot replace `www.youtube.com` on its own. The watch page and player JS (needed for the JS challenge) are still fetched from `www.youtube.com`, and `player_skip=webpage,js` would lose formats and metadata.

### Gaps
- `manifest.googlevideo.com` (HLS/DASH manifests) is a fixed hostname, but segments still come from `rr…` hosts. I found no source showing an HLS-only route that avoids dynamic hosts.
- Whether `www.youtube.com/api/timedtext` is the current caption host was not verified live (blocked here).

## 5. Rate limits, best practice, cookie risks

### Takeaway
Guest sessions are limited to about **300 videos/hour** (about 1000 webpage/player requests); accounts to about **2000 videos/hour**. Use `-t sleep` or 5–10 s between videos. For a personal cookbook (a few videos per session) this is far below the limits, but datacenter IPs may be blocked regardless. Cookies carry a ban risk and rotate, so use a throwaway account and the private-window export method.

### Cited Findings
- "the rate limit for guest sessions is ~300 videos/hour (~1000 webpage/player requests per hour)"; accounts are about 2000 videos/hour (about 4000 requests). Exceeding them gives "This content isn't available, try again later". Recommended: a 5–10 s delay between downloads with `-t sleep`. — [yt-dlp wiki: Extractors](https://github.com/yt-dlp/yt-dlp/wiki/Extractors)
- `-t sleep` = `--sleep-subtitles 5 --sleep-requests 0.75 --sleep-interval 10 --max-sleep-interval 20`. — [yt-dlp README](https://github.com/yt-dlp/yt-dlp/blob/master/README.md)
- Cookie risks: possible temporary or permanent account ban; frequent rotation on open tabs; use the private window plus `robots.txt` export method. — [yt-dlp wiki: Extractors](https://github.com/yt-dlp/yt-dlp/wiki/Extractors)
- Backing off for a while after a block may help; sleep options are recommended. — [VRChat forum (secondary)](https://ask.vrchat.com/t/specifically-youtube-videos-not-playing-as-of-yesterday/41893/10)

### Inferences
- Best practice for this use case:
  - Process one video per request with `--no-playlist`.
  - Fetch metadata and subtitles first; download audio only when no usable track exists.
  - Request at most 2–4 subtitle languages, not `all`.
  - Cache `info.json` and subtitles in `work/`, which is git-ignored per project rules, so no video is fetched twice.
  - Never commit `cookies.txt` (it contains a session credential). Keep it outside the repository and pass it with `--cookies`.
  - Never use the user's main Google account.
  - Note that `--cookies` also writes the cookie jar back to the same file.

### Gaps
- No public figures on how long datacenter IP blocks last, or on per-IP subtitle-request limits.

## 6. Legal / ToS notes (brief)

### Takeaway
YouTube's Terms forbid downloading content or accessing the service by automated means unless YouTube expressly authorises it or gives written permission. Personal, non-commercial use is **not** an exception in the Terms. Reading metadata and captions to write one's own recipe notes is lower-risk than redistributing media, but it is still technically outside the ToS. Under copyright, facts and techniques (a recipe's method) are generally not protected, unlike the video and its wording.

### Cited Findings
- The ToS "Permissions and Restrictions" clause bars users from accessing, reproducing, downloading, distributing and similar acts on the Service or Content, except "(a) as expressly authorized by the Service; or (b) with prior written permission from YouTube and, if applicable, the respective rights holders". It also bars accessing the Service by automated means such as robots or scrapers, except public search engines following robots.txt or with prior permission. The version cited by a university copyright FAQ was last updated 5 Jan 2022. — [YouTube Terms of Service](https://www.youtube.com/static?gl=GB&template=terms); [University of Waterloo copyright FAQ](https://uwaterloo.ca/copyright-at-waterloo/catalogs/frequently-asked-questions/27-my-course-i-link-youtube-videos-some-students-are-not)
- An older version (2017 archive) said you shall not download any Content "unless you see a 'download' or similar link displayed by YouTube". — [Wayback Machine, YouTube ToS 2017](https://web-wp.archive.org/web/20170811164130/https:/www.youtube.com/t/terms)
- yt-dlp warns that using an account with it risks a ban. — [yt-dlp wiki: Extractors](https://github.com/yt-dlp/yt-dlp/wiki/Extractors)

### Inferences
- For the cookbook:
  - Keep the processing personal and do not redistribute downloaded audio, video or full transcripts.
  - Store only the derived, re-written recipe plus a source link. This matches the project's existing source-attribution practice.
  - Delete intermediate media in `work/` after transcription.
  - A ToS breach is a contract or account-level risk (block or ban), separate from copyright. This is not legal advice.

### Gaps
- I could not read the current live ToS text: `www.youtube.com` is blocked in this session, so the wording and effective date were confirmed only via search snippets. Whether a 2025 or 2026 revision changed the clause is unknown.
- Slovenian or EU private-copy exceptions (e.g. the private-use copying exception in national copyright law) were not researched.
