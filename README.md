# 4Saves

4Saves is a terminal media downloader for saving videos and audio from YouTube, TikTok, Instagram, X/Twitter, and other sites supported by `yt-dlp`.

It is built for creators and editors: normal video downloads are converted to Premiere/QuickTime-friendly H.264/AAC MP4 by default.

Made by **mofe404**.

X: [@mofe404](https://x.com/mofe404)

## Features

- Download videos, posts, reels, shorts, tweets, playlists, profiles, and collections.
- Download audio as MP3, M4A, Opus, or WAV.
- Batch download multiple URLs.
- Convert existing downloads to H.264/AAC MP4.
- Save subtitles, thumbnails, descriptions, and metadata.
- Use browser cookies for login-gated or private content.
- Organize downloads by platform and uploader.
- Check dependencies and update tools from the menu.

## Requirements

4Saves needs:

- Python 3.10+
- `yt-dlp`
- `ffmpeg`
- `aria2c` optional, for faster downloads

macOS:

```bash
brew install python yt-dlp ffmpeg aria2
```

Linux, Debian/Ubuntu example:

```bash
sudo apt update
sudo apt install python3 python3-pip ffmpeg aria2
python3 -m pip install -U yt-dlp
```

Windows, using winget:

```powershell
winget install Python.Python.3.12
winget install yt-dlp.yt-dlp
winget install Gyan.FFmpeg
```

## Install 4Saves From Terminal

Install `pipx` first.

macOS:

```bash
brew install pipx
pipx ensurepath
```

Linux, Debian/Ubuntu example:

```bash
sudo apt install pipx
pipx ensurepath
```

Windows:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

Then install 4Saves:

```bash
pipx install https://github.com/mofe404/4saves/archive/refs/heads/main.zip
```

Run it:

```bash
4saves
```

## Update 4Saves

Update from terminal:

```bash
pipx install --force https://github.com/mofe404/4saves/archive/refs/heads/main.zip
```

Then run:

```bash
4saves
```

## Download Option

If you prefer downloading manually, use the latest GitHub release:

```text
https://github.com/mofe404/4saves/releases/latest
```

## Future Package Install

Long term, 4Saves should be published to PyPI so install/update becomes:

```bash
pipx install 4saves
pipx upgrade 4saves
```

To update the downloader engine:

```bash
yt-dlp -U
```

or:

```bash
python3 -m pip install -U yt-dlp
```

## Usage Notes

If Instagram, TikTok, X, or YouTube blocks a download because of login, privacy, age checks, or bot checks, choose the browser cookies option. Safari, Chrome, Firefox, Brave, Edge, and Opera are supported when `yt-dlp` can read the browser profile.

4K means "4K if the source site provides a 4K stream." 4Saves cannot create real 4K detail from a 1080p source.

Downloads are saved to `~/Downloads/4Saves` by default. Existing installs may keep the previous folder until changed in Settings.

## Publish Checklist

Before sharing publicly:

- Create a GitHub repo named `4saves`.
- Initialize git in this folder if needed.
- Commit the project files.
- Push to GitHub.
- Add screenshots or a short demo GIF.
- Share the terminal install command.
- Create a release for people who prefer manual downloads.
- Later, publish to PyPI for easier `pipx install 4saves` updates.

## Legal

4Saves is a wrapper around `yt-dlp` and `ffmpeg`. Use it responsibly and only download content you have the right to save.
