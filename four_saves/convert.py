from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m four_saves.convert <video-file>", file=sys.stderr)
        raise SystemExit(2)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"File not found: {input_path}", file=sys.stderr)
        raise SystemExit(1)

    temp_path = input_path.with_name(f"{input_path.stem}.compat{input_path.suffix}")
    args = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
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
        str(temp_path),
    ]
    result = subprocess.run(args, check=False)
    if result.returncode != 0:
        if temp_path.exists():
            temp_path.unlink()
        raise SystemExit(result.returncode)

    temp_path.replace(input_path)


if __name__ == "__main__":
    main()
