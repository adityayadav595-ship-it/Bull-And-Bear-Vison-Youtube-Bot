# Trade With Ruchi — Instagram Auto Upload Bot

Separate Instagram Reel uploader for the **Trade With Ruchi** brand. It does not modify the existing Bull & Bear YouTube bot files.

## What it does

- Runs manually or automatically from GitHub Actions.
- Default schedule: every 3 hours.
- Accepts approved Instagram Reel/Post URLs from `sources.txt`.
- Downloads the highest available MP4 from Instagram with `yt-dlp`.
- Does **not** re-encode the downloaded Reel, avoiding an extra quality-loss step.
- Uploads the local file to Meta using Instagram's official resumable video-upload flow.
- Publishes it as an Instagram Reel after Meta processing finishes.
- Uses a custom caption from `sources.txt`, or generates a basic Trade With Ruchi caption.
- Records successfully published Instagram source URLs in `uploaded_urls.txt` to avoid duplicates.
- Uses a concurrency lock so two uploader runs do not overlap.

## Required Instagram setup

Use an Instagram account that is eligible for API publishing (normally a Professional account with the required Meta app/account setup).

Add these GitHub repository secrets:

- `RUCHI_IG_USER_ID` — the Instagram professional account/user ID used by the publishing API.
- `RUCHI_IG_ACCESS_TOKEN` — an access token with the required Instagram publishing permission(s).

Optional repository variable:

- `META_GRAPH_VERSION` — workflow default is `v25.0` and can be changed without editing the code.

Never commit access tokens or passwords into the repository.

## Add Instagram Reel sources

Edit `sources.txt` and add one approved Instagram Reel/Post URL per line:

```text
https://www.instagram.com/reel/ABC123xyz/ | Trade With Ruchi 📈 #trading #tradewithruchi
https://www.instagram.com/p/DEF456xyz/ | Market learning with Trade With Ruchi
```

The downloader rejects non-Instagram sources. Add only content you own or have permission to republish.

## Quality mode

The bot selects the best available MP4 exposed by Instagram and uploads that file directly to Meta. It intentionally does not resize, render, or re-encode the Reel. This avoids an additional compression pass; Instagram may still apply its own platform processing after upload.

If Instagram exposes no downloadable MP4 for a source, the bot fails that run instead of transcoding a lower-quality or incompatible file.

## Manual test

Open GitHub Actions → **Trade With Ruchi - Instagram Auto Upload** → **Run workflow**.

Choose `dry_run=true` first. The bot will select a source and build the caption without downloading or publishing anything. Then use `dry_run=false` for a real upload.

## Automatic schedule

The workflow currently uses:

```yaml
cron: "17 */3 * * *"
```

GitHub cron schedules use UTC. This means the bot attempts a run every three hours; if there is no unused source, it safely exits without publishing.

## Files

- `app.py` — Instagram source download, quality-preserving local-file upload, processing-status polling and publishing logic.
- `sources.txt` — approved Instagram Reel/Post sources and optional captions.
- `uploaded_urls.txt` — duplicate-prevention history.
- `requirements.txt` — Python dependencies.
- `.github/workflows/trade-with-ruchi-instagram.yml` — automation workflow.
