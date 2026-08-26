\
# Bull & Bear Vision — Pinterest → YouTube Auto Uploader

This bot checks approved Pinterest Pin/board/profile URLs, finds the newest unseen video,
downloads it, generates trading-focused title/description/tags, uploads it to YouTube,
and repeats every 3 hours.

## Important boundary

Only add Pinterest sources containing videos you own, created, licensed, or have explicit
permission to repost. The bot intentionally requires `I_HAVE_RIGHTS_TO_REPOST=true`
before it will download/upload anything.

Pinterest frequently changes its site and may block automated extraction. The bot uses
`yt-dlp`; if Pinterest changes its extractor/API behavior, update yt-dlp first.

## What it does

- Checks one or more Pinterest Pin / board / profile URLs.
- Picks the newest unseen item.
- Downloads with yt-dlp.
- Avoids reposting the same source twice using SQLite.
- Auto-classifies:
  - tutorials/indicators/strategy → Education
  - lifestyle/motivation → People & Blogs
- Generates:
  - Shorts title
  - description
  - trading-risk disclaimer
  - hashtags
  - YouTube tags
- Uploads via YouTube Data API.
- Runs every 3 hours by default.
- Sets "not made for kids" by default.
- Supports YouTube's altered/synthetic-media disclosure flag.

## 1) Install Python

Recommended: Python 3.11+ on Windows, macOS, Linux, VPS, or a cloud runner.

On iPhone, do NOT try to keep this running in Safari. Run the bot on a computer/VPS/cloud
and control the source file remotely.

## 2) Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

FFmpeg is strongly recommended because yt-dlp may need it to merge video/audio.

## 3) Create Google / YouTube OAuth credentials

1. Open Google Cloud Console.
2. Create/select a project.
3. Enable **YouTube Data API v3**.
4. Configure OAuth consent.
5. Create an **OAuth client ID → Desktop app**.
6. Download the JSON and rename it to:
   `client_secret.json`
7. Put it beside `app.py`.

On first upload, a browser window opens. Sign in to the YouTube channel owner account
and approve upload access. The bot saves `token.json`.

### Important YouTube API note

Google states that uploads from some **unverified API projects** can be restricted to
private viewing until the API project passes the required compliance audit. The code
can request `public`, but Google/YouTube ultimately controls whether the project is
allowed to publish publicly.

## 4) Configure the bot

Copy:

```bash
cp .env.example .env
```

Then edit `.env`:

```env
I_HAVE_RIGHTS_TO_REPOST=true
POST_EVERY_HOURS=3
YOUTUBE_PRIVACY=public
MADE_FOR_KIDS=false
CONTAINS_SYNTHETIC_MEDIA=false
CHANNEL_BRAND=Bull & Bear Vision
```

If a permitted Pinterest source requires your browser session, you may set:

```env
PINTEREST_COOKIES_FILE=/path/to/cookies.txt
```

Do not share your cookies file or YouTube OAuth token.

## 5) Add approved Pinterest sources

Edit `pinterest_sources.txt` and add one URL per line:

```text
https://www.pinterest.com/pin/123456789012345678/
https://www.pinterest.com/USERNAME/BOARDNAME/
```

## 6) Test one cycle

```bash
python app.py --once
```

Expected flow:

```text
Checking source...
Selected video...
Downloaded...
Generated metadata...
Upload progress...
SUCCESS: YouTube video ID = ...
```

## 7) Run continuously

```bash
python app.py
```

Default schedule: one upload attempt every 3 hours.

For a VPS, run it under systemd, supervisor, Docker, or another process manager so it
keeps running after you disconnect.

## Viral metadata logic included

Educational/indicator clips get titles similar to:

`Aroon Indicator Explained Fast 📈🔥 #shorts`

Lifestyle clips get:

`POV: When The Grind Finally Pays Off 💸📈 #shorts`

Descriptions automatically include a trading-risk disclaimer and focused hashtags.
The generator avoids claims such as "guaranteed profit" or "100% win".

## Files

- `app.py` — scheduler + orchestration
- `bot/downloader.py` — Pinterest/yt-dlp discovery and download
- `bot/metadata.py` — titles, descriptions, hashtags, tags, category
- `bot/youtube.py` — YouTube OAuth + upload
- `bot/storage.py` — duplicate protection
- `pinterest_sources.txt` — approved source URLs
- `.env` — private config; do not upload publicly
- `bot_state.sqlite3` — upload history

## Troubleshooting Pinterest

Pinterest extraction can break when Pinterest changes its page/API behavior.

First try:

```bash
python -m pip install -U yt-dlp
```

Then test the exact Pin:

```bash
yt-dlp "PIN_URL"
```

If it fails with 403/404, do not try to bypass Pinterest's security controls. Use a
source URL/account/API flow that you are authorized to access, or place your own/licensed
video file in a separate manual intake workflow.

## Security

Never commit these files to GitHub:

- `.env`
- `client_secret.json`
- `token.json`
- `cookies.txt`
- `bot_state.sqlite3`
