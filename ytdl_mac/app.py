from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse

from four_saves import __version__


APP_NAME = "4Saves"
APP_TAGLINE = "Save media from YouTube, TikTok, Instagram, and X"
CONFIG_DIR = Path.home() / ".config" / "4saves"
CONFIG_FILE = CONFIG_DIR / "settings.json"
LOCAL_CONFIG_FILE = Path.cwd() / ".4saves-settings.json"
DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "4Saves"
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


def supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def color(text: str, *styles: str) -> str:
    if not supports_color():
        return text
    return "".join(styles) + text + Style.reset


def terminal_width(max_width: int = 82) -> int:
    return min(shutil.get_terminal_size((max_width, 20)).columns, max_width)


def rule(char: str = "-") -> str:
    return color(char * terminal_width(), Style.dim)


def panel(lines: list[str], title: str | None = None) -> None:
    width = terminal_width()
    print(color("+" + "-" * (width - 2) + "+", Style.cyan))
    if title:
        print(color("|", Style.cyan) + " " + color(title.ljust(width - 4), Style.bold, Style.cyan) + " " + color("|", Style.cyan))
        print(color("|" + "-" * (width - 2) + "|", Style.cyan))
    for line in lines:
        clipped = line[: width - 4]
        print(color("|", Style.cyan) + " " + clipped.ljust(width - 4) + " " + color("|", Style.cyan))
    print(color("+" + "-" * (width - 2) + "+", Style.cyan))


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
                f"Download folder: {settings.download_dir}",
                f"Default video: {quality_label(settings.video_quality)}",
                f"Audio format: {settings.audio_format.upper()}",
                "Supported: YouTube, TikTok, Instagram, X/Twitter",
            ],
            "Current Setup",
        )
        choice = menu(
            "What do you want to do?",
            [
                "Download video",
                "Download audio only",
                "Download playlist / profile / collection",
                "Batch download URLs",
                "Convert existing video",
                "List available formats",
                "Download subtitles",
                "Download thumbnail + metadata",
                "Advanced custom download",
                "Settings",
                "Updates / dependency check",
                "Quit",
            ],
        )

        if choice == 1:
            download_video(settings)
        elif choice == 2:
            download_audio(settings)
        elif choice == 3:
            download_playlist(settings)
        elif choice == 4:
            batch_download(settings)
        elif choice == 5:
            convert_existing_video()
        elif choice == 6:
            list_formats(settings)
        elif choice == 7:
            download_subtitles(settings)
        elif choice == 8:
            download_metadata_bundle(settings)
        elif choice == 9:
            advanced_download(settings)
        elif choice == 10:
            settings = settings_menu(settings)
        elif choice == 11:
            dependency_menu()
        elif choice == 12:
            status("DONE", "Done. May your downloads behave themselves.", "green")
            return


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
        print("  4saves update    Pull the latest app changes when installed from git")
        print("  4saves --version Show version")
        return
    status("ERR", f"Unknown option: {args[0]}", "red")


def load_settings() -> Settings:
    for config_file in [CONFIG_FILE, LOCAL_CONFIG_FILE]:
        if not config_file.exists():
            continue
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            return normalize_settings(Settings(**{**asdict(Settings()), **data}))
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
    return settings


def save_settings(settings: Settings) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    except OSError as error:
        try:
            LOCAL_CONFIG_FILE.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
            status("WARN", f"Could not save to {CONFIG_FILE}; saved local settings instead.", "yellow")
        except OSError:
            status("WARN", f"Could not save settings: {error}", "yellow")


def ensure_download_dir(settings: Settings) -> None:
    path = Path(settings.download_dir).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        fallback = Path.cwd() / "downloads"
        fallback.mkdir(parents=True, exist_ok=True)
        settings.download_dir = str(fallback)


def clear_screen() -> None:
    os.system("clear")


def header() -> None:
    width = terminal_width()
    print(color("=" * width, Style.cyan))
    print(color(APP_NAME.center(width), Style.bold, Style.cyan))
    print(color(APP_TAGLINE.center(width), Style.dim))
    print(color("=" * width, Style.cyan))
    print()


def menu(title: str, options: list[str]) -> int:
    print(color(title, Style.bold))
    print(rule())
    for index, option in enumerate(options, start=1):
        number = color(f"{index:>2}", Style.bold, Style.cyan)
        print(f" {number}  {option}")
    print(rule())

    while True:
        raw = input(color("Choose an option: ", Style.bold, Style.green)).strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw)
        status("ERR", "Please enter a valid number.", "red")


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
        "--continue",
        "--no-overwrites",
        "--restrict-filenames",
        "--windows-filenames",
        "--trim-filenames",
        "180",
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "--progress",
        "--newline",
        "-o",
        base_output_template(settings),
    ]

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


def run_ytdlp(args: list[str], pause_when_done: bool = True) -> int:
    print()
    status("RUN", "Starting command", "blue")
    print(color(" ".join(shlex.quote(part) for part in args), Style.dim))
    print()

    try:
        process = subprocess.run(args, check=False)
    except FileNotFoundError:
        status("MISS", "yt-dlp could not be found.", "red")
        if pause_when_done:
            pause()
        return 127
    except KeyboardInterrupt:
        status("STOP", "Download cancelled.", "yellow")
        if pause_when_done:
            pause()
        return 130

    if process.returncode == 0:
        status("OK", "Finished.", "green")
    else:
        status("ERR", f"yt-dlp exited with code {process.returncode}.", "red")
        status("TIP", "Try updating yt-dlp or use browser cookies from the menu.", "yellow")
    if pause_when_done:
        pause()
    return process.returncode


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

    args = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
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
            save_settings(settings)
            return settings

        save_settings(settings)


def choose_value(title: str, values: list[str], current: str) -> str:
    labels = [
        f"{quality_label(value) if value in QUALITY_LABELS else value}{' (current)' if value == current else ''}"
        for value in values
    ]
    return values[menu(title, labels) - 1]


def dependency_menu() -> None:
    clear_screen()
    header()
    print(color("Dependency Check", Style.bold))
    print(rule())
    checks = [
        ("yt-dlp", "Required downloader"),
        ("ffmpeg", "Required for merging video/audio and audio conversion"),
        ("aria2c", "Optional faster downloader"),
    ]
    for command, description in checks:
        found = command_exists(command)
        state = color("found", Style.green) if found else color("missing", Style.red)
        print(f" {color(command.ljust(8), Style.bold)} {state:8} {description}")

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
        print("  brew install yt-dlp ffmpeg aria2")
        print()
        print(color("Alternative pip setup:", Style.bold))
        print("  python3 -m pip install -U yt-dlp")
        pause()
    elif choice == 3:
        run_command(["brew", "upgrade", "yt-dlp"])
    elif choice == 4:
        run_command([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"])


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
