from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .domain import DownloadJob, DownloadPreset

PROGRESS_PREFIX = "4SAVES_PROGRESS|"
FILE_PREFIX = "4SAVES_FILE|"


@dataclass(frozen=True, slots=True)
class MediaInfo:
    title: str
    platform: str
    uploader: str
    duration: int | None
    thumbnail: str
    is_collection: bool
    item_count: int | None


def normalize_url(value: str) -> str:
    value = value.strip()
    if value.startswith(("http://", "https://")):
        return value
    if value.startswith("www."):
        return f"https://{value}"
    return value


def is_youtube(url: str) -> bool:
    host = urlparse(normalize_url(url)).netloc.lower().removeprefix("www.")
    return host == "youtu.be" or host.endswith("youtube.com")


def probe_command(url: str) -> list[str]:
    args = [
        "yt-dlp",
        "--ignore-config",
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
    ]
    if is_youtube(url):
        args.extend(["--remote-components", "ejs:github"])
    args.append(normalize_url(url))
    return args


def parse_probe_output(output: str) -> MediaInfo:
    lines = [line for line in output.splitlines() if line.lstrip().startswith("{")]
    if not lines:
        raise ValueError("The site did not return usable media information.")
    data = json.loads(lines[-1])
    entries = data.get("entries")
    count = len(entries) if isinstance(entries, list) else data.get("playlist_count")
    return MediaInfo(
        title=str(data.get("title") or data.get("playlist_title") or "Untitled media"),
        platform=str(
            data.get("extractor_key") or data.get("extractor") or "Unknown site"
        ),
        uploader=str(data.get("uploader") or data.get("channel") or ""),
        duration=int(data["duration"]) if data.get("duration") is not None else None,
        thumbnail=str(data.get("thumbnail") or ""),
        is_collection=bool(data.get("_type") in {"playlist", "multi_video"} or entries),
        item_count=int(count) if count is not None else None,
    )


def output_template(job: DownloadJob) -> str:
    return str(
        Path(job.output_dir).expanduser()
        / "%(extractor_key)s"
        / "%(uploader)s"
        / "%(title)s [%(id)s].%(ext)s"
    )


def download_command(job: DownloadJob) -> list[str]:
    args = [
        "yt-dlp",
        "--ignore-config",
        "--continue",
        "--part",
        "--no-overwrites",
        "--no-playlist",
        "--windows-filenames",
        "--trim-filenames",
        "180",
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "--retry-sleep",
        "http:exp=1:20",
        "--retry-sleep",
        "fragment:exp=1:20",
        "--concurrent-fragments",
        "4",
        "--newline",
        "--color",
        "no_color",
        "--progress-template",
        f"download:{PROGRESS_PREFIX}%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s",
        "--print",
        f"after_move:{FILE_PREFIX}%(filepath)s",
        "-o",
        output_template(job),
    ]
    if is_youtube(job.url):
        args.extend(["--remote-components", "ejs:github"])

    if job.preset is DownloadPreset.BEST:
        args.extend(["-f", "bv*+ba/b", "--merge-output-format", "mkv"])
    elif job.preset is DownloadPreset.SMALL:
        args.extend(
            [
                "-f",
                "bv*[height<=720]+ba/b[height<=720]/worst",
                "--merge-output-format",
                "mp4",
            ]
        )
    elif job.preset is DownloadPreset.AUDIO:
        args.extend(
            [
                "-x",
                "--audio-format",
                "m4a",
                "--audio-quality",
                "0",
                "--embed-thumbnail",
                "--add-metadata",
            ]
        )
    else:
        args.extend(["-f", "bv*+ba/b", "--merge-output-format", "mp4"])

    args.append(job.url)
    return args


def parse_progress(line: str) -> tuple[float, str, str] | None:
    if not line.startswith(PROGRESS_PREFIX):
        return None
    pieces = line[len(PROGRESS_PREFIX) :].split("|", 2)
    pieces.extend([""] * (3 - len(pieces)))
    match = re.search(r"[\d.]+", pieces[0])
    percent = float(match.group()) if match else 0.0
    return max(0.0, min(percent, 100.0)), pieces[1].strip(), pieces[2].strip()


def parse_output_path(line: str) -> str | None:
    return line[len(FILE_PREFIX) :].strip() if line.startswith(FILE_PREFIX) else None


def friendly_error(output: str) -> str:
    lowered = output.lower()
    if "http error 403" in lowered or "forbidden" in lowered:
        if "youtube" in lowered:
            return "YouTube rejected the media request. Update the download engine or retry with YouTube authentication support."
        return (
            "The site rejected the request. It may require a signed-in browser session."
        )
    if "unsupported url" in lowered:
        return (
            "This link does not contain supported media, or the site changed recently."
        )
    if "no space left" in lowered:
        return "The destination drive does not have enough free space."
    if "requested format is not available" in lowered:
        return "That preset is unavailable for this media. Try Best quality or another preset."
    errors = [line.strip() for line in output.splitlines() if "error:" in line.lower()]
    return (
        errors[-1]
        if errors
        else "The download did not finish. Open details or retry the job."
    )
