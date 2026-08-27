# Changelog

## Unreleased

- Added the first native 4Saves desktop interface for macOS, Windows, and Linux.
- Added link analysis with title, platform, creator, duration, and collection details.
- Added simple Best, Universal, Edit-ready, Small, and Audio presets.
- Added a persistent SQLite download queue with restart recovery.
- Added live progress, retry, cancel, native folder selection, drag-and-drop, and reveal-in-folder actions.
- Replaced the desktop app's shell-based conversion hook with a structured internal processing stage.
- Kept the Qt desktop runtime optional so terminal-only installations remain lightweight.

## 0.5.0

- Added modern YouTube challenge support through the official EJS remote-component fallback.
- Added configurable concurrent fragments, exponential retry delays, socket timeouts, and file/extractor retries.
- Added error-specific recovery advice and a persistent `last-error.log` for failed jobs.
- Made settings and history writes atomic and tolerant of unknown or malformed records.
- Added free-space warnings and a visible destination summary before downloads.
- Added direct `4saves URL` and `4saves audio URL` commands.
- Grouped secondary actions into submenus so the main interface fits an 80×24 terminal.
- Expanded system health checks for `ffprobe`, Deno/Node, and YouTube EJS.

## 0.4.0

- Replaced numbered prompts with highlighted arrow-key menus.
- Refreshed the terminal layout with compact headers and rounded panels.
- Added a clean live download bar with speed and ETA.
- Standardized video output for broad editor compatibility: MP4, 8-bit H.264, CFR, AAC-LC stereo/48 kHz, even dimensions, `avc1`, and fast-start metadata.
- Skip redundant conversion when a download already meets the compatibility checks.
- Added quick custom downloads with start/end clipping and per-job folders.
- Added persistent download history and one-menu retry/resume support.
- Detects partial files created before download history existed and distinguishes active downloads.
- Made changing the default download folder a main-menu action.
- Updated the interface to reflect broad `yt-dlp` site support.

## 0.3.0

- Rebranded the app to 4Saves.
- Added `4saves` as the primary command.
- Added `4saves --version` and `4saves update`.
- Replaced the shell-only conversion hook with a cross-platform Python converter.
- Prepared the project for GitHub publishing.

## 0.2.0

- Added support for YouTube, TikTok, Instagram, and X/Twitter URLs.
- Added platform-aware login cookie guidance.
- Organized downloads by extractor/platform.

## 0.1.0

- Added terminal menu downloads powered by `yt-dlp`.
- Added Premiere/QuickTime friendly video conversion.
- Added batch downloads, playlist downloads, audio extraction, subtitles, metadata, and dependency checks.
