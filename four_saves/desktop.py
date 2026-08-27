from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .convert import build_conversion_args, is_editor_compatible
from .database import JobStore
from .domain import DownloadJob, DownloadPreset, JobStatus
from .engine import (
    MediaInfo,
    download_command,
    friendly_error,
    normalize_url,
    parse_output_path,
    parse_probe_output,
    parse_progress,
    probe_command,
)

APP_STYLE = """
QWidget {
    background: #0b0d12;
    color: #f5f7fb;
    font-size: 14px;
}
QMainWindow { background: #0b0d12; }
QLabel#brand { font-size: 27px; font-weight: 800; color: #ffffff; }
QLabel { background: transparent; }
QLabel#tagline { color: #9da7b8; font-size: 14px; }
QLabel#section { font-size: 16px; font-weight: 700; }
QLabel#mediaTitle { font-size: 18px; font-weight: 700; }
QLabel#muted { color: #8f99aa; }
QFrame#card {
    background: #141821;
    border: 1px solid #272d3a;
    border-radius: 14px;
}
QLineEdit, QComboBox {
    background: #10141b;
    border: 1px solid #323949;
    border-radius: 9px;
    padding: 10px 12px;
    min-height: 20px;
}
QLineEdit:focus, QComboBox:focus { border: 2px solid #6d7cff; }
QPushButton {
    background: #222838;
    border: 1px solid #343c50;
    border-radius: 9px;
    padding: 10px 15px;
    font-weight: 650;
}
QPushButton:hover { background: #2a3246; }
QPushButton:focus { border: 2px solid #9ba5ff; }
QPushButton#primary {
    background: #6d5dfc;
    border-color: #8175ff;
    color: white;
}
QPushButton#primary:hover { background: #7a6cff; }
QPushButton:disabled { color: #656d7c; background: #171b24; }
QTableWidget {
    background: #10141b;
    alternate-background-color: #121720;
    border: 1px solid #272d3a;
    border-radius: 12px;
    gridline-color: transparent;
    selection-background-color: #29315a;
    selection-color: #ffffff;
}
QHeaderView::section {
    background: #171c27;
    color: #9da7b8;
    border: none;
    padding: 9px;
    font-weight: 700;
}
QProgressBar {
    background: #202634;
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
}
QProgressBar::chunk { background: #6d5dfc; border-radius: 5px; }
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.store = JobStore()
        self.store.recover_interrupted()
        self.media_info: MediaInfo | None = None
        self.probed_url = ""
        self.probe_output = ""
        self.download_output = ""
        self.download_buffer = ""
        self.current_job_id: str | None = None
        self.cancel_requested = False
        self.downloaded_path = ""
        self.processing_source: Path | None = None
        self.processing_target: Path | None = None
        self.processing_final: Path | None = None

        self.probe_process = QProcess(self)
        self.probe_process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        self.probe_process.readyReadStandardOutput.connect(self._read_probe_output)
        self.probe_process.finished.connect(self._probe_finished)
        self.probe_process.errorOccurred.connect(self._probe_process_error)

        self.download_process = QProcess(self)
        self.download_process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        self.download_process.readyReadStandardOutput.connect(
            self._read_download_output
        )
        self.download_process.finished.connect(self._download_finished)
        self.download_process.errorOccurred.connect(self._download_process_error)

        self.processing_process = QProcess(self)
        self.processing_process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        self.processing_process.finished.connect(self._processing_finished)
        self.processing_process.errorOccurred.connect(self._processing_process_error)

        self.setWindowTitle("4Saves")
        self.setMinimumSize(920, 650)
        self.resize(1080, 760)
        self.setAcceptDrops(True)
        self._build_ui()
        self._refresh_jobs()
        self._start_next_job()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(18)

        brand = QLabel("4Saves")
        brand.setObjectName("brand")
        tagline = QLabel("Save online media. Get files that work.")
        tagline.setObjectName("tagline")
        layout.addWidget(brand)
        layout.addWidget(tagline)

        add_card = QFrame()
        add_card.setObjectName("card")
        add_layout = QVBoxLayout(add_card)
        add_layout.setContentsMargins(18, 18, 18, 18)
        add_layout.setSpacing(12)

        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste a video, post, or audio link")
        self.url_input.setAccessibleName("Media URL")
        self.url_input.returnPressed.connect(self._analyze)
        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.clicked.connect(self._analyze)
        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(self.analyze_button)
        add_layout.addLayout(url_row)

        self.media_title = QLabel("Paste a link to see its details")
        self.media_title.setObjectName("mediaTitle")
        self.media_details = QLabel(
            "4Saves will identify the site, title, duration, and available collection."
        )
        self.media_details.setObjectName("muted")
        self.media_details.setWordWrap(True)
        add_layout.addWidget(self.media_title)
        add_layout.addWidget(self.media_details)

        options_row = QHBoxLayout()
        self.preset_combo = QComboBox()
        for preset in DownloadPreset:
            self.preset_combo.addItem(preset.label, preset.value)
        self.preset_combo.setCurrentIndex(1)
        self.preset_combo.setAccessibleName("Download preset")
        self.folder_input = QLineEdit(str(Path.home() / "Downloads" / "4Saves"))
        self.folder_input.setAccessibleName("Download folder")
        browse_button = QPushButton("Choose folder")
        browse_button.clicked.connect(self._choose_folder)
        options_row.addWidget(self.preset_combo, 1)
        options_row.addWidget(self.folder_input, 2)
        options_row.addWidget(browse_button)
        add_layout.addLayout(options_row)

        self.download_button = QPushButton("Add to downloads")
        self.download_button.setObjectName("primary")
        self.download_button.clicked.connect(self._add_download)
        add_layout.addWidget(self.download_button)
        layout.addWidget(add_card)

        queue_header = QHBoxLayout()
        queue_label = QLabel("Downloads")
        queue_label.setObjectName("section")
        queue_header.addWidget(queue_label)
        queue_header.addStretch()
        retry_button = QPushButton("Retry")
        retry_button.clicked.connect(self._retry_selected)
        reveal_button = QPushButton("Show file")
        reveal_button.clicked.connect(self._reveal_selected)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel_selected)
        queue_header.addWidget(retry_button)
        queue_header.addWidget(reveal_button)
        queue_header.addWidget(self.cancel_button)
        layout.addLayout(queue_header)

        self.jobs_table = QTableWidget(0, 5)
        self.jobs_table.setHorizontalHeaderLabels(
            ["Media", "Preset", "Status", "Progress", "Speed / ETA"]
        )
        self.jobs_table.verticalHeader().setVisible(False)
        self.jobs_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.jobs_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.jobs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.jobs_table.setAlternatingRowColors(True)
        header = self.jobs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 150)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.jobs_table, 1)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("muted")
        layout.addWidget(self.status_label)
        self.setCentralWidget(root)

    def _analyze(self) -> None:
        url = normalize_url(self.url_input.text())
        if not url.startswith(("http://", "https://")):
            self._message("Enter a complete http:// or https:// link.")
            return
        if self.probe_process.state() != QProcess.ProcessState.NotRunning:
            return
        self.media_info = None
        self.probed_url = url
        self.probe_output = ""
        self.analyze_button.setEnabled(False)
        self.media_title.setText("Analyzing link…")
        self.media_details.setText(
            "Reading media information without downloading the file."
        )
        command = probe_command(url)
        self.probe_process.start(command[0], command[1:])

    def _read_probe_output(self) -> None:
        self.probe_output += bytes(self.probe_process.readAllStandardOutput()).decode(
            "utf-8", "replace"
        )

    def _probe_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self.analyze_button.setEnabled(True)
        if exit_code != 0:
            self.media_title.setText("Could not analyze this link")
            self.media_details.setText(friendly_error(self.probe_output))
            return
        try:
            self.media_info = parse_probe_output(self.probe_output)
        except (ValueError, TypeError) as error:
            self.media_title.setText("Could not understand this link")
            self.media_details.setText(str(error))
            return
        info = self.media_info
        self.media_title.setText(info.title)
        details = [info.platform]
        if info.uploader:
            details.append(info.uploader)
        if info.duration is not None:
            minutes, seconds = divmod(info.duration, 60)
            details.append(f"{minutes}:{seconds:02d}")
        if info.is_collection:
            details.append(f"{info.item_count or 'Multiple'} items")
        self.media_details.setText("  •  ".join(details))

    def _probe_process_error(self, error: QProcess.ProcessError) -> None:
        if error is not QProcess.ProcessError.FailedToStart:
            return
        self.analyze_button.setEnabled(True)
        self.media_title.setText("Download engine not found")
        self.media_details.setText(
            "Install yt-dlp or run System health in the terminal version, then try again."
        )

    def _choose_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Choose download folder", self.folder_input.text()
        )
        if selected:
            self.folder_input.setText(selected)

    def _add_download(self) -> None:
        url = normalize_url(self.url_input.text())
        if not url.startswith(("http://", "https://")):
            self._message("Paste a complete link before adding a download.")
            return
        output_dir = Path(self.folder_input.text()).expanduser()
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self._message(f"4Saves could not use that folder:\n{error}")
            return
        preset = DownloadPreset(self.preset_combo.currentData())
        info = self.media_info if self.probed_url == url else None
        job = DownloadJob.create(
            url=url,
            title=info.title if info else url,
            platform=info.platform if info else "Pending analysis",
            preset=preset,
            output_dir=output_dir,
        )
        self.store.add(job)
        self.url_input.clear()
        self.media_info = None
        self.media_title.setText("Added to downloads")
        self.media_details.setText("You can add another link while this one runs.")
        self._refresh_jobs(select_id=job.id)
        self._start_next_job()

    def _start_next_job(self) -> None:
        if (
            self.current_job_id
            or self.processing_process.state() != QProcess.ProcessState.NotRunning
        ):
            return
        queued = self.store.queued()
        if not queued:
            self.status_label.setText("Ready")
            return
        job = queued[0]
        self.current_job_id = job.id
        self.cancel_requested = False
        self.download_output = ""
        self.download_buffer = ""
        self.downloaded_path = ""
        self.store.update(job.id, status=JobStatus.DOWNLOADING, error="")
        self.status_label.setText(f"Downloading {job.title}")
        self._refresh_jobs(select_id=job.id)
        command = download_command(job)
        self.download_process.start(command[0], command[1:])

    def _read_download_output(self) -> None:
        chunk = bytes(self.download_process.readAllStandardOutput()).decode(
            "utf-8", "replace"
        )
        self.download_output += chunk
        self.download_buffer += chunk
        lines = self.download_buffer.splitlines(keepends=True)
        self.download_buffer = ""
        if lines and not lines[-1].endswith(("\n", "\r")):
            self.download_buffer = lines.pop()
        for line in lines:
            self._handle_download_line(line.strip())

    def _handle_download_line(self, line: str) -> None:
        if not self.current_job_id:
            return
        progress = parse_progress(line)
        if progress:
            percent, speed, eta = progress
            self.store.update(
                self.current_job_id, progress=percent, speed=speed, eta=eta
            )
            self._refresh_jobs(select_id=self.current_job_id)
            return
        output_path = parse_output_path(line)
        if output_path:
            self.downloaded_path = output_path
            self.store.update(self.current_job_id, output_path=output_path)

    def _download_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if self.download_buffer:
            self._handle_download_line(self.download_buffer.strip())
            self.download_buffer = ""
        if not self.current_job_id:
            return
        job = self.store.get(self.current_job_id)
        if job is None:
            self.current_job_id = None
            return
        if self.cancel_requested:
            self.store.update(
                job.id,
                status=JobStatus.CANCELLED,
                error="Cancelled. Partial files were kept so this job can be retried.",
            )
            self.current_job_id = None
            self.cancel_requested = False
            self._refresh_jobs(select_id=job.id)
            self._start_next_job()
            return
        if exit_code != 0:
            status = (
                JobStatus.CANCELLED if exit_code in {130, 143, -1} else JobStatus.FAILED
            )
            self.store.update(
                job.id, status=status, error=friendly_error(self.download_output)
            )
            self.current_job_id = None
            self._refresh_jobs(select_id=job.id)
            self._start_next_job()
            return

        path = Path(self.downloaded_path) if self.downloaded_path else None
        needs_compatibility = job.preset in {
            DownloadPreset.UNIVERSAL,
            DownloadPreset.EDIT_READY,
        }
        if (
            path
            and path.exists()
            and needs_compatibility
            and not is_editor_compatible(path)
        ):
            final = (
                path
                if path.suffix.lower() == ".mp4"
                else path.with_name(f"{path.stem} - 4Saves.mp4")
            )
            target = final.with_name(f"{final.stem}.processing.mp4")
            self.processing_source = path
            self.processing_target = target
            self.processing_final = final
            self.store.update(
                job.id, status=JobStatus.PROCESSING, progress=100.0, speed="", eta=""
            )
            self.status_label.setText(f"Preparing {job.title} for editors")
            self._refresh_jobs(select_id=job.id)
            command = build_conversion_args(path, target)
            self.processing_process.start(command[0], command[1:])
            return

        self.store.update(job.id, status=JobStatus.COMPLETED, progress=100.0)
        self.current_job_id = None
        self._refresh_jobs(select_id=job.id)
        self._start_next_job()

    def _download_process_error(self, error: QProcess.ProcessError) -> None:
        if error is not QProcess.ProcessError.FailedToStart or not self.current_job_id:
            return
        job_id = self.current_job_id
        self.store.update(
            job_id,
            status=JobStatus.FAILED,
            error="yt-dlp could not be started. Install or repair the download engine.",
        )
        self.current_job_id = None
        self._refresh_jobs(select_id=job_id)
        self._start_next_job()

    def _processing_finished(
        self, exit_code: int, _status: QProcess.ExitStatus
    ) -> None:
        if not self.current_job_id:
            return
        job_id = self.current_job_id
        source = self.processing_source
        target = self.processing_target
        final = self.processing_final
        if self.cancel_requested:
            if target and target.exists():
                target.unlink(missing_ok=True)
            self.store.update(
                job_id,
                status=JobStatus.CANCELLED,
                error="Compatibility processing was cancelled. The downloaded original was kept.",
            )
        elif exit_code == 0 and source and target and final and target.exists():
            try:
                os.replace(target, final)
                if source != final and source.exists():
                    source.unlink()
                self.store.update(
                    job_id,
                    status=JobStatus.COMPLETED,
                    progress=100.0,
                    output_path=str(final),
                )
            except OSError as error:
                self.store.update(
                    job_id,
                    status=JobStatus.NEEDS_ATTENTION,
                    error=f"The compatible file was created but could not replace the original: {error}",
                    output_path=str(target),
                )
        else:
            if target and target.exists():
                target.unlink(missing_ok=True)
            self.store.update(
                job_id,
                status=JobStatus.NEEDS_ATTENTION,
                error="The media downloaded, but compatibility processing failed. The original was kept.",
            )
        self.current_job_id = None
        self.cancel_requested = False
        self.processing_source = None
        self.processing_target = None
        self.processing_final = None
        self._refresh_jobs(select_id=job_id)
        self._start_next_job()

    def _processing_process_error(self, error: QProcess.ProcessError) -> None:
        if error is not QProcess.ProcessError.FailedToStart or not self.current_job_id:
            return
        job_id = self.current_job_id
        self.store.update(
            job_id,
            status=JobStatus.NEEDS_ATTENTION,
            error="The media downloaded, but FFmpeg could not be started. The original was kept.",
        )
        self.current_job_id = None
        self.processing_source = None
        self.processing_target = None
        self.processing_final = None
        self._refresh_jobs(select_id=job_id)
        self._start_next_job()

    def _refresh_jobs(self, select_id: str | None = None) -> None:
        jobs = self.store.list()
        self.jobs_table.setRowCount(len(jobs))
        selected_row = -1
        for row, job in enumerate(jobs):
            title = QTableWidgetItem(job.title)
            title.setData(Qt.ItemDataRole.UserRole, job.id)
            title.setToolTip(job.url)
            self.jobs_table.setItem(row, 0, title)
            self.jobs_table.setItem(row, 1, QTableWidgetItem(job.preset.label))
            status_text = job.status.value.replace("_", " ").title()
            status_item = QTableWidgetItem(status_text)
            status_item.setToolTip(job.error)
            self.jobs_table.setItem(row, 2, status_item)
            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(round(job.progress))
            progress.setFormat(f"{job.progress:.0f}%")
            self.jobs_table.setCellWidget(row, 3, progress)
            speed_eta = "  ".join(
                part
                for part in (job.speed, f"ETA {job.eta}" if job.eta else "")
                if part
            )
            self.jobs_table.setItem(row, 4, QTableWidgetItem(speed_eta or "—"))
            self.jobs_table.setRowHeight(row, 46)
            if job.id == select_id:
                selected_row = row
        if selected_row >= 0:
            self.jobs_table.selectRow(selected_row)

    def _selected_job(self) -> DownloadJob | None:
        row = self.jobs_table.currentRow()
        if row < 0:
            return None
        item = self.jobs_table.item(row, 0)
        return (
            self.store.get(str(item.data(Qt.ItemDataRole.UserRole))) if item else None
        )

    def _retry_selected(self) -> None:
        job = self._selected_job()
        if not job:
            return
        if job.id == self.current_job_id:
            return
        self.store.update(
            job.id,
            status=JobStatus.QUEUED,
            progress=0.0,
            speed="",
            eta="",
            error="",
        )
        self._refresh_jobs(select_id=job.id)
        self._start_next_job()

    def _cancel_selected(self) -> None:
        job = self._selected_job()
        if not job:
            return
        if job.id == self.current_job_id:
            self.cancel_requested = True
            if self.processing_process.state() != QProcess.ProcessState.NotRunning:
                self.processing_process.terminate()
            else:
                self.download_process.terminate()
            return
        if job.status is JobStatus.QUEUED:
            self.store.update(
                job.id, status=JobStatus.CANCELLED, error="Cancelled before starting."
            )
            self._refresh_jobs(select_id=job.id)

    def _reveal_selected(self) -> None:
        job = self._selected_job()
        if not job:
            return
        target = Path(job.output_path) if job.output_path else Path(job.output_dir)
        if target.is_file():
            if sys.platform == "darwin":
                QProcess.startDetached("open", ["-R", str(target)])
                return
            target = target.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _message(self, message: str) -> None:
        QMessageBox.information(self, "4Saves", message)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        text = event.mimeData().text().strip().splitlines()[0]
        self.url_input.setText(text)
        event.acceptProposedAction()
        self._analyze()

    def closeEvent(self, event: QCloseEvent) -> None:
        for process in (
            self.probe_process,
            self.download_process,
            self.processing_process,
        ):
            if process.state() != QProcess.ProcessState.NotRunning:
                process.terminate()
                process.waitForFinished(1500)
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("4Saves")
    app.setOrganizationName("4Saves")
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
