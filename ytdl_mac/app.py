from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict, fields
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from four_saves import __version__
from four_saves.convert import build_conversion_args


APP_NAME = "4Saves"
APP_TAGLINE = "Save video and audio from almost anywhere"
CONFIG_DIR = Path.home() / ".config" / "4saves"
CONFIG_FILE = CONFIG_DIR / "settings.json"
HISTORY_FILE = CONFIG_DIR / "history.json"
ERROR_LOG_FILE = CONFIG_DIR / "last-error.log"
LOCAL_CONFIG_FILE = Path.cwd() / ".4saves-settings.json"
LOCAL_HISTORY_FILE = Path.cwd() / ".4saves-history.json"
DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "4Saves"
PROGRESS_PREFIX = "4SAVES_PROGRESS|"
POSTPROCESS_PREFIX = "4SAVES_POST|"
BROWSERS = ["safari", "chrome", "firefox", "brave", "edge", "opera"]
BROWSER_LABELS = {
    "safari": "Safari",
    "chrome": "Google Chrome",
    "firefox": "Firefox",
    "brave": "Brave",
    "edge": "Microsoft Edge",
    "opera": "Opera",
}
QUALITY_LABELS = {
    "best": "Best quality",
    "2160": "4K if available",
    "1440": "Up to 1440p",
    "1080": "Up to 1080p",
    "720": "Up to 720p",
    "small": "Smallest MP4",
    "premiere_1080": "Up to 1080p",
    "premiere_720": "Up to 720p",
}


class Style:
    reset = "\033[0m"
    bold = "\033[1m"
    dim = "\033[2m"
    cyan = "\033[36m"
    green = "\033[32m"
    yellow = "\033[33m"
    red = "\033[31m"
    blue = "\033[34m"
    magenta = "\033[35m"
    reverse = "\033[7m"


def supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def color(text: str, *styles: str) -> str:
    if not supports_color():
        return text
    return "".join(styles) + text + Style.reset


def terminal_width(max_width: int = 82) -> int:
    return min(shutil.get_terminal_size((max_width, 20)).columns, max_width)


def rule(char: str = "─") -> str:
    return color(char * terminal_width(), Style.dim)


def panel(lines: list[str], title: str | None = None) -> None:
    width = terminal_width()
    print(color("╭" + "─" * (width - 2) + "╮", Style.cyan))
    if title:
        print(color("│", Style.cyan) + " " + color(title.ljust(width - 4), Style.bold, Style.cyan) + " " + color("│", Style.cyan))
        print(color("├" + "─" * (width - 2) + "┤", Style.cyan))
    for line in lines:
        clipped = line[: width - 4]
        print(color("│", Style.cyan) + " " + clipped.ljust(width - 4) + " " + color("│", Style.cyan))
    print(color("╰" + "─" * (width - 2) + "╯", Style.cyan))


def status(label: str, message: str, tone: str = "cyan") -> None:
    tones = {
        "cyan": Style.cyan,
        "green": Style.green,
        "yellow": Style.yellow,
        "red": Style.red,
        "blue": Style.blue,
        "magenta": Style.magenta,
    }
    badge = color(f"[{label}]", Style.bold, tones.get(tone, Style.cyan))
    print(f"{badge} {message}")


@dataclass
class Settings:
    download_dir: str = str(DEFAULT_DOWNLOAD_DIR)
    video_quality: str = "1080"
    audio_format: str = "mp3"
    audio_quality: str = "0"
    subtitle_language: str = "en"
    browser_for_cookies: str = "safari"
    use_aria2c: bool = False
    concurrent_fragments: int = 4
    youtube_ejs: bool = True


@dataclass
class DownloadJob:
    id: str
    url: str
    label: str
    args: list[str]
    status: str
    created_at: str
    finished_at: str | None = None
    exit_code: int | None = None


def main() -> None:
    if len(sys.argv) > 1:
        handle_cli_args(sys.argv[1:])
        return

    settings = load_settings()
    ensure_download_dir(settings)

    while True:
        clear_screen()
        header()
        panel(
            [
                f"Save to: {settings.download_dir}",
                f"Video: {quality_label(settings.video_quality)}  ·  Audio: {settings.audio_format.upper()}  ·  1,000+ sites",
            ],
            "Current Setup",
        )
        choice = menu(
            "What do you want to do?",
            [
                "Download video",
                "Download audio only",
                "Quick custom download (clip + location)",
                "Resume / retry unfinished download",
                "Playlists, profiles & batch downloads",
                "Subtitles, metadata & advanced tools",
                "Convert existing video",
                "Change download folder",
                "Settings",
                "System health & updates",
                "Quit",
            ],
        )

        if choice == 1:
            download_video(settings)
        elif choice == 2:
            download_audio(settings)
        elif choice == 3:
            quick_custom_download(settings)
        elif choice == 4:
            resume_download(settings)
        elif choice == 5:
            collection_download_menu(settings)
        elif choice == 6:
            extra_tools_menu(settings)
        elif choice == 7:
            convert_existing_video()
        elif choice == 8:
            settings = change_download_folder(settings)
        elif choice == 9:
            settings = settings_menu(settings)
        elif choice == 10:
            dependency_menu(settings)
        elif choice == 11:
            status("DONE", "Done. May your downloads behave themselves.", "green")
            return


def collection_download_menu(settings: Settings) -> None:
    choice = menu(
        "Playlists, profiles & batches",
        [
            "Download playlist / profile / collection",
            "Batch download pasted URLs",
            "Back",
        ],
    )
    if choice == 1:
        download_playlist(settings)
    elif choice == 2:
        batch_download(settings)


