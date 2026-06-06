# Contributing

Thanks for helping make 4Saves better.

## Development

Run the app locally:

```bash
python3 -m four_saves
```

Run a quick syntax check:

```bash
python3 -m py_compile four_saves/*.py ytdl_mac/*.py
```

## Good First Improvements

- Better error messages for Instagram, TikTok, and X login issues.
- More output presets for editors.
- A download history view.
- Safer update checks and release notifications.
- Tests for command construction.

## Notes

4Saves wraps `yt-dlp` and `ffmpeg`. Please avoid adding heavy dependencies unless they clearly improve the terminal experience.
