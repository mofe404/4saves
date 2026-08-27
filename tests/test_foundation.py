from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from four_saves.database import JobStore
from four_saves.domain import DownloadJob, DownloadPreset, JobStatus
from four_saves.engine import (
    download_command,
    friendly_error,
    parse_output_path,
    parse_probe_output,
    parse_progress,
    probe_command,
)


def make_job(
    output_dir: str, preset: DownloadPreset = DownloadPreset.UNIVERSAL
) -> DownloadJob:
    return DownloadJob.create(
        url="https://example.com/watch/abc",
        title="Example",
        platform="Example",
        preset=preset,
        output_dir=output_dir,
    )


class JobStoreTests(unittest.TestCase):
    def test_round_trips_and_updates_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = JobStore(Path(temp_dir) / "jobs.sqlite3")
            job = store.add(make_job(temp_dir))
            updated = store.update(
                job.id,
                status=JobStatus.DOWNLOADING,
                progress=42.5,
                speed="3 MiB/s",
            )

            loaded = store.get(job.id)

        self.assertEqual(updated.status, JobStatus.DOWNLOADING)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.progress, 42.5)
        self.assertEqual(loaded.speed, "3 MiB/s")

    def test_recovers_jobs_interrupted_by_app_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = JobStore(Path(temp_dir) / "jobs.sqlite3")
            job = store.add(make_job(temp_dir))
            store.update(job.id, status=JobStatus.PROCESSING)

            count = store.recover_interrupted()
            recovered = store.get(job.id)

        self.assertEqual(count, 1)
        assert recovered is not None
        self.assertEqual(recovered.status, JobStatus.NEEDS_ATTENTION)
        self.assertIn("Retry", recovered.error)

    def test_queued_jobs_keep_creation_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = JobStore(Path(temp_dir) / "jobs.sqlite3")
            first = store.add(make_job(temp_dir))
            second = store.add(make_job(temp_dir, DownloadPreset.AUDIO))

            queued = store.queued()

        self.assertEqual([job.id for job in queued], [first.id, second.id])


class EngineTests(unittest.TestCase):
    def test_probe_enables_youtube_ejs(self) -> None:
        command = probe_command("https://music.youtube.com/watch?v=abc")
        self.assertIn("--remote-components", command)
        self.assertIn("ejs:github", command)

    def test_parses_media_information(self) -> None:
        output = "warning line\n" + json.dumps(
            {
                "title": "A title",
                "extractor_key": "YouTube",
                "uploader": "Creator",
                "duration": 125,
                "thumbnail": "https://example.com/thumb.jpg",
            }
        )
        info = parse_probe_output(output)
        self.assertEqual(info.title, "A title")
        self.assertEqual(info.duration, 125)
        self.assertFalse(info.is_collection)

    def test_download_command_is_resumable_and_preset_driven(self) -> None:
        job = make_job("/tmp/4saves", DownloadPreset.AUDIO)
        command = download_command(job)
        self.assertIn("--continue", command)
        self.assertIn("--no-playlist", command)
        self.assertIn("--audio-format", command)
        self.assertIn("m4a", command)
        self.assertEqual(command[-1], job.url)

    def test_desktop_conversion_is_not_a_shell_exec_hook(self) -> None:
        command = download_command(make_job("/tmp/4saves", DownloadPreset.EDIT_READY))
        self.assertNotIn("--exec", command)
        self.assertIn("--print", command)

    def test_parses_structured_process_output(self) -> None:
        progress = parse_progress("4SAVES_PROGRESS| 67.4%|2.1 MiB/s|00:12")
        self.assertEqual(progress, (67.4, "2.1 MiB/s", "00:12"))
        self.assertEqual(
            parse_output_path("4SAVES_FILE|/tmp/video.mp4"), "/tmp/video.mp4"
        )

    def test_explains_common_failures(self) -> None:
        message = friendly_error("[youtube] ERROR: HTTP Error 403: Forbidden")
        self.assertIn("YouTube", message)


if __name__ == "__main__":
    unittest.main()