def extra_tools_menu(settings: Settings) -> None:
    choice = menu(
        "More download tools",
        [
            "List available formats",
            "Download subtitles",
            "Download thumbnail + metadata",
            "Advanced yt-dlp flags",
            "Back",
        ],
    )
    if choice == 1:
        list_formats(settings)
    elif choice == 2:
        download_subtitles(settings)
    elif choice == 3:
        download_metadata_bundle(settings)
    elif choice == 4:
        advanced_download(settings)


def handle_cli_args(args: list[str]) -> None:
    if args[0] in {"-v", "--version", "version"}:
        print(f"{APP_NAME} {__version__}")
        return
    if args[0] in {"--update", "update"}:
        update_app()
        return
    if args[0] in {"-h", "--help", "help"}:
        print(f"{APP_NAME} {__version__}")
        print("Usage:")
        print("  4saves           Open the interactive menu")
        print("  4saves URL       Download a video with saved defaults")
        print("  4saves audio URL Download audio with saved defaults")
        print("  4saves update    Pull the latest app changes when installed from git")
        print("  4saves --version Show version")
        return
    if len(args) == 1 and "." in args[0]:
        direct_download(load_settings(), normalize_url(args[0]), audio_only=False)
        return
    if len(args) == 2 and args[0] in {"video", "download"}:
        direct_download(load_settings(), normalize_url(args[1]), audio_only=False)
        return
    if len(args) == 2 and args[0] == "audio":
        direct_download(load_settings(), normalize_url(args[1]), audio_only=True)
        return
    status("ERR", f"Unknown option: {args[0]}", "red")


def direct_download(settings: Settings, url: str, audio_only: bool) -> None:
    if audio_only:
        if not require_ytdlp():
            return
    elif not require_video_tools():
        return
    ensure_download_dir(settings)
    args = common_args(settings, url)
    if audio_only:
        extra = [
            "-x",
            "--audio-format",
            settings.audio_format,
            "--audio-quality",
            settings.audio_quality,
            "--embed-thumbnail",
            "--add-metadata",
        ]
    else:
        extra = video_output_args(quality_format(settings.video_quality))
    run_ytdlp(args[:-1] + extra + args[-1:], pause_when_done=False)


def load_settings() -> Settings:
    for config_file in [CONFIG_FILE, LOCAL_CONFIG_FILE]:
        if not config_file.exists():
            continue
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise TypeError("settings must be a JSON object")
            allowed = {field.name for field in fields(Settings)}
            known_data = {key: value for key, value in data.items() if key in allowed}
            return normalize_settings(Settings(**{**asdict(Settings()), **known_data}))
        except (OSError, json.JSONDecodeError, TypeError):
            status("WARN", f"Could not read {config_file}; using defaults.", "yellow")
            pause()
            return Settings()
    return Settings()


def normalize_settings(settings: Settings) -> Settings:
    migrations = {
        "premiere_1080": "1080",
        "premiere_720": "720",
    }
    settings.video_quality = migrations.get(settings.video_quality, settings.video_quality)
    if settings.video_quality not in {"best", "2160", "1440", "1080", "720", "small"}:
        settings.video_quality = "1080"
    if not isinstance(settings.concurrent_fragments, int) or not 1 <= settings.concurrent_fragments <= 16:
        settings.concurrent_fragments = 4
    return settings


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def save_settings(settings: Settings) -> None:
    try:
        atomic_write_text(CONFIG_FILE, json.dumps(asdict(settings), indent=2))
    except OSError as error:
        try:
            atomic_write_text(LOCAL_CONFIG_FILE, json.dumps(asdict(settings), indent=2))
            status("WARN", f"Could not save to {CONFIG_FILE}; saved local settings instead.", "yellow")
        except OSError:
            status("WARN", f"Could not save settings: {error}", "yellow")


def load_history() -> list[DownloadJob]:
    for history_file in [HISTORY_FILE, LOCAL_HISTORY_FILE]:
        if not history_file.exists():
            continue
        try:
            records = json.loads(history_file.read_text(encoding="utf-8"))
            jobs: list[DownloadJob] = []
            for record in records if isinstance(records, list) else []:
                if not isinstance(record, dict):
                    continue
                try:
                    jobs.append(DownloadJob(**record))
                except TypeError:
                    continue
            return jobs
        except (OSError, json.JSONDecodeError):
            return []
    return []


def save_history(jobs: list[DownloadJob]) -> None:
    payload = json.dumps([asdict(job) for job in jobs[-30:]], indent=2)
    try:
        atomic_write_text(HISTORY_FILE, payload)
    except OSError:
        try:
            atomic_write_text(LOCAL_HISTORY_FILE, payload)
        except OSError:
            pass


def add_history_job(args: list[str]) -> DownloadJob:
    url = args[-1] if args else ""
    mode = "Audio" if "-x" in args else "Video"
    now = datetime.now(timezone.utc)
    job = DownloadJob(
        id=now.strftime("%Y%m%d%H%M%S%f"),
        url=url,
        label=f"{mode} from {platform_name(url)}",
        args=list(args),
        status="in_progress",
        created_at=now.isoformat(timespec="seconds"),
    )
    jobs = load_history()
    jobs.append(job)
    save_history(jobs)
    return job


def finish_history_job(job: DownloadJob, exit_code: int) -> None:
    jobs = load_history()
    for saved_job in jobs:
        if saved_job.id == job.id:
            saved_job.status = "completed" if exit_code == 0 else "cancelled" if exit_code == 130 else "failed"
            saved_job.exit_code = exit_code
            saved_job.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            break
    save_history(jobs)


def human_size(size: int) -> str:
    value = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def partial_source_url(platform: str, uploader: str, media_id: str) -> str | None:
    platform = platform.lower()
    if platform in {"youtube", "youtubewebarchive"}:
        return f"https://www.youtube.com/watch?v={media_id}"
    if platform in {"twitch", "twitchvod"}:
        return f"https://www.twitch.tv/videos/{media_id.removeprefix('v')}"
    if platform == "tiktok" and uploader:
        return f"https://www.tiktok.com/@{uploader.removeprefix('@')}/video/{media_id}"
    if platform in {"twitter", "x"} and uploader:
        return f"https://x.com/{uploader.removeprefix('@')}/status/{media_id}"
    if platform == "instagram":
        return f"https://www.instagram.com/p/{media_id}/"
    return None


