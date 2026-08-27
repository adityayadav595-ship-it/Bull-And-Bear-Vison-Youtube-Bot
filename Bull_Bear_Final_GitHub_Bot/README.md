# Bull & Bear Final GitHub Bot

Runs automatically in GitHub Actions, even if your laptop/iPhone is off.

Safety-oriented setup:
- Upload cadence is controlled by `.github/workflows/main.yml` (currently every 6 hours for a fresh channel).
- It checks only the approved Pinterest sources you list and requires `I_HAVE_RIGHTS_TO_REPOST=true`.
- It scores unseen videos for trading/Quotex relevance and Shorts-friendly duration.
- It permanently records source IDs and file hashes so the same video is not posted again.
- YouTube metadata is sanitized to remove aggressive or guaranteed-profit language and includes an educational/risk disclosure.

Required GitHub Secrets: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN.

Only use sources whose videos you own or are licensed/authorized to repost. No automation can guarantee that a channel will never receive enforcement; YouTube policy compliance and content rights still matter.
