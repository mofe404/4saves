from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def is_editor_compatible(input_path: Path) -> bool:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name,codec_type,profile,pix_fmt,sample_rate,channels,avg_frame_rate,r_frame_rate:format=format_name",
                "-of",
                "json",
                str(input_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        data = json.loads(result.stdout)
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        return False
    if result.returncode != 0:
        return False
    streams = data.get("streams", [])
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
    format_name = str(data.get("format", {}).get("format_name", ""))
    video_is_safe = len(videos) == 1 and all(
        stream.get("codec_name") == "h264"
        and stream.get("pix_fmt") == "yuv420p"
        and stream.get("avg_frame_rate") == stream.get("r_frame_rate")
        and stream.get("avg_frame_rate") not in {None, "0/0"}
        for stream in videos
    )
    audio_is_safe = len(audios) <= 1 and all(
        stream.get("codec_name") == "aac"
        and stream.get("profile") in {None, "LC"}
        and str(stream.get("channels", "")).isdigit()
        and int(stream["channels"]) <= 2
        and stream.get("sample_rate") in {"44100", "48000"}
        for stream in audios
    )
    return "mp4" in format_name and video_is_safe and audio_is_safe


def build_conversion_args(input_path: Path, output_path: Path) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-profile:v",
        "high",
        "-tag:v",
        "avc1",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos,format=yuv420p",
        "-fps_mode",
        "cfr",
        "-c:a",
        "aac",
        "-profile:a",
        "aac_low",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-max_muxing_queue_size",
        "4096",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m four_saves.convert <video-file>", file=sys.stderr)
        raise SystemExit(2)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"File not found: {input_path}", file=sys.stderr)
        raise SystemExit(1)

    if is_editor_compatible(input_path):
        print("[OK] Already H.264/AAC MP4 — no conversion needed.")
        return

    temp_path = input_path.with_name(f"{input_path.stem}.compat{input_path.suffix}")
    args = build_conversion_args(input_path, temp_path)
    result = subprocess.run(args, check=False)
    if result.returncode != 0:
        if temp_path.exists():
            temp_path.unlink()
        print(f"Conversion failed; the original file was kept: {input_path}", file=sys.stderr)
        raise SystemExit(result.returncode)

    temp_path.replace(input_path)


if __name__ == "__main__":
    main()
