from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

from .domain import DownloadJob, DownloadPreset, JobStatus, utc_now

DEFAULT_DATABASE = Path.home() / ".config" / "4saves" / "jobs.sqlite3"


class JobStore:
    def __init__(self, path: str | Path = DEFAULT_DATABASE) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    preset TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    speed TEXT NOT NULL DEFAULT '',
                    eta TEXT NOT NULL DEFAULT '',
                    output_path TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS jobs_updated_at_idx ON jobs(updated_at DESC)"
            )

    def add(self, job: DownloadJob) -> DownloadJob:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, url, title, platform, preset, output_dir, status,
                    progress, speed, eta, output_path, error, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._values(job),
            )
        return job

    def save(self, job: DownloadJob) -> DownloadJob:
        updated = replace(job, updated_at=utc_now())
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET
                    url = ?, title = ?, platform = ?, preset = ?, output_dir = ?,
                    status = ?, progress = ?, speed = ?, eta = ?, output_path = ?,
                    error = ?, created_at = ?, updated_at = ?
                WHERE id = ?
                """,
                self._values(updated)[1:] + (updated.id,),
            )
        return updated

    def update(self, job_id: str, **changes: Any) -> DownloadJob:
        job = self.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return self.save(replace(job, **changes))

    def get(self, job_id: str) -> DownloadJob | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def list(self, *, limit: int = 250) -> list[DownloadJob]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def queued(self) -> list[DownloadJob]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at",
                (JobStatus.QUEUED.value,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def recover_interrupted(self) -> int:
        interrupted = (
            JobStatus.ANALYZING.value,
            JobStatus.DOWNLOADING.value,
            JobStatus.PROCESSING.value,
        )
        with self._connect() as connection:
            result = connection.execute(
                """
                UPDATE jobs
                SET status = ?, error = ?, updated_at = ?
                WHERE status IN (?, ?, ?)
                """,
                (
                    JobStatus.NEEDS_ATTENTION.value,
                    "4Saves closed before this job finished. Retry to continue the partial download.",
                    utc_now(),
                    *interrupted,
                ),
            )
        return result.rowcount

    @staticmethod
    def _values(job: DownloadJob) -> tuple[Any, ...]:
        return (
            job.id,
            job.url,
            job.title,
            job.platform,
            job.preset.value,
            job.output_dir,
            job.status.value,
            job.progress,
            job.speed,
            job.eta,
            job.output_path,
            job.error,
            job.created_at,
            job.updated_at,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> DownloadJob:
        return DownloadJob(
            id=row["id"],
            url=row["url"],
            title=row["title"],
            platform=row["platform"],
            preset=DownloadPreset(row["preset"]),
            output_dir=row["output_dir"],
            status=JobStatus(row["status"]),
            progress=float(row["progress"]),
            speed=row["speed"],
            eta=row["eta"],
            output_path=row["output_path"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
