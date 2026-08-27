# 4Saves

4Saves is a friendly terminal app for saving video and audio from more than a thousand sites supported by `yt-dlp`, including YouTube, TikTok, Instagram, X/Twitter, Vimeo, Facebook, Twitch, Reddit, and many more.

It is built for creators and editors: normal video downloads are delivered as broadly compatible MP4 files by default—8-bit H.264 video, constant frame rate, AAC-LC stereo audio, even dimensions, and fast-start metadata. This is the common-denominator format for Premiere Pro, DaVinci Resolve, Final Cut Pro, After Effects, CapCut, QuickTime, and most other editors and players.

Made by **mofe404**.

X: [@mofe404](https://x.com/mofe404)

## Features

- Download videos, posts, reels, shorts, tweets, playlists, profiles, and collections.
- Download audio as MP3, M4A, Opus, or WAV.
- Batch download multiple URLs.
- Show a clean live progress bar with speed and estimated time remaining.
- Download a precise clip by entering its start and end time.
- Continue interrupted downloads from the main menu.
- Choose a download folder per job or change the default folder directly.
- Convert existing downloads to H.264/AAC MP4.
- Save subtitles, thumbnails, descriptions, and metadata.
- Use browser cookies for login-gated or private content.
- Organize downloads by platform and uploader.
- Diagnose failures with specific recovery advice and a saved error log.
- Use resilient retries and concurrent fragment downloading.
- Check ffmpeg, ffprobe, yt-dlp, Deno/Node, EJS support, and updates from the menu.

## Install 4Saves From Terminal

4Saves needs:

- Python 3.10+
- `yt-dlp`
- `ffmpeg`
- Deno or Node.js 22+ strongly recommended for full YouTube support
- `aria2c` optional, for faster downloads

Install the required tools first.

macOS:

```bash
brew install git python yt-dlp ffmpeg deno aria2
```

Linux, Debian/Ubuntu example:

```bash
sudo apt update
sudo apt install git python3 python3-pip ffmpeg aria2
python3 -m pip install -U "yt-dlp[default]"
```

Windows, using winget:

```powershell
winget install Git.Git
winget install Python.Python.3.12
winget install yt-dlp.yt-dlp
winget install Gyan.FFmpeg
```

Install 4Saves on macOS/Linux:

```bash
git clone https://github.com/mofe404/4saves.git
cd 4saves
./install.sh
```

Install 4Saves on Windows:

```powershell
git clone https://github.com/mofe404/4saves.git
cd 4saves
py -m pip install --user .
```

Run it:

```bash
4saves
```

You can also download directly without opening the menu:

```bash
4saves "https://example.com/video"
4saves audio "https://example.com/video"
```

## Update 4Saves

Update from terminal anytime:

```bash
4saves update
```

Then run:

```bash
4saves
```

## Download Option

If you prefer downloading manually instead of installing through git, use the latest GitHub release:

```text
https://github.com/mofe404/4saves/releases/latest
```

To update the downloader engine:

```bash
yt-dlp -U
```

or:

```bash
python3 -m pip install -U "yt-dlp[default]"
```

## Usage Notes

Menus use a highlighted selection instead of numbered prompts. Move with the Up/Down arrow keys and press Enter to select. `J`/`K`, Home/End, and Esc on Back/Quit menus are also supported.

If Instagram, TikTok, X, or YouTube blocks a download because of login, privacy, age checks, or bot checks, choose the browser cookies option. Safari, Chrome, Firefox, Brave, Edge, and Opera are supported when `yt-dlp` can read the browser profile.

YouTube increasingly requires JavaScript challenge solving. 4Saves enables yt-dlp's official EJS GitHub fallback for YouTube by default and reports whether Deno or Node is available under **System health & updates**. This can be disabled in Settings.

When a job fails, 4Saves shows advice matched to the error and saves the last 120 diagnostic lines to `~/.config/4saves/last-error.log`.

4K means "4K if the source site provides a 4K stream." 4Saves cannot create real 4K detail from a 1080p source.

Downloads are saved to `~/Downloads/4Saves` by default. Existing installs may keep the previous folder until changed in Settings.

Interrupted downloads are kept as partial files. Choose **Resume / retry unfinished download** from the main menu and 4Saves will detect both tracked jobs and older partial files, then ask `yt-dlp` to continue instead of starting over when the source supports resuming. Files still being written are marked **ACTIVE** so a second downloader is not started accidentally.

For a clip, choose **Quick custom download**, enter a start and end such as `01:15` and `02:40`, then choose video or audio and the destination folder.

## Legal

4Saves is a wrapper around `yt-dlp` and `ffmpeg`. Use it responsibly and only download content you have the right to save.
