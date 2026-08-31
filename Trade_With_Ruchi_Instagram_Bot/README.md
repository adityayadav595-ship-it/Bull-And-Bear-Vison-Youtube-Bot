# Trade With Ruchi — Instagram Auto Upload Bot

Separate Instagram Reel uploader for the **Trade With Ruchi** brand. It does not modify the existing Bull & Bear YouTube bot files.

## What it does

- Runs manually or automatically from GitHub Actions.
- Default schedule: every 3 hours.
- Selects one unused public HTTPS video URL from `sources.txt`.
- Publishes it as an Instagram Reel using Meta's official API flow.
- Uses a custom caption from `sources.txt`, or generates a basic Trade With Ruchi caption.
- Waits until Meta finishes processing the Reel before publishing.
- Records successfully published source URLs in `uploaded_urls.txt` to avoid duplicates.
- Uses a concurrency lock so two uploader runs do not overlap.

## Required Instagram setup

Use an Instagram account that is eligible for API publishing (normally a Professional account with the required Meta app/account setup).

Add these GitHub repository secrets:

- `RUCHI_IG_USER_ID` — the Instagram professional account/user ID used by the publishing API.
- `RUCHI_IG_ACCESS_TOKEN` — an access token with the required Instagram publishing permission(s).

Optional repository variable:

- `META_GRAPH_VERSION` — defaults to `v22.0` in the workflow and can be changed without editing the code.

Never commit access tokens or passwords into the repository.

## Add videos

Edit `sources.txt` and add one source per line:

```text
https://your-public-host.example/video1.mp4 | Caption for Reel 1 #tradewithruchi
https://your-public-host.example/video2.mp4 | Caption for Reel 2 #trading
```

The video URL must be HTTPS and reachable by Meta's servers. Only add content you own or have permission to publish.

## Manual test

Open GitHub Actions → **Trade With Ruchi - Instagram Auto Upload** → **Run workflow**.

Choose `dry_run=true` first. The bot will select a source and build the caption without publishing anything. Then use `dry_run=false` for a real upload.

## Automatic schedule

The workflow currently uses:

```yaml
cron: "17 */3 * * *"
```

GitHub cron schedules use UTC. This means the bot attempts a run every three hours; if there is no unused source, it safely exits without publishing.

## Files

- `app.py` — selection, Meta upload, processing-status polling and publishing logic.
- `sources.txt` — approved public video sources and optional captions.
- `uploaded_urls.txt` — duplicate-prevention history.
- `requirements.txt` — Python dependency list.
- `.github/workflows/trade-with-ruchi-instagram.yml` — automation workflow.
