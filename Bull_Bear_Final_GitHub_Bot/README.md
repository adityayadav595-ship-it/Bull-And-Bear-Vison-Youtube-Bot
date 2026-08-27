# Bull & Bear Final GitHub Bot

A review-first YouTube workflow designed to reduce repetitive/spam-like publishing patterns and keep human control over every upload.

## Current safety state

The repository is intentionally **locked for YouTube uploads** while the channel termination is unresolved:

- `CHANNEL_STATE` defaults to `suspended`
- `BOT_RUN_MODE` defaults to `review`
- automatic uploads are **PRIVATE-only**
- public publishing must be done manually in YouTube Studio

The GitHub Action can still run every 3 hours to discover/rank candidates and refresh `review_queue.jsonl` without uploading to YouTube.

## Guardrails

- Human approval required for every candidate via `approved_uploads.txt`
- Per-item reuse-rights review instead of relying only on a blanket source list
- Exact duplicate protection with source history + SHA-256 content hashes
- 12-hour minimum upload cooldown even when upload mode is enabled
- Previous-title similarity check to block repetitive/templated metadata
- Maximum 6 relevant tags and 3 hashtags
- External URLs removed/blocked from automated metadata
- Guaranteed-profit, risk-free, withdrawal-proof, VIP-signal, promo-code and engagement-exchange language blocked
- Trading-risk / educational disclosure included
- One upload at most per successful run
- No automated comments, likes, subscriptions, playlists, artificial views, or engagement features
- Fail-closed behavior: missing approval, rights confirmation, unsafe metadata, duplicate content, wrong channel state, or non-private privacy setting = no upload

## Review workflow

1. Scheduled run creates/updates `review_queue.jsonl`.
2. Human watches a candidate and confirms ownership/license/permission to repost it.
3. Copy the candidate's exact URL or `source_key` into `approved_uploads.txt`.
4. Only after YouTube restores/confirms the channel is permitted to operate, set repository variables:
   - `CHANNEL_STATE=active`
   - `BOT_RUN_MODE=upload`
   - `I_HAVE_RIGHTS_TO_REPOST=true`
5. The bot may then upload an approved candidate as **PRIVATE**.
6. Review the private upload manually in YouTube Studio before deciding whether to publish it.

Required GitHub Secrets: `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.

No automation can guarantee that YouTube will not take enforcement action. The content itself, reuse rights, metadata, financial claims, and overall channel behavior must comply with YouTube policies.
