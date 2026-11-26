# Extracting content from Instagram Reels (link only) in a headless, allowlisted Linux cloud container — state as of 26 Nov 2026

Scope note: researched 26 Nov 2026. "Verified in this session" means it was checked directly in this container: local commands, the extractor source code pulled from raw.githubusercontent.com, and PyPI JSON. Instagram itself could NOT be reached from this session (see Q3), so no end-to-end download of a real reel was tested here. The procedure below is assembled from the current tool source and docs, not from a live run.

## Q1. Which tools work in 2026 (yt-dlp, instaloader, gallery-dl, others)? Login needs, datacenter IPs, typical errors and fixes

### Takeaway
yt-dlp is the best-maintained option for single reels in 2026. Its Instagram extractor was rewritten in the 2026.07.04 release and logged-in extraction was fixed in 2026.08.19. Anonymous (no-login) extraction of public reels still exists in the code, but it only works when browser-TLS impersonation is installed (`curl_cffi`). Logged-in cookies are the more reliable route, at the risk of the account being flagged. Instaloader (4.16) and gallery-dl (1.32.21) are maintained too. gallery-dl no longer supports username/password login (browser cookies only). Instaloader documents much stricter anonymous limits for cloud/VPN IPs.

### Cited Findings
**Versions (current, from PyPI on 26 Nov 2026; verified in this session)**
- yt-dlp 2026.11.23 (uploaded 2026-11-23), instaloader 4.16 (2026-10-26), gallery-dl 1.32.21 (2026-11-21), curl-cffi 0.17.0 (2026-10-26) — [PyPI yt-dlp](https://pypi.org/project/yt-dlp/), [PyPI instaloader](https://pypi.org/project/instaloader/), [PyPI gallery-dl](https://pypi.org/project/gallery-dl/), [PyPI curl-cffi](https://pypi.org/project/curl-cffi/)
- This container already has `/usr/local/bin/yt-dlp` version 2026.10.26 and `/usr/bin/ffmpeg`, with Python 3.13. `curl_cffi` is NOT installed: `yt-dlp --list-impersonate-targets` shows Chrome/Edge/Firefox/Safari/Tor all "(unavailable)". [Verified in this session]

**yt-dlp changelog (Instagram entries, 2025–2026)**
- 2025.03.21: added the `app_id` extractor-arg, fixed extraction of older private posts, improved error handling — [yt-dlp Changelog](https://github.com/yt-dlp/yt-dlp/blob/master/Changelog.md)
- 2026.07.04: "Rework extractor" (#17075) and "Detect when cookies are invalidated" (#17126) — [yt-dlp Changelog](https://github.com/yt-dlp/yt-dlp/blob/master/Changelog.md)
- 2026.08.19: "Fix logged-in extraction" (#17278) — [yt-dlp Changelog](https://github.com/yt-dlp/yt-dlp/blob/master/Changelog.md)
- No Instagram entries in 2026.10.21, 2026.10.26 or 2026.11.23 (grep of the changelog). [Verified in this session]
- The trigger for the rework was issue #17074, opened 28 Jun 2026 on 2026.06.09: "Instagram sent an empty media response" for reels that work without login. Maintainer bashonly: "the extractor should still work w/ logged-in cookies and w/o impersonation. But as always, there is the risk that your account will be flagged or banned." Also: "An account will not be flagged/banned if you're not passing logged-in cookies." Without cookies, `curl-cffi` is needed because "The site blocks anonymous API requests that do not have a browser fingerprint." Closed via PR #17075. Some users still reported failures with cookies afterwards — [yt-dlp issue #17074](https://github.com/yt-dlp/yt-dlp/issues/17074)
- A similar report: a reel page loads in the browser with cookies, but the extractor fails with HTTP 404 / empty media response (filed 3 Jul 2026) — [yt-dlp issue #17124](https://github.com/yt-dlp/yt-dlp/issues/17124)
- Downstream apps hit the same problem. Seal (Android yt-dlp GUI) reports "missing impersonate target (curl_cffi)", and the fix is installing impersonation dependencies — [Seal issue #2566](https://github.com/JunkFood02/Seal/issues/2566). Another project's PR installs `yt-dlp[curl-cffi]` "for Instagram impersonation" — [reclip PR #99](https://github.com/averygan/reclip/pull/99)
- Older precedent: "empty media response" even with a valid cookies file (2025) — [yt-dlp issue #13551](https://github.com/yt-dlp/yt-dlp/issues/13551). Story URLs still raise login-required errors on 2026.08.19 and nightly — [search summary pointing to yt-dlp issues; e.g. #17755](https://github.com/yt-dlp/yt-dlp/issues/17755)

**How the current yt-dlp extractor works (read from master source; verified in this session)** — [yt-dlp instagram.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/instagram.py)
- Login state is detected only by a `sessionid` cookie (`_AUTH_COOKIE_NAME = 'sessionid'`). There is no username/password or `.netrc` login in this extractor, so only `--cookies` / `--cookies-from-browser` work.
- Logged-in path: GET `{API_BASE_URL}/media/{pk}/info/`. `API_BASE_URL` is `https://www.instagram.com/api/v1` with the default web app id `936619743392459`, or `https://i.instagram.com/api/v1` with `--extractor-args "instagram:app_id=ios"` (id `124024574287414`). If the cookies are rejected, it warns "The provided Instagram account cookies are no longer valid", clears `sessionid` and falls back to logged-out extraction.
- Logged-out path: GET `https://www.instagram.com/` ("Setting up session", reads the LSD token), then GET `/api/v1/web/get_ruling_for_content/`, then POST `https://www.instagram.com/api/graphql` (doc_id `27130156389949648`, `PolarisLoggedOutDesktopWWWPostRootContentQuery`). **Key detail: that GraphQL POST is only sent `if self._can_impersonate`, so without curl_cffi the anonymous path skips its main step.** The last fallback is the HTML page `https://www.instagram.com/p/{shortcode}`.
- Exact error strings: "Instagram sent an empty media response. Check if this post is accessible in your browser without being logged-in…"; "The webpage request was redirected to the login page. You have exceeded the rate-limit for accessing posts anonymously"; "This content is only available for registered users who follow this account" (private posts, shortcode longer than 28 chars); `Restricted Video` triggers login-required (age-restricted); warnings "No CSRF token set by Instagram API" and "Instagram API is not granting access".
- README: impersonation needs curl_cffi, "Can be installed with the `curl-cffi` extra, e.g. `pip install "yt-dlp[default,curl-cffi]"`"; the only Instagram extractor-arg is `app_id` — [yt-dlp README](https://github.com/yt-dlp/yt-dlp/blob/master/README.md)

**Instaloader**
- Single post or reel by shortcode: `instaloader -- -B_K4CykAOtf` (the leading `-` marks a shortcode) — [instaloader docs/basic-usage.rst](https://github.com/instaloader/instaloader/blob/master/docs/basic-usage.rst)
- Session options: `--login USER` (stores a session file that is reused non-interactively), `--load-cookies BROWSER` / `-b` (needs `browser_cookie3`; since 4.11), `--cookiefile`, `--sessionfile`. Content flags include `--no-pictures`, `--no-video-thumbnails`, `--no-captions`, `--no-metadata-json` — [instaloader docs/cli-options.rst](https://github.com/instaloader/instaloader/blob/master/docs/cli-options.rst)
- Troubleshooting docs: "services, that in their nature offer promiscuous IP addresses, such as cloud, VPN and public proxy services, might be subject to significantly stricter limits for anonymous access. However, logged-in accesses do not seem to be affected." Restarting Instaloader often within a short time "is prone to cause a 429". Login problems can be worked around with `615_import_firefox_session.py` (import Firefox cookies). Keep the session file because "session files usually do not expire" — [instaloader docs/troubleshooting.rst](https://github.com/instaloader/instaloader/blob/master/docs/troubleshooting.rst)
- 2025 reports of a blanket `401 "Please wait a few minutes before you try again"` on requests (issues #2532, #2511); a "Fix reels download" PR #2545 was open at the time — [ecosyste.ms index of instaloader issues](https://issues.ecosyste.ms/hosts/GitHub/repositories/instaloader%2Finstaloader/issues). Whether 4.16 resolves this was not confirmed.
- One third-party guide says anonymous access is throttled to roughly 1–2 requests per 30 s — [apiserpent blog (vendor, unverified)](https://apiserpent.com/blog/scrape-instagram-for-free)

**gallery-dl**
- Password login removed: `_login_impl` logs "Login with username & password is no longer supported. Use browser cookies instead." The auth cookie is `sessionid` on `.instagram.com`. Stories/highlights raise `AuthRequired("authenticated cookies")`. API calls go to `https://www.instagram.com/api/v1/...` with `X-IG-App-ID: 936619743392459`. GraphQL goes to `https://www.instagram.com/graphql/query/`. It warns "Potentially lowered video quality due to non-Chrome User-Agent" and suggests refreshing cookies when only lower resolutions come back — [gallery-dl instagram.py](https://github.com/mikf/gallery-dl/blob/master/gallery_dl/extractor/instagram.py)
- Config: `extractor.instagram.api` = `"rest"` (default, higher-resolution) or `"graphql"` (lower-resolution). `extractor.instagram.videos` = `true`/`"dash"`/`"ytdl"` downloads from `video_dash_manifest` using yt-dlp, or `"merged"` — [gallery-dl configuration.rst](https://github.com/mikf/gallery-dl/blob/master/docs/configuration.rst)

**Datacenter IPs (third-party, mostly vendor claims)**
- Proxy and scraping vendors say Instagram flags cloud IPs quickly (blocks from the first request up to within 5–20 requests) and cite about 200 requests/hour/IP for unauthenticated access. Logged-out scraping leads to IP blocks, not account bans — [Scrapfly 2026](https://scrapfly.io/blog/posts/how-to-scrape-instagram), [torchproxies 2026](https://torchproxies.com/instagram-scraping-in-2026-scrape-without-getting-blocked/), [hikerapi](https://hikerapi.com/help/instagram-scraping-without-getting-blocked). These have a commercial stake in residential proxies, so treat the numbers as anecdotal.

### Inferences
- For one reel at a time, the most robust 2026 setup is yt-dlp ≥ 2026.08.19 (preferably 2026.11.23) **plus curl_cffi**. Try anonymous first (no account risk). If it fails with "empty media response" or a login redirect, fall back to a cookies file from a dedicated secondary account.
- The installed yt-dlp 2026.10.26 already contains the July/August Instagram fixes, but it will not run the anonymous GraphQL query until curl_cffi is installed.
- A cloud container's datacenter egress IP is exactly the case Instaloader warns about. Anonymous success is likely to be intermittent, and cookies may be needed in practice.
- Other routes (not scraping): Meta's official oEmbed / Graph API only covers embedding or accounts you own (see Q6). The simplest robust fallback is for the user to save or share the video file itself (or a screen recording), or to run yt-dlp on their own computer.

### Gaps
- No live test against Instagram was possible here (proxy 403). Whether a public reel currently extracts anonymously from this specific egress IP is unknown.
- No post-August-2026 yt-dlp issue confirming the current anonymous success rate for reels was found.
- The instaloader.github.io pages were unreachable from this session; the same docs were read from the GitHub repo instead.

## Q2. Supplying cookies safely in a headless environment

### Takeaway
In a headless container, the practical method is a Netscape-format `cookies.txt` exported on a desktop browser and passed with `--cookies FILE`. `--cookies-from-browser` needs a local browser profile. Use a separate low-value account, never the user's main one, and treat the file as a secret. The yt-dlp maintainers explicitly warn that passing logged-in cookies risks the account being flagged or banned.

### Cited Findings
- yt-dlp options: `--cookies FILE` ("Netscape formatted file to read cookies from") and `--cookies-from-browser BROWSER[+KEYRING][:PROFILE][::CONTAINER]` (brave, chrome, chromium, edge, firefox, opera, safari, vivaldi, whale) — [yt-dlp README](https://github.com/yt-dlp/yt-dlp/blob/master/README.md); flags confirmed with the local `yt-dlp --help` [verified in this session]
- The yt-dlp Instagram extractor needs only the `sessionid` cookie to count as logged in. It looks for cookies on `i.instagram.com`, `www.instagram.com` and `.instagram.com` — [yt-dlp instagram.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/instagram.py)
- Maintainer: logged-in cookies carry "the risk that your account will be flagged or banned", while no-cookie use does not put an account at risk — [yt-dlp issue #17074](https://github.com/yt-dlp/yt-dlp/issues/17074)
- Since 2026.07.04, yt-dlp detects invalidated cookies ("The provided Instagram account cookies are no longer valid") and continues logged-out instead of failing — [yt-dlp Changelog](https://github.com/yt-dlp/yt-dlp/blob/master/Changelog.md), [instagram.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/instagram.py)
- A 2026 guide says `--cookies-from-browser firefox` is the reliably working variant, and that 401 / "login required" / empty results usually mean a stale session (log in again in the browser, then re-export) — [techearl.com](https://techearl.com/download-instagram-reel)
- Instaloader: `--load-cookies firefox` (browser_cookie3) or the `615_import_firefox_session.py` script creates a reusable session file; Instagram may issue a "checkpoint challenge" when it suspects unusual authentication activity — [instaloader troubleshooting.rst](https://github.com/instaloader/instaloader/blob/master/docs/troubleshooting.rst), [cli-options.rst](https://github.com/instaloader/instaloader/blob/master/docs/cli-options.rst)
- gallery-dl accepts only browser cookies for Instagram (`--cookies FILE` or `--cookies-from-browser`) — [gallery-dl instagram.py](https://github.com/mikf/gallery-dl/blob/master/gallery_dl/extractor/instagram.py)
- Instagram's Terms of Use also forbid soliciting or using other users' login credentials — [Instagram Terms of Use (via search summary; page not fetchable here)](https://help.instagram.com/581066165581870)

### Inferences
- Recommended handling: export `cookies.txt` for instagram.com from a desktop Firefox session of a secondary account (for example with a "cookies.txt" export extension, or `yt-dlp --cookies-from-browser firefox --cookies cookies.txt --skip-download <any reel URL>` run on the desktop, which writes the jar to a file). Store it outside the Git repo, `chmod 600`, and never commit it. `work/` is already git-ignored per AGENTS.md, but a path outside the repo is safer.
- A cookie created on the user's home IP and then used from a datacenter IP in another country is a classic trigger for suspicious-login checkpoints. Expect occasional re-login on the desktop and a fresh export.
- The `sessionid` is effectively a password-equivalent. Putting it in the cloud environment's plain-text env vars or setup script would expose it, and the environment tooling explicitly says not to.

### Gaps
- No reliable 2025–2026 data was found on how often secondary accounts get checkpointed or banned when used with yt-dlp at very low volume. Only the maintainer's general warning exists.
- The exact lifetime of Instagram `sessionid` cookies in 2026 was not found.

## Q3. Exact hostnames contacted; are CDN hosts dynamic; is an exact-host allowlist feasible; can a fixed CDN host be forced?

### Takeaway
Metadata and caption need only **`www.instagram.com`**. With yt-dlp's default web `app_id`, both the logged-out and logged-in paths use it, and `i.instagram.com` is needed only with `app_id=ios`. Video, audio and thumbnail bytes come from **region-specific CDN hosts** (`scontent-<pop>.cdninstagram.com`, `instagram.f<pop>.fna.fbcdn.net` and similar) that the API picks per request. Every community allowlist resorts to wildcards (`*.cdninstagram.com`, `*.fbcdn.net`). An exact-host allowlist works reliably for metadata only. Media needs either a two-step "discover host, then allow it" process, unrestricted network, or downloading outside the container.

### Cited Findings
- Hosts in the yt-dlp extractor: `https://www.instagram.com/` (session setup), `www.instagram.com/api/v1/web/get_ruling_for_content/`, `www.instagram.com/api/graphql`, `www.instagram.com/p/{id}`, `{API_BASE_URL}/media/{pk}/info/` (where `API_BASE_URL` is `www.instagram.com/api/v1` for the web app id and `i.instagram.com/api/v1` for the ios id), `{API_BASE_URL}/feed/reels_media/` (stories) — [yt-dlp instagram.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/instagram.py)
- gallery-dl uses `www.instagram.com/api/v1/...` and `www.instagram.com/graphql/query/` — [gallery-dl instagram.py](https://github.com/mikf/gallery-dl/blob/master/gallery_dl/extractor/instagram.py). Instaloader also calls `i.instagram.com` (iPhone API, `get_iphone_json`, on by default via `iphone_support=True`) as well as `www.instagram.com` `graphql/query` and `api/graphql` — [instaloader instaloadercontext.py](https://github.com/instaloader/instaloader/blob/master/instaloader/instaloadercontext.py)
- Media URLs come from the API JSON: formats from `video_versions` and `video_dash_manifest`, thumbnails from `image_versions2` candidates — [yt-dlp instagram.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/instagram.py)
- CDN hostnames are many and region-specific (e.g. `scontent-hel3-1.cdninstagram.com`, `scontent.cdninstagram.com`, `instagram-shv-06-lla1.fbcdn.net`, `instagram.ffor20-1.fna.fbcdn.net`). "host/IP is different for scontent, external, video" across fbcdn subdomains — [StevenBlack/hosts issue #1535](https://github.com/StevenBlack/hosts/issues/1535), [bol-van/zapret discussion #1712](https://github.com/bol-van/zapret/discussions/1712), [Flowseal issue #10993](https://github.com/Flowseal/zapret-discord-youtube/issues/10993)
- Firewall admins note that allowing Instagram also needs `*.fna.fbcdn.net` and `connect.facebook.net` — [Palo Alto LIVEcommunity](https://live.paloaltonetworks.com/t5/general-topics/instagram-allowed-in-the-security-policy-but-the-pictures-are/td-p/411162). An allowlist PR that allowed only instagram.com found styles/scripts/images broken and added `*.instagram.com`, `*.cdninstagram.com`, `*.fbcdn.net` — [infyum-outreach PR #42](https://github.com/rudravejpara099-glitch/infyum-outreach/pull/42)
- A 2021 yt-dlp log shows the media download going to a `fna.fbcdn.net` host — [lightrun summary of youtube-dl/yt-dlp issue (older info)](https://lightrun.com/answers/ytdl-org-youtube-dl-some-instagram-reels-giving-an-httperror)
- **This session (verified):** the egress proxy returns `CONNECT tunnel failed, response 403` for `www.instagram.com`, `i.instagram.com`, `scontent.cdninstagram.com`, `scontent-vie1-1.cdninstagram.com` and `instagram.flju1-1.fna.fbcdn.net`. WebFetch also cannot resolve `help.instagram.com`, `instaloader.github.io` or `dev.to`. `raw.githubusercontent.com` and `pypi.org` are reachable. The cloud-environment tooling for this session accepts only exact hostnames and rejects patterns like `*.example.com`. Package registries (PyPI) are reachable by default; "unrestricted" network access is a separate setting the user can choose. [Verified in this session / environment tool documentation]

### Inferences
- Minimum allowlist for metadata and caption only (yt-dlp default `app_id`): `www.instagram.com`. Add `i.instagram.com` only if using `app_id=ios` or Instaloader. Installing tools needs PyPI (`pypi.org`, `files.pythonhosted.org`), which is reachable by default.
- For media, two-step discovery should work with exact hosts. Run `yt-dlp --skip-download -J <url>` (contacts only `www.instagram.com`), read the hostnames from `formats[].url` and `thumbnails[].url`, and ask the user to add exactly those hosts. Because the CDN POP is likely chosen from the egress IP's location, the same few hosts will probably recur from a fixed egress, but they can change at any time. This is unverified; it needs a test once `www.instagram.com` is allowed.
- Practical options, ranked: (1) ask the user to set the environment to unrestricted network for this task, or add hosts as discovered. (2) Run yt-dlp on the user's own computer (the session's Remote Control / attached-folder feature) and process the file in the cloud. (3) The user sends the video file directly. Option 3 avoids Instagram ToS and account-risk issues entirely.
- The safest exact allowlist for metadata only is `www.instagram.com`. Caption text alone is often enough for ingredient lists, and the video is needed only for techniques that are shown and not written.

### Gaps
- No source was found showing that a CDN host can be forced to a fixed generic host (e.g. rewriting to `scontent.cdninstagram.com`). Instagram CDN URLs carry signed query parameters (commonly `oh=`, `oe=`), so rewriting the host may or may not be accepted. This is unverified; treat it as not supported.
- No official Meta list of Instagram media hostnames was found. All hostname lists are community-sourced.
- Whether DASH audio/video segments and the progressive MP4 for one reel share one CDN host could not be checked without access.

## Q4. Getting caption/description, subtitles, audio and thumbnails/frames — without downloading video where possible (concrete procedure)

### Takeaway
Caption and metadata come back from the API with no media download: `yt-dlp --skip-download --write-info-json --write-description` (only `www.instagram.com` is needed). yt-dlp's Instagram extractor does **not** extract subtitles, so plan on local speech-to-text from the audio. Audio-only may be available as a DASH audio format (`-f bestaudio`). If not, download the small progressive MP4 and extract audio with ffmpeg. Thumbnails need the CDN host, and frames are taken locally from the video with ffmpeg.

### Cited Findings
- Fields the yt-dlp extractor returns: `description` (from `caption.text`), `title` ("Video by …" fallback), `channel`, `uploader`, `uploader_id`, `timestamp`, `duration`, `view_count`, `like_count`, `comment_count`, `thumbnails` (from `image_versions2`), formats from `video_versions` (with `acodec: none` when `has_audio` is false) and DASH formats parsed from `video_dash_manifest`; comments when `getcomments`. No subtitle extraction in the code. Carousels become playlists — [yt-dlp instagram.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/instagram.py)
- Relevant flags in the installed yt-dlp: `--skip-download`, `--write-info-json`, `--write-description`, `--write-thumbnail`, `--write-all-thumbnails`, `--write-subs`/`--write-auto-subs` (no effect here, since none are extracted), `-x/--extract-audio`, `-O/--print`, `--print-traffic` (shows hosts contacted), `--sleep-requests`, `--impersonate`, `--extractor-args` — [yt-dlp README](https://github.com/yt-dlp/yt-dlp/blob/master/README.md); confirmed with local `yt-dlp --help` [verified in this session]
- gallery-dl can fetch video via `video_dash_manifest` using yt-dlp (`videos: "dash"/"ytdl"`) — [gallery-dl configuration.rst](https://github.com/mikf/gallery-dl/blob/master/docs/configuration.rst)
- Instaloader writes the caption as a `.txt` and metadata as `.json.xz` by default, unless `--no-captions` / `--no-metadata-json` are given; `--no-pictures` and `--no-video-thumbnails` limit downloads — [instaloader cli-options.rst](https://github.com/instaloader/instaloader/blob/master/docs/cli-options.rst)
- One Seal (yt-dlp GUI) issue is titled "Instagram Reels – Audio Not Downloadable", so audio-only format availability is not guaranteed — [Seal issues list (title only seen)](https://github.com/JunkFood02/Seal/issues/2579)

### Inferences
Proposed procedure, assembled from the cited flags. It was not run end-to-end here because the proxy blocks Instagram.

```bash
# 0) Install / upgrade (PyPI is reachable by default). Use a venv.
python3 -m venv ~/.venvs/ig && . ~/.venvs/ig/bin/activate
pip install -U "yt-dlp[default,curl-cffi]"     # curl_cffi = browser TLS impersonation, needed for anonymous IG
yt-dlp --version && yt-dlp --list-impersonate-targets   # Chrome/Safari etc. should no longer say "(unavailable)"
# ffmpeg is already at /usr/bin/ffmpeg in this container

URL='https://www.instagram.com/reel/<SHORTCODE>/'
OUT="work/reels/%(id)s"     # work/ is git-ignored per AGENTS.md

# (a) metadata + caption only, no media download (host: www.instagram.com)
yt-dlp --skip-download --write-info-json --write-description \
       --sleep-requests 1 -o "$OUT.%(ext)s" "$URL"
#   -> <id>.info.json (uploader, timestamp, duration, formats[].url ...) and <id>.description (caption)
#   Optional: list CDN hosts needed for step (c)/(d):
yt-dlp -J --skip-download "$URL" | python3 -c 'import sys,json,urllib.parse as u;d=json.load(sys.stdin);print(sorted({u.urlparse(x["url"]).hostname for x in d.get("formats",[])+d.get("thumbnails",[]) if x.get("url")}))'

# (b) subtitles: Instagram extractor provides none -> transcribe audio locally (step c)

# (c) audio for transcription (needs the CDN host(s) printed above)
yt-dlp -F "$URL"                                       # inspect: is there an audio-only DASH format?
yt-dlp -f "bestaudio/best" -x --audio-format m4a -o "$OUT.%(ext)s" "$URL"
#   fallback if no audio-only format: download smallest progressive mp4 and extract audio with ffmpeg
ffmpeg -i work/reels/<id>.mp4 -vn -ac 1 -ar 16000 work/reels/<id>.wav   # 16 kHz mono WAV suits Whisper-type ASR

# (d) thumbnail + frames
yt-dlp --skip-download --write-thumbnail --convert-thumbnails jpg -o "$OUT.%(ext)s" "$URL"
ffmpeg -i work/reels/<id>.mp4 -vf "fps=1/2,scale=720:-1" work/reels/<id>_%03d.jpg   # one frame every 2 s

# If anonymous fails ("empty media response" / "redirected to the login page"):
yt-dlp --cookies /secure/path/ig_cookies.txt ...same options...
```
- `--print-traffic` (or `-v`) on the first real run is the cleanest way to record exactly which hosts were contacted, for the allowlist.
- Instagram Reels often carry burned-in on-screen text (ingredient lists) rather than speech. Frame extraction plus OCR or vision may matter as much as audio transcription for cooking reels.

### Gaps
- Whether reels in 2026 typically expose a separate audio-only DASH representation (so `-f bestaudio` avoids video download) could not be verified without access.
- Whether Instagram's in-app auto-captions are exposed anywhere in the API JSON was not found in any tool source. Assume not available.
- Local ASR tool choice (Whisper / faster-whisper versions, model hosts such as huggingface.co) was not researched here.

## Q5. Rate limits and best practices to avoid blocks

### Takeaway
For a personal assistant handling one reel at a time, volume is tiny. The main risks are datacenter IP reputation (anonymous) and account flags (cookies). Make one request per reel, add sleeps, avoid restarts and retries in bursts, cache the info.json, and never crawl profiles.

### Cited Findings
- yt-dlp's built-in preset `-t sleep` expands to `--sleep-subtitles 5 --sleep-requests 0.75 --sleep-interval 10 --max-sleep-interval 20` — [yt-dlp README](https://github.com/yt-dlp/yt-dlp/blob/master/README.md) [confirmed in local help]
- yt-dlp reports the anonymous limit explicitly: "redirected to the login page. You have exceeded the rate-limit for accessing posts anonymously" — [yt-dlp instagram.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/instagram.py)
- Instaloader has a built-in rate controller and retries 429s after the assumed ban expires. "Too many queries in the last time" is a notice, not an error. Frequent restarts cause 429s. Cloud/VPN IPs get stricter anonymous limits — [instaloader troubleshooting.rst](https://github.com/instaloader/instaloader/blob/master/docs/troubleshooting.rst)
- Vendor guidance: about 200 requests/hour/IP anonymous; a 429 means rotate the IP, `feedback_required` means rotate the account; delays of 3–7 s between requests — [Scrapfly](https://scrapfly.io/blog/posts/how-to-scrape-instagram), [hikerapi](https://hikerapi.com/help/instagram-scraping-without-getting-blocked), [Apify downloader listing](https://apify.com/shahidirfan/instagram-video-downloader) (commercial sources; anecdotal)
- Instagram's help centre says Meta has teams that detect and block scraping patterns — [Instagram Help: scraping (via search summary; not fetchable here)](https://help.instagram.com/740480200552298)

### Inferences
- Per reel: one `-J`/`--write-info-json` call, then reuse the JSON. Do not call yt-dlp again for each artefact. A single combined invocation (`--write-info-json --write-description --write-thumbnail -f ...`) is better than three separate runs.
- Use `-t sleep` or at least `--sleep-requests 1`, and stop after the first login-redirect or 401/429. Do not loop retries; wait hours, or switch to the user-sends-file fallback.
- Don't use rotating proxies or account rotation. That is ban-evasion territory, against ToS, and unnecessary for personal volumes.

### Gaps
- No primary-source (Meta) figures for Instagram's rate limits exist. All numbers are third-party estimates.

## Q6. Legal / ToS notes (brief)

### Takeaway
Instagram's Terms prohibit collecting information "in an automated way without our express permission". Downloading reels with yt-dlp, Instaloader or gallery-dl is, strictly, a ToS violation even for personal use, and the main practical risk is account or IP blocking. The only Meta-sanctioned programmatic route is oEmbed/Graph API (embedding, or your own accounts). It does not give the video file, and since 2025 oEmbed no longer returns thumbnails or author. For the cookbook: ingredient lists and simple directions are not copyrightable (US), but the creator's expressive text, video and photos are. Rewrite techniques in your own words, credit the source, and keep the content personal.

### Cited Findings
- Instagram Terms of Use: you can't access or collect information in unauthorized ways, including collecting information in an automated way without Meta's express permission. Selling or licensing data from the service and soliciting other users' login credentials are also prohibited — [Instagram Terms of Use](https://help.instagram.com/581066165581870); court-filed copy: [lb7.uscourts.gov PDF](https://www.lb7.uscourts.gov/documents/19-1861URL1Termsofuse.pdf). The live page could not be fetched from this session, so the wording comes from search summaries and the effective date was not checked.
- Meta's separate Automated Data Collection Terms require express written permission even for public data (secondary commentary) — [Thunderbit blog](https://thunderbit.com/blog/is-scraping-instagram-legal)
- Meta oEmbed changes: from 2025, `/instagram_oembed` no longer returns `thumbnail_url`, `thumbnail_width`, `thumbnail_height`, `author_name`; existing apps moved to "Meta oEmbed Read" (dates given as 1 Oct 2025 / 3 Nov 2025) — [Meta for Developers blog, 8 Apr 2025](https://developers.facebook.com/blog/post/2025/04/08/oembed-updates/), [Graph API non-versioned changes 2025](https://developers.facebook.com/docs/graph-api/changelog/non-versioned-changes/nvc-2025), [iframely note](https://iframely.com/updates/193071-facebook-and-instagram-oembed-thumbnail-deprecation)
- US Copyright Office Circular 33: "a mere listing of ingredients or contents, or a simple set of directions, is uncopyrightable". FL-122: protection "may extend to a description, explanation, or illustration … that accompanies a recipe … or to a combination of recipes, as in a cookbook" — [Copyright Office Circular 33](https://www.copyright.gov/circs/circ33.pdf), [FL-122 (archived)](https://webharvest.gov/peth04/20041015023438/http://www.copyright.gov/fls/fl122.html), [Copyright Alliance](https://copyrightalliance.org/are-rec)

### Inferences
- For a personal, non-commercial cookbook: transcribe or adapt the technique (ingredients, quantities, temperatures and steps rewritten in Slovenian in the book's style). Do not reproduce the creator's caption prose or embed their frames in the published DOCX/PDF beyond what is necessary. Keep the source link in the recipe's evidence file, as the project already does with `reference/` notes.
- The EU/Slovenian private-copy exception and how it interacts with Instagram's ToS (contract) was not researched. Treat it as unknown.
- The lowest-risk workflow, legally and technically, is for the user to send the video file or screenshots themselves, or to paste the caption text, with yt-dlp as a convenience path.

### Gaps
- The exact current wording and effective date of Instagram's Terms of Use could not be fetched (host blocked). Re-check at https://help.instagram.com/581066165581870 if exact quotes are needed.
- EU/Slovenian copyright treatment of recipes (e.g. the originality standard under EU case law) and the private-copy exception were not covered by sources found here.
- This is not legal advice.
