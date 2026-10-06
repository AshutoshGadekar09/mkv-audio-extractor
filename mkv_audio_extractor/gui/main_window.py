"""Main GUI window for MKV Audio Extractor."""

import logging
import sys
import threading
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QMimeData, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QStyle,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.extractor import (
    ConvertFormat,
    ExtractionMode,
    ExtractionResult,
    ExtractionTask,
    Extractor,
    FileExistsAction,
    build_output_path,
    sanitize_filename,
)
from ..core.probe import AudioTrack, FileInfo, check_ffmpeg, check_ffprobe, probe_file

logger = logging.getLogger(__name__)


class ExtractionWorker(QThread):
    """Worker thread for audio extraction."""

    progress = pyqtSignal(int, int, float, str)  # task_idx, total, pct, msg
    finished = pyqtSignal(list)  # list of ExtractionResult
    log_message = pyqtSignal(str)  # log messages

    def __init__(
        self,
        extractor: Extractor,
        tasks: list[ExtractionTask],
        file_exists_action: FileExistsAction,
    ) -> None:
        super().__init__()
        self.extractor = extractor
        self.tasks = tasks
        self.file_exists_action = file_exists_action

    def run(self) -> None:
        """Run extraction in worker thread."""
        try:
            results = self.extractor.extract_tracks(
                self.tasks,
                file_exists_action=self.file_exists_action,
                progress_callback=self._progress_callback,
            )
            self.finished.emit(results)
        except Exception as e:
            self.log_message.emit(f"Error: {e}")
            self.finished.emit([])

    def _progress_callback(
        self, task_index: int, total_tasks: int, pct: float, msg: str
    ) -> None:
        """Emit progress signal."""
        self.progress.emit(task_index, total_tasks, pct, msg)
        self.log_message.emit(msg)