def active_ytdlp_urls() -> set[str]:
    if os.name == "nt":
        return set()
    try:
        result = subprocess.run(
            ["ps", "-Ao", "command="],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return set()
    urls: set[str] = set()
    for command in result.stdout.splitlines():
        if "yt-dlp" not in command:
            continue
        urls.update(match.rstrip("'\"") for match in re.findall(r"https?://\S+", command))
    return urls


def discover_partial_downloads(settings: Settings) -> list[DownloadJob]:
    root = Path(settings.download_dir).expanduser()
    if not root.exists():
        return []

    groups: dict[tuple[str, str], list[Path]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        if ".part" not in name or any(marker in name for marker in [".stale", ".failed-", ".incomplete-backup"]):
            continue
        match = re.search(r"\[([^\[\]]+)\]", name)
        if not match:
            continue
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        platform = relative.parts[0] if relative.parts else ""
        groups.setdefault((platform, match.group(1)), []).append(path)

    discovered: list[DownloadJob] = []
    active_urls = active_ytdlp_urls()
    for (platform, media_id), paths in groups.items():
        existing: list[tuple[Path, os.stat_result]] = []
        for path in paths:
            try:
                existing.append((path, path.stat()))
            except OSError:
                continue
        if not existing:
            continue
        representative, representative_stat = max(existing, key=lambda item: item[1].st_size)
        relative = representative.relative_to(root)
        uploader = relative.parts[1] if len(relative.parts) > 2 else ""
        url = partial_source_url(platform, uploader, media_id)
        if not url:
            continue
        stats = [item[1] for item in existing]
        total_size = sum(item.st_size for item in stats)
        is_active = url in active_urls or time.time() - max(item.st_mtime for item in stats) < 30
        title = representative.name.split(" [", 1)[0].replace("_", " ")
        args = common_args(settings, url)
        args = args[:-1] + video_output_args(quality_format(settings.video_quality)) + args[-1:]
        discovered.append(
            DownloadJob(
                id=f"discovered:{platform}:{media_id}",
                url=url,
                label=f"{'ACTIVE' if is_active else 'FOUND '} {human_size(total_size)} · {title[:42]}",
                args=args,
                status="active_partial" if is_active else "found_partial",
                created_at=datetime.fromtimestamp(
                    representative_stat.st_mtime, tz=timezone.utc
                ).isoformat(timespec="seconds"),
            )
        )
    return sorted(discovered, key=lambda job: job.created_at, reverse=True)


def ensure_download_dir(settings: Settings) -> None:
    path = Path(settings.download_dir).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        fallback = Path.cwd() / "downloads"
        fallback.mkdir(parents=True, exist_ok=True)
        settings.download_dir = str(fallback)


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def header() -> None:
    print()
    print(color(f"  {APP_NAME.upper()}", Style.bold, Style.cyan))
    print(color(f"  {APP_TAGLINE}", Style.dim))
    print()


def read_menu_key() -> str:
    if os.name == "nt":
        import msvcrt

        key = msvcrt.getwch()
        if key in {"\x00", "\xe0"}:
            return {"H": "up", "P": "down", "G": "home", "O": "end"}.get(msvcrt.getwch(), "")
        return {"\r": "enter", "\x1b": "escape"}.get(key, key.lower())

    import select
    import termios
    import tty

    descriptor = sys.stdin.fileno()
    previous = termios.tcgetattr(descriptor)
    try:
        tty.setraw(descriptor)
        key = os.read(descriptor, 1).decode("utf-8", errors="ignore")
        if key == "\x03":
            raise KeyboardInterrupt
        if key in {"\r", "\n"}:
            return "enter"
        if key != "\x1b":
            return key.lower()
        if not select.select([descriptor], [], [], 0.05)[0]:
            return "escape"
        sequence = os.read(descriptor, 2).decode("utf-8", errors="ignore")
        return {"[A": "up", "[B": "down", "[H": "home", "[F": "end"}.get(sequence, "")
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, previous)


def draw_menu_options(options: list[str], selected: int, redraw: bool) -> None:
    width = terminal_width()
    line_count = len(options) + 2
    if redraw:
        print(f"\033[{line_count}A", end="")
    for index, option in enumerate(options):
        text = f"  › {option}" if index == selected else f"    {option}"
        text = text[:width].ljust(width)
        print("\r\033[2K" + (color(text, Style.bold, Style.reverse) if index == selected else text))
    print("\r\033[2K" + rule())
    escape_hint = "   Esc close" if options[-1].lower() in {"back", "quit", "cancel"} else ""
    print("\r\033[2K" + color(f"  ↑/↓ move   Enter select{escape_hint}", Style.dim))


def menu(title: str, options: list[str]) -> int:
    print(color(title, Style.bold))
    print(rule())
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        for index, option in enumerate(options, start=1):
            print(f" {index:>2}  {option}")
        print(rule())
        while True:
            raw = input("Choose an option: ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return int(raw)

    selected = 0
    draw_menu_options(options, selected, redraw=False)
    print("\033[?25l", end="", flush=True)
    try:
        while True:
            key = read_menu_key()
            if key in {"up", "k"}:
                selected = (selected - 1) % len(options)
            elif key in {"down", "j"}:
                selected = (selected + 1) % len(options)
            elif key == "home":
                selected = 0
            elif key == "end":
                selected = len(options) - 1
            elif key in {"enter", " "}:
                return selected + 1
            elif key in {"escape", "q"} and options[-1].lower() in {"back", "quit", "cancel"}:
                return len(options)
            else:
                continue
            draw_menu_options(options, selected, redraw=True)
    finally:
        print("\033[?25h")


def prompt_url(prompt: str = "Paste URL: ") -> str | None:
    url = normalize_url(input(color(prompt, Style.bold, Style.green)).strip())
    if not url:
        status("WARN", "No URL entered.", "yellow")
        pause()
        return None
    return url


def normalize_url(url: str) -> str:
    if not url or "://" in url:
        return url
    if "." in url.split("/", 1)[0]:
        return f"https://{url}"
    return url


def prompt_text(prompt: str, default: str | None = None) -> str:
    suffix = color(f" [{default}]", Style.dim) if default else ""
    value = input(color(prompt, Style.bold, Style.green) + f"{suffix}: ").strip()
    return value or default or ""


def prompt_path(prompt: str, default: str | None = None) -> Path | None:
    value = prompt_text(prompt, default)
    if not value:
        return None

    try:
        parts = shlex.split(value)
    except ValueError:
        parts = []

    if len(parts) == 1:
        value = parts[0]
    elif (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        value = value[1:-1]

    return Path(value).expanduser()


def prompt_yes_no(prompt: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = input(color(prompt, Style.bold, Style.green) + color(f" ({hint}): ", Style.dim)).strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes"}


def pause() -> None:
    input(color("\nPress Enter to continue...", Style.dim))


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def require_ytdlp() -> bool:
    if command_exists("yt-dlp"):
        return True

    status("MISS", "yt-dlp is not installed or is not in PATH.", "red")
    print(color("Install it with one of these:", Style.bold))
    print("  brew install yt-dlp")
    print("  python3 -m pip install -U yt-dlp")
    pause()
    return False


def require_ffmpeg() -> bool:
    if command_exists("ffmpeg"):
        return True

    status("MISS", "ffmpeg is not installed or is not in PATH.", "red")
    print(color("Install it with:", Style.bold))
    print("  brew install ffmpeg")
    pause()
    return False


def require_video_tools() -> bool:
    return require_ytdlp() and require_ffmpeg()


def platform_name(url: str) -> str:
    host = urlparse(normalize_url(url)).netloc.lower().removeprefix("www.")
    if "youtu.be" in host or "youtube.com" in host:
        return "YouTube"
    if "tiktok.com" in host:
        return "TikTok"
    if "instagram.com" in host:
        return "Instagram"
    if host == "x.com" or host.endswith(".x.com") or "twitter.com" in host:
        return "X/Twitter"
    return "this site"


def base_output_template(settings: Settings) -> str:
    download_dir = str(Path(settings.download_dir).expanduser())
    return str(Path(download_dir) / "%(extractor_key)s" / "%(uploader)s" / "%(title)s [%(id)s].%(ext)s")


def common_args(settings: Settings, url: str) -> list[str]:
    args = [
        "yt-dlp",
        "--ignore-config",
        "--continue",
        "--part",
        "--no-overwrites",
        "--restrict-filenames",
        "--windows-filenames",
        "--trim-filenames",
        "180",
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "--file-access-retries",
        "5",
        "--extractor-retries",
        "5",
        "--retry-sleep",
        "http:exp=1:20",
        "--retry-sleep",
        "fragment:exp=1:20",
        "--socket-timeout",
        "30",
        "--concurrent-fragments",
        str(settings.concurrent_fragments),
        "--quiet",
        "--progress",
        "--newline",
        "--progress-delta",
        "0.5",
        "--color",
        "no_color",
        "--progress-template",
        f"download:{PROGRESS_PREFIX}%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s|%(info.title)s",
        "--progress-template",
        f"postprocess:{POSTPROCESS_PREFIX}%(progress.status)s|%(info.title)s",
        "-o",
        base_output_template(settings),
    ]

    if platform_name(url) == "YouTube" and settings.youtube_ejs:
        args.extend(["--remote-components", "ejs:github"])

    if settings.use_aria2c and command_exists("aria2c"):
        args.extend(["--downloader", "aria2c", "--downloader-args", "aria2c:-x 8 -s 8 -k 1M"])

    args.append(url)
    return args


def with_cookies(args: list[str], settings: Settings) -> list[str]:
    url = args[-1]
    platform = platform_name(url)
    status("LOGIN", f"Cookies can help with private, age-restricted, or login-gated {platform} links.", "yellow")
    if not prompt_yes_no("Use browser cookies for this download?", False):
        return args
    browser = choose_browser(settings.browser_for_cookies)
    return args[:-1] + ["--cookies-from-browser", browser] + args[-1:]


def choose_browser(current: str) -> str:
    if current not in BROWSERS:
        current = "safari"

    labels = [
        f"{BROWSER_LABELS[browser]} ({browser}){' - current' if browser == current else ''}"
        for browser in BROWSERS
    ]
    return BROWSERS[menu("Choose browser for cookies", labels) - 1]


def progress_bar(percent: float, width: int = 28) -> str:
    percent = max(0.0, min(100.0, percent))
    filled = round(width * percent / 100)
    return f"[{'#' * filled}{'-' * (width - filled)}]"


def parse_percent(value: str) -> float:
    match = re.search(r"[\d.]+", value)
    return float(match.group()) if match else 0.0


def render_progress_line(percent_text: str, speed: str, eta: str, title: str) -> None:
    percent = parse_percent(percent_text)
    width = terminal_width()
    details = f"{progress_bar(percent)} {percent:5.1f}%  {speed.strip()}  ETA {eta.strip()}"
    if title:
        details += f"  {title.strip()}"
    details = details[:width]
    if sys.stdout.isatty():
        print(f"\r\033[2K{color(details, Style.cyan)}", end="", flush=True)
    else:
        print(details)


def failure_tips(output: str, url: str) -> list[str]:
    lowered = output.lower()
    tips: list[str] = []
    if "no space left" in lowered or "disk full" in lowered:
        tips.append("Free some storage or choose another download folder.")
    if "unsupported url" in lowered:
        tips.append("The link may not contain media, or this site is not supported yet.")
    if "requested format is not available" in lowered:
        tips.append("Choose a lower quality or use List available formats.")
    if any(marker in lowered for marker in ["sign in", "login required", "age-restricted", "private video"]):
        tips.append("Retry with cookies from the browser where you are signed in.")
    if "cookie" in lowered and any(marker in lowered for marker in ["could not", "failed", "permission"]):
        tips.append("Close the browser fully, or select a different browser for cookies.")
    if any(marker in lowered for marker in ["http error 403", "forbidden", "challenge", "javascript runtime", "ejs"]):
        if platform_name(url) == "YouTube":
            tips.append("Update yt-dlp and verify Deno/Node plus YouTube EJS support in Dependency check.")
        else:
            tips.append("Retry with browser cookies; the site may be blocking automated requests.")
    if "ffmpeg" in lowered and any(marker in lowered for marker in ["not found", "not installed", "error"]):
        tips.append("Install or update ffmpeg, then retry the job.")
    if "postprocessing" in lowered:
        tips.append("The media may already be downloaded; check the destination before retrying.")
    if not tips:
        tips.append("Update yt-dlp, then retry with browser cookies if the site requires a login.")
    return list(dict.fromkeys(tips))


def save_error_log(lines: list[str]) -> Path | None:
    if not lines:
        return None
    content = f"4Saves failure log — {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n\n"
    content += "\n".join(lines[-120:]) + "\n"
    try:
        atomic_write_text(ERROR_LOG_FILE, content)
        return ERROR_LOG_FILE
    except OSError:
        return None


def command_download_root(args: list[str]) -> Path | None:
    try:
        template = args[args.index("-o") + 1]
    except (ValueError, IndexError):
        return None
    static_prefix = template.split("%(", 1)[0]
    candidate = Path(static_prefix).expanduser()
    if not static_prefix.endswith(("/", "\\")):
        candidate = candidate.parent
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate if candidate.exists() else None


def warn_if_storage_low(args: list[str], minimum_free_gb: int = 2) -> None:
    root = command_download_root(args)
    if root is None:
        return
    try:
        free = shutil.disk_usage(root).free
    except OSError:
        return
    if free < minimum_free_gb * 1024**3:
        status("SPACE", f"Only {human_size(free)} is free on {root}. Large downloads may fail.", "yellow")


def run_ytdlp(args: list[str], pause_when_done: bool = True, track_history: bool = True) -> int:
    print()
    status("LOAD", f"Reading media information from {platform_name(args[-1])}...", "blue")
    download_root = command_download_root(args)
    if download_root:
        status("SAVE", str(download_root), "cyan")
    warn_if_storage_low(args)
    if os.environ.get("FOURSAVES_DEBUG"):
        print(color(" ".join(shlex.quote(part) for part in args), Style.dim))

    should_track = track_history and "--skip-download" not in args and "-F" not in args
    job = add_history_job(args) if should_track else None
    process: subprocess.Popen[str] | None = None
    progress_visible = False
    output_lines: list[str] = []
    try:
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.rstrip("\r\n")
            if line.startswith(PROGRESS_PREFIX):
                parts = line[len(PROGRESS_PREFIX) :].split("|", 3)
                while len(parts) < 4:
                    parts.append("")
                render_progress_line(*parts)
                progress_visible = True
                continue
            if line.startswith(POSTPROCESS_PREFIX):
                if progress_visible and sys.stdout.isatty():
                    print()
                parts = line[len(POSTPROCESS_PREFIX) :].split("|", 1)
                stage = parts[0] if parts else "working"
                title = parts[1] if len(parts) > 1 else ""
                status("PROCESS", f"{stage.replace('_', ' ').title()}: {title}", "magenta")
                progress_visible = False
                continue
            if line:
                output_lines.append(line)
                if progress_visible and sys.stdout.isatty():
                    print()
                    progress_visible = False
                print(color(line, Style.dim))
        return_code = process.wait()
    except FileNotFoundError:
        status("MISS", "yt-dlp could not be found.", "red")
        return_code = 127
    except KeyboardInterrupt:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        status("STOP", "Download cancelled.", "yellow")
        return_code = 130

    if progress_visible and sys.stdout.isatty():
        print()
    if job is not None:
        finish_history_job(job, return_code)

    if return_code == 0:
        status("OK", "Finished.", "green")
    else:
        status("ERR", f"yt-dlp exited with code {return_code}.", "red")
        combined_output = "\n".join(output_lines)
        for tip in failure_tips(combined_output, args[-1]):
            status("TIP", tip, "yellow")
        log_path = save_error_log(output_lines)
        if log_path:
            status("LOG", f"Details saved to {log_path}", "blue")
    if pause_when_done:
        pause()
    return return_code


def download_video(settings: Settings) -> None:
    if not require_video_tools():
        return
    url = prompt_url()
    if not url:
        return

    quality_choice = menu(
        "Choose video quality",
            [
            "Best quality",
            "4K if available",
            "Up to 1440p",
            "Up to 1080p",
            "Up to 720p",
            "Smallest MP4",
        ],
    )
    formats = {
        1: compatible_format(),
        2: compatible_format("2160"),
        3: compatible_format("1440"),
        4: compatible_format("1080"),
        5: compatible_format("720"),
        6: "worst[ext=mp4][vcodec^=avc1][acodec^=mp4a]/worst[ext=mp4]/worst",
    }
    args = common_args(settings, url)
    args = args[:-1] + video_output_args(formats[quality_choice]) + args[-1:]
    run_ytdlp(with_cookies(args, settings))


def download_audio(settings: Settings) -> None:
    if not require_ytdlp():
        return
    url = prompt_url()
    if not url:
        return

    format_choice = menu("Choose audio format", ["MP3", "M4A", "Opus", "WAV"])
    audio_format = {1: "mp3", 2: "m4a", 3: "opus", 4: "wav"}[format_choice]
    args = common_args(settings, url)
    args = args[:-1] + [
        "-x",
        "--audio-format",
        audio_format,
        "--audio-quality",
        settings.audio_quality,
        "--embed-thumbnail",
        "--add-metadata",
    ] + args[-1:]
    run_ytdlp(with_cookies(args, settings))


def time_to_seconds(value: str) -> float:
    value = value.strip()
    if not value:
        return 0.0
    parts = value.split(":")
    if len(parts) > 3 or any(not re.fullmatch(r"\d+(?:\.\d+)?", part) for part in parts):
        raise ValueError("Use seconds, MM:SS, or HH:MM:SS")
    numbers = [float(part) for part in parts]
    if len(numbers) > 1 and any(part >= 60 for part in numbers[1:]):
        raise ValueError("Minutes and seconds must be below 60")
    return sum(part * (60 ** index) for index, part in enumerate(reversed(numbers)))


def format_timestamp(seconds: float) -> str:
    whole_seconds = int(seconds)
    hours, remainder = divmod(whole_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def prompt_clip_range() -> str | None:
    if not prompt_yes_no("Download only part of the media?", False):
        return None
    while True:
        start_text = prompt_text("Start time (seconds, MM:SS, or HH:MM:SS)", "0")
        end_text = prompt_text("End time (required)")
        try:
            start = time_to_seconds(start_text)
            end = time_to_seconds(end_text)
            if not end_text or end <= start:
                raise ValueError("End time must be later than start time")
            return f"*{format_timestamp(start)}-{format_timestamp(end)}"
        except ValueError as error:
            status("ERR", str(error), "red")


def choose_download_directory(current: str) -> Path:
    downloads = DEFAULT_DOWNLOAD_DIR
    desktop = Path.home() / "Desktop" / "4Saves"
    choice = menu(
        "Choose download folder",
        [
            f"Current: {current}",
            f"Downloads: {downloads}",
            f"Desktop: {desktop}",
            "Enter another folder",
        ],
    )
    if choice == 1:
        return Path(current).expanduser()
    if choice == 2:
        return downloads
    if choice == 3:
        return desktop
    custom = prompt_path("Download folder", current)
    return custom or Path(current).expanduser()


def change_download_folder(settings: Settings) -> Settings:
    folder = choose_download_directory(settings.download_dir)
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        status("ERR", f"Could not create {folder}: {error}", "red")
        pause()
        return settings
    settings.download_dir = str(folder)
    save_settings(settings)
    status("OK", f"Downloads will be saved to {folder}", "green")
    pause()
    return settings


def quick_custom_download(settings: Settings) -> None:
    if not require_video_tools():
        return
    url = prompt_url()
    if not url:
        return

    mode = menu("What do you want to save?", ["Video", "Audio only"])
    run_settings = Settings(**asdict(settings))
    if prompt_yes_no(f"Use the default folder ({settings.download_dir})?", True) is False:
        folder = choose_download_directory(settings.download_dir)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            run_settings.download_dir = str(folder)
        except OSError as error:
            status("ERR", f"Could not create {folder}: {error}", "red")
            pause()
            return
        if prompt_yes_no("Make this the new default folder?", False):
            settings.download_dir = str(folder)
            save_settings(settings)

    section = prompt_clip_range()
    args = common_args(run_settings, url)
    extra: list[str] = []
    if mode == 1:
        quality = choose_value(
            "Video quality",
            ["best", "2160", "1440", "1080", "720", "small"],
            settings.video_quality,
        )
        extra.extend(video_output_args(quality_format(quality)))
    else:
        audio_format = choose_value(
            "Audio format",
            ["mp3", "m4a", "opus", "wav"],
            settings.audio_format,
        )
        extra.extend(["-x", "--audio-format", audio_format, "--audio-quality", settings.audio_quality, "--embed-thumbnail", "--add-metadata"])
    if section:
        extra.extend(["--download-sections", section])
        if mode == 1:
            extra.append("--force-keyframes-at-cuts")
    args = args[:-1] + extra + args[-1:]
    run_ytdlp(with_cookies(args, settings))


def resume_download(settings: Settings) -> None:
    jobs = load_history()
    unfinished = [job for job in jobs if job.status in {"in_progress", "failed", "cancelled"}]
    unfinished = list(reversed(unfinished[-10:]))
    known_urls = {job.url for job in unfinished}
    discovered = [
        job for job in discover_partial_downloads(settings) if job.url not in known_urls
    ]
    candidates = unfinished + discovered
    if not candidates:
        status("OK", "There are no unfinished downloads.", "green")
        pause()
        return

    labels = []
    for job in candidates:
        if job.status in {"found_partial", "active_partial"}:
            labels.append(job.label)
        else:
            labels.append(f"{job.status.upper():10} {job.label} - {job.url[:38]}")
    labels.append("Back")
    choice = menu("Select a download to continue", labels)
    if choice == len(labels):
        return

    selected = candidates[choice - 1]
    if selected.status == "active_partial":
        status("ACTIVE", "That file is still being downloaded by another process.", "green")
        status("TIP", "Wait for it to finish. If it stops, it will appear as FOUND and can be resumed.", "blue")
        pause()
        return
    for job in jobs:
        if job.id == selected.id:
            job.status = "retried"
            break
    save_history(jobs)
    status("RESUME", "Using the existing partial file instead of starting over when the site allows it.", "blue")
    run_ytdlp(selected.args)


def download_playlist(settings: Settings) -> None:
    if not require_ytdlp():
        return
    url = prompt_url("Paste playlist, profile, channel, or collection URL: ")
    if not url:
        return

    mode = menu("Collection mode", ["Download videos", "Download audio only"])
    if mode == 1 and not require_ffmpeg():
        return
    start = prompt_text("Start item number, blank for beginning")
    end = prompt_text("End item number, blank for all")

    args = common_args(settings, url)
    playlist_bits: list[str] = ["--yes-playlist", "-o", playlist_output_template(settings)]
    if start:
        playlist_bits.extend(["--playlist-start", start])
    if end:
        playlist_bits.extend(["--playlist-end", end])
    if mode == 1:
        playlist_bits.extend(video_output_args(quality_format(settings.video_quality)))
    else:
        playlist_bits.extend(["-x", "--audio-format", settings.audio_format, "--embed-thumbnail", "--add-metadata"])

    args = replace_output_args(args, playlist_bits)
    run_ytdlp(with_cookies(args, settings))


def batch_download(settings: Settings) -> None:
    if not require_ytdlp():
        return

    status("BATCH", "Paste one URL per line. Submit a blank line when finished.", "blue")
    urls: list[str] = []
    while True:
        url = input(color("> ", Style.green)).strip()
        if not url:
            break
        urls.append(url)

    if not urls:
        status("WARN", "No URLs entered.", "yellow")
        pause()
        return

    mode = menu("Batch mode", ["Videos", "Audio only"])
    if mode == 1 and not require_ffmpeg():
        return
    use_cookies = prompt_yes_no("Use browser cookies for this batch?", False)
    browser = settings.browser_for_cookies
    if use_cookies:
        browser = choose_browser(settings.browser_for_cookies)

    failures = 0
    for index, url in enumerate(urls, start=1):
        print()
        status("RUN", f"Starting {index}/{len(urls)}", "blue")
        args = common_args(settings, url)
        if mode == 1:
            args = args[:-1] + video_output_args(quality_format(settings.video_quality)) + args[-1:]
        else:
            args = args[:-1] + [
                "-x",
                "--audio-format",
                settings.audio_format,
                "--audio-quality",
                settings.audio_quality,
                "--embed-thumbnail",
                "--add-metadata",
            ] + args[-1:]
        if use_cookies:
            args = args[:-1] + ["--cookies-from-browser", browser] + args[-1:]
        if run_ytdlp(args, pause_when_done=False) != 0:
            failures += 1

    print()
    if failures:
        status("WARN", f"Batch finished with {failures} failed download(s).", "yellow")
    else:
        status("OK", "Batch finished.", "green")
    pause()


def list_formats(settings: Settings) -> None:
    if not require_ytdlp():
        return
    url = prompt_url()
    if not url:
        return

    status("INFO", f"Checking formats for {platform_name(url)}.", "blue")
    args = ["yt-dlp", "-F", url]
    run_ytdlp(with_cookies(args, settings))


def convert_existing_video() -> None:
    if not require_ffmpeg():
        return

    input_path = prompt_path("Path to video file")
    if input_path is None:
        status("WARN", "No file entered.", "yellow")
        pause()
        return

    if not input_path.exists():
        status("ERR", f"File not found: {input_path}", "red")
        pause()
        return

    output_path = input_path.with_name(f"{input_path.stem} - Premiere.mp4")
    chosen_output_path = prompt_path("Output file", str(output_path))
    if chosen_output_path is None:
        status("WARN", "No output file entered.", "yellow")
        pause()
        return
    output_path = chosen_output_path

    args = build_conversion_args(input_path, output_path)
    run_command(args)


def playlist_output_template(settings: Settings) -> str:
    download_dir = str(Path(settings.download_dir).expanduser())
    return str(Path(download_dir) / "%(extractor_key)s" / "%(playlist_title)s" / "%(playlist_index)03d - %(title)s [%(id)s].%(ext)s")


def replace_output_args(args: list[str], replacement: list[str]) -> list[str]:
    output_index = args.index("-o")
    return args[:output_index] + replacement + args[output_index + 2 :]


def compatible_format(max_height: str | None = None) -> str:
    height_filter = f"[height<={max_height}]" if max_height else ""
    return (
        f"bv*{height_filter}+ba/b{height_filter}/"
        f"bv*[ext=mp4]{height_filter}+ba[ext=m4a]/"
        f"b[ext=mp4]{height_filter}/"
        f"bv*[vcodec^=avc1][ext=mp4]{height_filter}+ba[acodec^=mp4a][ext=m4a]/"
        "b"
    )


def video_output_args(format_selector: str) -> list[str]:
    python = sys.executable.replace('"', '\\"')
    return [
        "-f",
        format_selector,
        "--merge-output-format",
        "mp4",
        "--exec",
        f'after_move:"{python}" -m four_saves.convert "{{}}"',
    ]


def quality_format(quality: str) -> str:
    return {
        "best": compatible_format(),
        "2160": compatible_format("2160"),
        "1440": compatible_format("1440"),
        "1080": compatible_format("1080"),
        "720": compatible_format("720"),
        "small": "worst[ext=mp4][vcodec^=avc1][acodec^=mp4a]/worst[ext=mp4]/worst",
        "premiere_1080": compatible_format("1080"),
        "premiere_720": compatible_format("720"),
    }.get(quality, compatible_format("1080"))


def quality_label(quality: str) -> str:
    return QUALITY_LABELS.get(quality, QUALITY_LABELS["1080"])


def download_subtitles(settings: Settings) -> None:
    if not require_ytdlp():
        return
    url = prompt_url()
    if not url:
        return

    language = prompt_text("Subtitle language", settings.subtitle_language)
    args = common_args(settings, url)
    args = args[:-1] + [
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        language,
        "--convert-subs",
        "srt",
    ] + args[-1:]
    run_ytdlp(with_cookies(args, settings))


def download_metadata_bundle(settings: Settings) -> None:
    if not require_ytdlp():
        return
    url = prompt_url()
    if not url:
        return

    args = common_args(settings, url)
    args = args[:-1] + [
        "--skip-download",
        "--write-thumbnail",
        "--write-info-json",
        "--write-description",
    ] + args[-1:]
    run_ytdlp(with_cookies(args, settings))


def advanced_download(settings: Settings) -> None:
    if not require_ytdlp():
        return
    url = prompt_url()
    if not url:
        return

    status("ADV", "Add extra yt-dlp flags. Example: --dateafter 20250101 --match-filter \"duration < 600\"", "magenta")
    extra = prompt_text("Extra flags")
    args = common_args(settings, url)
    if extra:
        args = args[:-1] + shlex.split(extra) + args[-1:]
    run_ytdlp(with_cookies(args, settings))


def settings_menu(settings: Settings) -> Settings:
    while True:
        clear_screen()
        header()
        panel(["Tune defaults used by video, audio, playlist, and cookie flows."], "Settings")
        options = [
            f"Download folder: {settings.download_dir}",
            f"Default video quality: {quality_label(settings.video_quality)}",
            f"Default audio format: {settings.audio_format}",
            f"Default subtitle language: {settings.subtitle_language}",
            f"Browser for cookies: {settings.browser_for_cookies}",
            f"Use aria2c if available: {'yes' if settings.use_aria2c else 'no'}",
            f"Concurrent stream fragments: {settings.concurrent_fragments}",
            f"YouTube EJS fallback: {'enabled' if settings.youtube_ejs else 'disabled'}",
            "Back",
        ]
        choice = menu("Choose setting", options)

        if choice == 1:
            settings.download_dir = prompt_text("Download folder", settings.download_dir)
            ensure_download_dir(settings)
        elif choice == 2:
            settings.video_quality = choose_value(
                "Default video quality",
                ["best", "2160", "1440", "1080", "720", "small"],
                settings.video_quality,
            )
        elif choice == 3:
            settings.audio_format = choose_value("Default audio format", ["mp3", "m4a", "opus", "wav"], settings.audio_format)
        elif choice == 4:
            settings.subtitle_language = prompt_text("Subtitle language", settings.subtitle_language)
        elif choice == 5:
            settings.browser_for_cookies = choose_browser(settings.browser_for_cookies)
        elif choice == 6:
            settings.use_aria2c = not settings.use_aria2c
        elif choice == 7:
            value = choose_value(
                "Concurrent fragments (higher can be faster, but less gentle)",
                ["1", "2", "4", "8"],
                str(settings.concurrent_fragments),
            )
            settings.concurrent_fragments = int(value)
        elif choice == 8:
            settings.youtube_ejs = not settings.youtube_ejs
        elif choice == 9:
            save_settings(settings)
            return settings

        save_settings(settings)


def choose_value(title: str, values: list[str], current: str) -> str:
    labels = [
        f"{quality_label(value) if value in QUALITY_LABELS else value}{' (current)' if value == current else ''}"
        for value in values
    ]
    return values[menu(title, labels) - 1]


def dependency_menu(settings: Settings) -> None:
    clear_screen()
    header()
    print(color("Dependency Check", Style.bold))
    print(rule())
    checks = [
        ("yt-dlp", "Required downloader"),
        ("ffmpeg", "Required for merging video/audio and audio conversion"),
        ("ffprobe", "Required for compatibility checks"),
        ("aria2c", "Optional faster downloader"),
    ]
    for command, description in checks:
        found = command_exists(command)
        state = color("found", Style.green) if found else color("missing", Style.red)
        print(f" {color(command.ljust(8), Style.bold)} {state:8} {description}")

    js_runtime = "deno" if command_exists("deno") else "node" if command_exists("node") else None
    runtime_state = color(js_runtime or "missing", Style.green if js_runtime else Style.red)
    print(f" {color('JS runtime'.ljust(8), Style.bold)} {runtime_state:8} Recommended for full YouTube support")
    ejs_state = color("enabled", Style.green) if settings.youtube_ejs else color("disabled", Style.yellow)
    print(f" {color('YT EJS'.ljust(8), Style.bold)} {ejs_state:8} Remote fallback for YouTube challenges")

    print()
    choice = menu(
        "Maintenance",
        [
            "Update 4Saves",
            "Show install commands",
            "Update yt-dlp with Homebrew",
            "Update yt-dlp with pip",
            "Back",
        ],
    )
    if choice == 1:
        update_app()
    elif choice == 2:
        print()
        print(color("Recommended Homebrew setup:", Style.bold))
        print("  brew install yt-dlp ffmpeg deno aria2")
        print()
        print(color("Alternative pip setup:", Style.bold))
        print('  python3 -m pip install -U "yt-dlp[default]"')
        pause()
    elif choice == 3:
        run_command(["brew", "upgrade", "yt-dlp"])
    elif choice == 4:
        run_command([sys.executable, "-m", "pip", "install", "-U", "yt-dlp[default]"])


def update_app() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    git_dir = project_dir / ".git"
    if not git_dir.exists():
        status("WARN", "Automatic app updates need a git or package-manager install.", "yellow")
        status("TIP", "For downloaded ZIP installs, download the latest release from GitHub and reinstall.", "blue")
        status("URL", "https://github.com/mofe404/4saves/releases/latest", "cyan")
        pause()
        return

    run_command(["git", "-C", str(project_dir), "pull", "--ff-only"])


def run_command(args: list[str]) -> None:
    print()
    status("RUN", "Starting command", "blue")
    print(color(" ".join(shlex.quote(part) for part in args), Style.dim))
    print()
    try:
        subprocess.run(args, check=False)
    except FileNotFoundError:
        status("MISS", f"{args[0]} could not be found.", "red")
    pause()
