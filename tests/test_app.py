from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from four_saves.convert import build_conversion_args, is_editor_compatible
from ytdl_mac.app import (
    Settings,
    add_history_job,
    atomic_write_text,
    command_download_root,
    common_args,
    discover_partial_downloads,
    finish_history_job,
    failure_tips,
    format_timestamp,
    load_history,
    load_settings,
    parse_percent,
    progress_bar,
    time_to_seconds,
)


class TimeRangeTests(unittest.TestCase):
    def test_parses_supported_time_formats(self) -> None:
        self.assertEqual(time_to_seconds("90"), 90)
        self.assertEqual(time_to_seconds("01:30"), 90)
        self.assertEqual(time_to_seconds("01:02:03"), 3723)

    def test_rejects_invalid_time(self) -> None:
        with self.assertRaises(ValueError):
            time_to_seconds("1:75")
        with self.assertRaises(ValueError):
            time_to_seconds("later")

    def test_formats_time_for_ytdlp(self) -> None:
        self.assertEqual(format_timestamp(90), "01:30")
        self.assertEqual(format_timestamp(3723), "01:02:03")


class ProgressTests(unittest.TestCase):
    def test_progress_helpers_handle_decorated_values(self) -> None:
        self.assertEqual(parse_percent(" 42.5%"), 42.5)
        self.assertEqual(progress_bar(50, width=10), "[#####-----]")


class ConversionTests(unittest.TestCase):
    def test_skips_files_that_are_already_editor_compatible(self) -> None:
        probe_data = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "pix_fmt": "yuv420p",
                    "avg_frame_rate": "30/1",
                    "r_frame_rate": "30/1",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "profile": "LC",
                    "sample_rate": "48000",
                    "channels": 2,
                },
            ],
            "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
        }
        result = SimpleNamespace(returncode=0, stdout=json.dumps(probe_data))
        with patch("four_saves.convert.subprocess.run", return_value=result):
            self.assertTrue(is_editor_compatible(Path("video.mp4")))

    def test_conversion_uses_universal_editing_defaults(self) -> None:
        args = build_conversion_args(Path("input.webm"), Path("output.mp4"))
        for expected in ["libx264", "avc1", "yuv420p", "cfr", "aac_low", "48000", "+faststart"]:
            self.assertTrue(any(expected in argument for argument in args))


class CommandTests(unittest.TestCase):
    def test_common_command_is_resumable_and_has_structured_progress(self) -> None:
        args = common_args(Settings(download_dir="/tmp/4saves"), "https://example.com/video")
        self.assertIn("--continue", args)
        self.assertIn("--progress-template", args)
        self.assertIn("--quiet", args)
        self.assertEqual(args[-1], "https://example.com/video")

    def test_youtube_command_enables_modern_ejs_and_resilience(self) -> None:
        args = common_args(Settings(), "https://www.youtube.com/watch?v=abc123")
        self.assertIn("ejs:github", args)
        self.assertIn("--ignore-config", args)
        self.assertIn("--retry-sleep", args)
        self.assertEqual(args[args.index("--concurrent-fragments") + 1], "4")

    def test_download_root_is_read_from_output_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = common_args(Settings(download_dir=temp_dir), "https://example.com/video")
            self.assertEqual(command_download_root(args), Path(temp_dir))


class DiagnosticsTests(unittest.TestCase):
    def test_403_youtube_failure_gets_specific_advice(self) -> None:
        tips = failure_tips("ERROR: HTTP Error 403: Forbidden", "https://youtube.com/watch?v=x")
        self.assertTrue(any("Deno/Node" in tip for tip in tips))

    def test_atomic_write_replaces_complete_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            atomic_write_text(path, '{"complete": true}')
            self.assertEqual(path.read_text(encoding="utf-8"), '{"complete": true}')


class SettingsTests(unittest.TestCase):
    def test_future_settings_are_ignored_and_values_are_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text(
                json.dumps({"video_quality": "720", "concurrent_fragments": 99, "future_option": True}),
                encoding="utf-8",
            )
            with patch("ytdl_mac.app.CONFIG_FILE", path), patch(
                "ytdl_mac.app.LOCAL_CONFIG_FILE", Path(temp_dir) / "fallback.json"
            ):
                settings = load_settings()

        self.assertEqual(settings.video_quality, "720")
        self.assertEqual(settings.concurrent_fragments, 4)


class HistoryTests(unittest.TestCase):
    def test_failed_job_remains_available_for_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            history_path = Path(temp_dir) / "history.json"
            with patch("ytdl_mac.app.HISTORY_FILE", history_path), patch(
                "ytdl_mac.app.LOCAL_HISTORY_FILE", Path(temp_dir) / "fallback.json"
            ):
                job = add_history_job(["yt-dlp", "https://example.com/video"])
                finish_history_job(job, 1)
                saved = load_history()

        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].status, "failed")
        self.assertEqual(saved[0].exit_code, 1)

    def test_discovers_partial_files_that_predate_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            partial = Path(temp_dir) / "Youtube" / "Creator" / "A title [abc123].f1.mp4.part"
            partial.parent.mkdir(parents=True)
            partial.write_bytes(b"partial video")
            jobs = discover_partial_downloads(Settings(download_dir=temp_dir))

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].url, "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(jobs[0].status, "active_partial")


if __name__ == "__main__":
    unittest.main()
