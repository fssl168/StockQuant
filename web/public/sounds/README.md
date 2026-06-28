# Sound Assets

This directory holds sound effect files referenced by `web/src/utils/soundManager.ts`:

- `risk-long.mp3` — high-risk alert (long descending tone)
- `opportunity-short.mp3` — opportunity alert (short ascending tone)
- `info-double.mp3` — informational alert (double tone)
- `critical-triple.mp3` — critical alert (triple tone)

## Fallback

When the MP3 files are not present, `soundManager` automatically falls back to
`fallbackBeep` synthesized via the Web Audio API (sine wave, 180ms) so the
application remains fully functional.

## Adding Real Files

Drop the four MP3 files into this directory (keep each under 50KB). Once added,
`soundManager.preloadAll()` will load them automatically on next page load and
the browser Network panel will no longer log 404s for these paths.