class TrackCheckBox(QCheckBox):
    """Checkbox for an audio track with associated metadata."""

    def __init__(self, track: AudioTrack, file_info: FileInfo) -> None:
        super().__init__(track.display_name)
        self.track = track
        self.file_info = file_info


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MKV Audio Extractor")
        self.setMinimumSize(900, 700)
        self.setAcceptDrops(True)

        self.extractor = Extractor()
        self.worker: Optional[ExtractionWorker] = None
        self.file_infos: list[FileInfo] = []
        self.track_checkboxes: list[TrackCheckBox] = []

        self._check_dependencies()
        self._setup_ui()
        self._setup_menubar()

    def _check_dependencies(self) -> None:
        """Check that ffmpeg and ffprobe are available."""
        ffprobe_ok, ffprobe_msg = check_ffprobe()
        ffmpeg_ok, ffmpeg_msg = check_ffmpeg()

        if not ffprobe_ok or not ffmpeg_ok:
            msg = "Missing dependencies:\n\n"
            if not ffprobe_ok:
                msg += f"• {ffprobe_msg}\n\n"
            if not ffmpeg_ok:
                msg += f"• {ffmpeg_msg}\n\n"
            QMessageBox.critical(self, "Missing Dependencies", msg)

    def _setup_menubar(self) -> None:
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open Files...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_files)
        file_menu.addAction(open_action)

        open_folder_action = QAction("Open &Folder...", self)
        open_folder_action.setShortcut("Ctrl+Shift+O")
        open_folder_action.triggered.connect(self._open_folder)
        file_menu.addAction(open_folder_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_ui(self) -> None:
        """Build the main UI layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(8)

        # ── File Selection ──
        file_group = QGroupBox("Input Files")
        file_layout = QHBoxLayout()

        self.btn_open = QPushButton("Open Files...")
        self.btn_open.clicked.connect(self._open_files)
        file_layout.addWidget(self.btn_open)

        self.btn_open_folder = QPushButton("Open Folder...")
        self.btn_open_folder.clicked.connect(self._open_folder)
        file_layout.addWidget(self.btn_open_folder)

        self.lbl_files = QLabel("No files selected. Drag and drop MKV files here.")
        self.lbl_files.setStyleSheet("color: #888; padding: 4px;")
        file_layout.addWidget(self.lbl_files, stretch=1)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self._clear_files)
        self.btn_clear.setEnabled(False)
        file_layout.addWidget(self.btn_clear)

        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)

        # ── Splitter: Tracks + Log ──
        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── Audio Tracks ──
        tracks_group = QGroupBox("Audio Tracks")
        tracks_layout = QVBoxLayout()

        # Selection buttons
        sel_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.clicked.connect(self._select_all)
        sel_layout.addWidget(self.btn_select_all)

        self.btn_deselect_all = QPushButton("Deselect All")
        self.btn_deselect_all.clicked.connect(self._deselect_all)
        sel_layout.addWidget(self.btn_deselect_all)

        sel_layout.addWidget(QLabel("Select by language:"))
        self.combo_lang = QComboBox()
        self.combo_lang.setMinimumWidth(150)
        self.combo_lang.currentTextChanged.connect(self._select_by_language)
        sel_layout.addWidget(self.combo_lang)

        sel_layout.addStretch()
        tracks_layout.addLayout(sel_layout)

        # Scrollable track list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.tracks_container = QWidget()
        self.tracks_list_layout = QVBoxLayout(self.tracks_container)
        self.tracks_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.tracks_container)
        tracks_layout.addWidget(scroll, stretch=1)

        tracks_group.setLayout(tracks_layout)
        splitter.addWidget(tracks_group)

        # ── Log Panel ──
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        self.log_text.setStyleSheet(
            "font-family: monospace; font-size: 11px; background: #1e1e1e; color: #ddd;"
        )
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        splitter.addWidget(log_group)

        splitter.setSizes([400, 150])
        main_layout.addWidget(splitter, stretch=1)

        # ── Options ──
        options_group = QGroupBox("Extraction Options")
        opt_layout = QGridLayout()

        # Mode
        opt_layout.addWidget(QLabel("Mode:"), 0, 0)
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Copy (keep original codec)", "Convert"])
        self.combo_mode.currentIndexChanged.connect(self._mode_changed)
        opt_layout.addWidget(self.combo_mode, 0, 1)

        # Format
        opt_layout.addWidget(QLabel("Convert to:"), 0, 2)
        self.combo_format = QComboBox()
        self.combo_format.addItems(["MP3", "AAC (M4A)", "FLAC", "Opus", "WAV"])
        self.combo_format.setEnabled(False)
        opt_layout.addWidget(self.combo_format, 0, 3)

        # Bitrate
        opt_layout.addWidget(QLabel("Bitrate:"), 0, 4)
        self.edit_bitrate = QLineEdit("192k")
        self.edit_bitrate.setMaximumWidth(80)
        self.edit_bitrate.setEnabled(False)
        opt_layout.addWidget(self.edit_bitrate, 0, 5)

        # Output directory
        opt_layout.addWidget(QLabel("Output:"), 1, 0)
        self.edit_output = QLineEdit()
        self.edit_output.setPlaceholderText("Default: folder named after source file")
        opt_layout.addWidget(self.edit_output, 1, 1, 1, 4)

        self.btn_browse_output = QPushButton("Browse...")
        self.btn_browse_output.clicked.connect(self._browse_output)
        opt_layout.addWidget(self.btn_browse_output, 1, 5)

        # File exists action
        opt_layout.addWidget(QLabel("If exists:"), 2, 0)
        self.combo_exists = QComboBox()
        self.combo_exists.addItems(["Rename (add number)", "Overwrite", "Skip"])
        opt_layout.addWidget(self.combo_exists, 2, 1)

        options_group.setLayout(opt_layout)
        main_layout.addWidget(options_group)

        # ── Progress ──
        progress_layout = QHBoxLayout()

        self.progress_overall = QProgressBar()
        self.progress_overall.setFormat("Overall: %p%")
        self.progress_overall.setValue(0)
        progress_layout.addWidget(self.progress_overall, stretch=1)

        self.progress_track = QProgressBar()
        self.progress_track.setFormat("Track: %p%")
        self.progress_track.setValue(0)
        progress_layout.addWidget(self.progress_track, stretch=1)

        main_layout.addLayout(progress_layout)

        # ── Action Buttons ──
        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.btn_extract = QPushButton("  Extract Selected  ")
        self.btn_extract.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: white; "
            "padding: 8px 24px; font-size: 14px; font-weight: bold; "
            "border-radius: 4px; }"
            "QPushButton:hover { background-color: #1d4ed8; }"
            "QPushButton:disabled { background-color: #555; color: #999; }"
        )
        self.btn_extract.clicked.connect(self._start_extraction)
        self.btn_extract.setEnabled(False)
        action_layout.addWidget(self.btn_extract)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet(
            "QPushButton { padding: 8px 16px; font-size: 14px; }"
        )
        self.btn_cancel.clicked.connect(self._cancel_extraction)
        self.btn_cancel.setEnabled(False)
        action_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(action_layout)

        # Status bar
        self.statusBar().showMessage("Ready")

    # ── Drag and Drop ──

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drag events with file URLs."""
        if event.mimeData() and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle dropped files."""
        if event.mimeData() and event.mimeData().hasUrls():
            paths = []
            for url in event.mimeData().urls():
                path = Path(url.toLocalFile())
                if path.suffix.lower() == ".mkv":
                    paths.append(path)
                elif path.is_dir():
                    paths.extend(sorted(path.glob("*.mkv")))

            if paths:
                self._load_files(paths)
            else:
                self.statusBar().showMessage("No MKV files found in dropped items.")

    # ── File Loading ──

    def _open_files(self) -> None:
        """Open file dialog to select MKV files."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select MKV Files",
            str(Path.home()),
            "MKV Files (*.mkv);;All Files (*)",
        )
        if files:
            self._load_files([Path(f) for f in files])

    def _open_folder(self) -> None:
        """Open folder dialog to scan for MKV files."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder", str(Path.home())
        )
        if folder:
            mkv_files = sorted(Path(folder).rglob("*.mkv"))
            if mkv_files:
                self._load_files(mkv_files)
            else:
                QMessageBox.information(
                    self, "No Files", "No MKV files found in the selected folder."
                )

    def _clear_files(self) -> None:
        """Clear all loaded files and tracks."""
        self.file_infos.clear()
        self.track_checkboxes.clear()

        # Clear track list
        while self.tracks_list_layout.count():
            item = self.tracks_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.combo_lang.clear()
        self.lbl_files.setText("No files selected. Drag and drop MKV files here.")
        self.lbl_files.setStyleSheet("color: #888; padding: 4px;")
        self.btn_clear.setEnabled(False)
        self.btn_extract.setEnabled(False)
        self.progress_overall.setValue(0)
        self.progress_track.setValue(0)
        self.statusBar().showMessage("Cleared")

    def _load_files(self, paths: list[Path]) -> None:
        """Load MKV files and probe their audio tracks."""
        self._clear_files()
        self.statusBar().showMessage(f"Probing {len(paths)} file(s)...")
        QApplication.processEvents()

        languages_seen: set[str] = set()
        errors: list[str] = []

        for path in paths:
            try:
                file_info = probe_file(path)
                if file_info.has_audio:
                    self.file_infos.append(file_info)
                    for track in file_info.audio_tracks:
                        languages_seen.add(track.language_name)
                else:
                    errors.append(f"{path.name}: no audio tracks")
            except Exception as e:
                errors.append(f"{path.name}: {e}")
                logger.error("Error probing %s: %s", path, e)

        if not self.file_infos:
            msg = "No files with audio tracks found."
            if errors:
                msg += "\n\nErrors:\n" + "\n".join(errors)
            QMessageBox.warning(self, "No Audio", msg)
            return

        # Populate track checkboxes
        for file_info in self.file_infos:
            if len(self.file_infos) > 1:
                file_label = QLabel(f"📁 {file_info.path.name} ({file_info.display_size})")
                file_label.setStyleSheet("font-weight: bold; padding: 6px 0 2px 0;")
                self.tracks_list_layout.addWidget(file_label)

            for track in file_info.audio_tracks:
                cb = TrackCheckBox(track, file_info)
                cb.setChecked(False)
                cb.stateChanged.connect(self._update_extract_button)
                self.track_checkboxes.append(cb)
                self.tracks_list_layout.addWidget(cb)

        # Populate language combo
        self.combo_lang.addItem("-- Select language --")
        for lang in sorted(languages_seen):
            self.combo_lang.addItem(lang)

        # Update UI
        total_tracks = sum(len(fi.audio_tracks) for fi in self.file_infos)
        self.lbl_files.setText(
            f"{len(self.file_infos)} file(s), {total_tracks} audio track(s)"
        )
        self.lbl_files.setStyleSheet("color: #2563eb; padding: 4px; font-weight: bold;")
        self.btn_clear.setEnabled(True)
        self.statusBar().showMessage(f"Loaded {len(self.file_infos)} file(s)")

        if errors:
            self._log(f"Warnings: {len(errors)} file(s) skipped")
            for err in errors:
                self._log(f"  ⚠ {err}")

    # ── Track Selection ──

    def _select_all(self) -> None:
        """Select all track checkboxes."""
        for cb in self.track_checkboxes:
            cb.setChecked(True)

    def _deselect_all(self) -> None:
        """Deselect all track checkboxes."""
        for cb in self.track_checkboxes:
            cb.setChecked(False)

    def _select_by_language(self, language: str) -> None:
        """Select tracks matching the chosen language."""
        if language == "-- Select language --":
            return
        for cb in self.track_checkboxes:
            if cb.track.language_name == language:
                cb.setChecked(True)

    def _update_extract_button(self) -> None:
        """Enable/disable Extract button based on selection."""
        any_selected = any(cb.isChecked() for cb in self.track_checkboxes)
        self.btn_extract.setEnabled(any_selected)

    # ── Options ──

    def _mode_changed(self, index: int) -> None:
        """Handle extraction mode change."""
        is_convert = index == 1
        self.combo_format.setEnabled(is_convert)
        self.edit_bitrate.setEnabled(is_convert)

    def _browse_output(self) -> None:
        """Browse for output directory."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", str(Path.home())
        )
        if folder:
            self.edit_output.setText(folder)

    # ── Extraction ──

    def _get_extraction_mode(self) -> ExtractionMode:
        """Get the selected extraction mode."""
        return (
            ExtractionMode.CONVERT
            if self.combo_mode.currentIndex() == 1
            else ExtractionMode.COPY
        )

    def _get_convert_format(self) -> Optional[ConvertFormat]:
        """Get the selected conversion format."""
        format_map = {
            0: ConvertFormat.MP3,
            1: ConvertFormat.AAC,
            2: ConvertFormat.FLAC,
            3: ConvertFormat.OPUS,
            4: ConvertFormat.WAV,
        }
        return format_map.get(self.combo_format.currentIndex())

    def _get_file_exists_action(self) -> FileExistsAction:
        """Get the selected file-exists action."""
        action_map = {
            0: FileExistsAction.RENAME,
            1: FileExistsAction.OVERWRITE,
            2: FileExistsAction.SKIP,
        }
        return action_map.get(self.combo_exists.currentIndex(), FileExistsAction.RENAME)

    def _start_extraction(self) -> None:
        """Start the extraction process."""
        selected = [cb for cb in self.track_checkboxes if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select tracks to extract.")
            return

        mode = self._get_extraction_mode()
        convert_format = self._get_convert_format() if mode == ExtractionMode.CONVERT else None
        bitrate = self.edit_bitrate.text().strip() if mode == ExtractionMode.CONVERT else None

        if mode == ExtractionMode.CONVERT and not convert_format:
            QMessageBox.warning(self, "No Format", "Please select a conversion format.")
            return

        # Build tasks
        tasks: list[ExtractionTask] = []
        custom_output = self.edit_output.text().strip()

        for cb in selected:
            if custom_output:
                output_dir = Path(custom_output)
            else:
                output_dir = cb.file_info.path.parent / sanitize_filename(cb.file_info.path.stem)

            output_path = build_output_path(
                cb.file_info, cb.track, output_dir, mode, convert_format
            )

            task = ExtractionTask(
                file_info=cb.file_info,
                track=cb.track,
                output_path=output_path,
                mode=mode,
                convert_format=convert_format,
                bitrate=bitrate,
            )
            tasks.append(task)

        # Start worker
        self.extractor.reset()
        self._set_ui_extracting(True)
        self.log_text.clear()
        self._log(f"Starting extraction of {len(tasks)} track(s)...")
        self.progress_overall.setMaximum(len(tasks))
        self.progress_overall.setValue(0)
        self.progress_track.setValue(0)

        self.worker = ExtractionWorker(
            self.extractor, tasks, self._get_file_exists_action()
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.log_message.connect(self._log)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _cancel_extraction(self) -> None:
        """Cancel the current extraction."""
        self.extractor.cancel()
        self._log("⚠ Cancellation requested...")
        self.statusBar().showMessage("Cancelling...")

    def _set_ui_extracting(self, extracting: bool) -> None:
        """Enable/disable UI elements during extraction."""
        self.btn_extract.setEnabled(not extracting)
        self.btn_cancel.setEnabled(extracting)
        self.btn_open.setEnabled(not extracting)
        self.btn_open_folder.setEnabled(not extracting)
        self.btn_clear.setEnabled(not extracting)
        self.combo_mode.setEnabled(not extracting)
        self.combo_format.setEnabled(not extracting and self.combo_mode.currentIndex() == 1)
        self.edit_bitrate.setEnabled(not extracting and self.combo_mode.currentIndex() == 1)

    def _on_progress(self, task_idx: int, total: int, pct: float, msg: str) -> None:
        """Handle progress updates from worker."""
        self.progress_overall.setValue(task_idx + (1 if pct >= 100 else 0))
        self.progress_track.setValue(int(pct))
        self.statusBar().showMessage(msg)

    def _on_finished(self, results: list[ExtractionResult]) -> None:
        """Handle extraction completion."""
        self._set_ui_extracting(False)
        self.progress_track.setValue(100)
        self.progress_overall.setValue(self.progress_overall.maximum())

        if not results:
            self._log("No results.")
            self.statusBar().showMessage("Done (no results)")
            return

        success = sum(1 for r in results if r.success and not r.skipped)
        skipped = sum(1 for r in results if r.skipped)
        failed = sum(1 for r in results if not r.success)

        self._log("")
        self._log("=" * 50)
        self._log("EXTRACTION COMPLETE")
        self._log("=" * 50)
        self._log(f"  ✓ Extracted: {success}")
        self._log(f"  ⏭ Skipped:   {skipped}")
        self._log(f"  ✗ Failed:    {failed}")

        for r in results:
            if r.success and not r.skipped:
                self._log(f"  ✓ {r.output_path}")
            elif r.skipped:
                self._log(f"  ⏭ {r.output_path} (skipped)")
            else:
                self._log(f"  ✗ {r.task.track.display_name}: {r.error}")

        summary = f"Done: {success} extracted, {skipped} skipped, {failed} failed"
        self.statusBar().showMessage(summary)

        if failed > 0:
            QMessageBox.warning(
                self, "Extraction Complete",
                f"{success} track(s) extracted successfully.\n"
                f"{failed} track(s) failed. Check the log for details.",
            )
        elif success > 0:
            QMessageBox.information(
                self, "Extraction Complete",
                f"Successfully extracted {success} track(s)!",
            )

    # ── Helpers ──

    def _log(self, message: str) -> None:
        """Append a message to the log panel."""
        self.log_text.append(message)
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def _show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About MKV Audio Extractor",
            "<h2>MKV Audio Extractor</h2>"
            "<p>Version 1.0.0</p>"
            "<p>Extract audio tracks from MKV files with ease.</p>"
            "<p>Supports copy mode (lossless) and conversion to "
            "MP3, AAC, FLAC, Opus, and WAV.</p>"
            "<p>Built with PyQt6 and ffmpeg.</p>",
        )


def run_gui() -> int:
    """Launch the GUI application.

    Returns:
        Application exit code.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("MKV Audio Extractor")
    app.setApplicationVersion("1.0.0")

    # Set application style
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    return app.exec()
