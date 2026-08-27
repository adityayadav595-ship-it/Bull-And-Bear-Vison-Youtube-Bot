# Market Vision Pro YouTube Review Uploader

A review-first YouTube workflow for the **Market Vision Pro** channel that keeps human control over every upload and reduces repetitive/spam-like publishing patterns.

## Fresh handoff state

This copy no longer contains the previous channel brand, previous source URLs, or previous upload history. It also uses new GitHub Secret names so old YouTube credentials are not reused automatically.

The scheduled GitHub Action can inspect sources every 3 hours. The bot starts in `review` mode and automatic uploads remain PRIVATE-only. Public publishing must be done manually in YouTube Studio.

## Guardrails

- Human approval required for every candidate via `approved_uploads.txt`
- Source/reuse-rights review for each video
- Exact duplicate protection using source history + SHA-256 hashes
- 6-hour minimum upload cooldown
- Previous-title similarity checks to reduce repetitive metadata
- Maximum 6 relevant tags and 3 hashtags
- External URLs blocked from automated metadata
- Guaranteed-profit, risk-free, withdrawal-proof, VIP-signal, promo-code and engagement-exchange language blocked
- Trading-risk / educational disclosure included
- At most one successful upload per run
- No automated comments, likes, subscriptions, artificial views, or engagement manipulation
- Fail-closed behavior when approvals, rights, metadata, duplicates, privacy, or configuration checks fail

## Setup for Market Vision Pro

1. Add only owned/licensed exact video URLs to `approved_sources.txt`.
2. Run the Action in review mode and inspect `review_queue.jsonl`.
3. After reviewing a candidate, copy its exact URL or `source_key` into `approved_uploads.txt`.
4. Add fresh GitHub Secrets for the channel owner's Google/YouTube project:
   - `BOT_YOUTUBE_CLIENT_ID`
   - `BOT_YOUTUBE_CLIENT_SECRET`
   - `BOT_YOUTUBE_REFRESH_TOKEN`
5. `CHANNEL_BRAND` defaults to `Market Vision Pro`; the repository variable can override it if needed.
6. Keep `CHANNEL_STATE=active` and change `BOT_RUN_MODE=upload` only when ready for approved PRIVATE uploads.
7. Review each private upload in YouTube Studio before deciding whether to publish it.

No automation can guarantee YouTube enforcement outcomes. Content rights, metadata, financial claims, and overall channel behavior still need to comply with YouTube policies.
