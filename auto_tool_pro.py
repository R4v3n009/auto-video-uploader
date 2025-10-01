import sys
import os
import json
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QAction, QComboBox, QProgressBar,
    QFileDialog, QMessageBox, QFrame, QScrollArea, QTableView, QHeaderView, 
    QTextEdit, QTabWidget
)
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal, QUrl
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

# Import local modules
from config import VideoConfig, YouTubeConfig
from video_processor import VideoProcessor
from youtube_uploader import YouTubeUploader
from folder_watcher import FolderWatcher
from account_manager import AccountManager
from accounts_dialog import AccountsDialog
from preset_manager import PresetManager
from presets_dialog import PresetsDialog

class ProcessingWorker(QObject):
   
    log_updated = pyqtSignal(str)
    overall_progress_updated = pyqtSignal(int, str)
    task_status_updated = pyqtSignal(int, str)
    task_progress_updated = pyqtSignal(int)
    task_finished = pyqtSignal(str, bool)

    def __init__(self, tasks, processor, uploader):
        super().__init__()
        self.tasks, self.processor, self.uploader = tasks, processor, uploader
        self.is_cancelled = False

    def run(self):
        total_tasks = len(self.tasks)
        for i, task_info in enumerate(self.tasks):
            if self.is_cancelled:
                self.log_updated.emit("Processing cancelled by user.")
                break
            
            row, input_path, yt_config, token_file, output_folder, video_config = task_info.values()
            
            self.task_status_updated.emit(row, "Processing...")
            self.log_updated.emit(f"Processing: {os.path.basename(input_path)}")
            self.overall_progress_updated.emit(int((i / total_tasks) * 100), f"Processing {i+1}/{total_tasks}")
            
            try:
                base_name, _ = os.path.splitext(os.path.basename(input_path))
                output_path = os.path.join(output_folder, f"{base_name}_processed_{int(datetime.now().timestamp())}.mp4")
                
                process_ok, process_msg = self.processor.process_video(
                    input_path, output_path, video_config, self.is_cancelled, self.task_progress_updated.emit
                )
                if not process_ok: raise RuntimeError(process_msg)
                
                self.task_status_updated.emit(row, "Uploading...")
                self.log_updated.emit(f"Uploading: {os.path.basename(output_path)}")
                self.task_progress_updated.emit(0)
                if "{filename}" in yt_config.title:
                    yt_config.title = yt_config.title.replace("{filename}", base_name)
                
                upload_ok, upload_msg = self.uploader.upload_video(
                    output_path, yt_config, token_file, self.task_progress_updated.emit
                )
                if not upload_ok: raise RuntimeError(upload_msg)
                
                self.task_status_updated.emit(row, "Completed")
            except Exception as e:
                self.task_status_updated.emit(row, "Error")
                self.log_updated.emit(f"Error with {os.path.basename(input_path)}: {e}")
        
        self.task_finished.emit("Queue processing finished!", False)

    def stop(self): self.is_cancelled = True

class AutoVideoTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Automation Pro (Preset Edition)")
        self.setGeometry(100, 100, 1600, 900)
        
        self.account_manager = AccountManager()
        self.preset_manager = PresetManager()
        self.processor = VideoProcessor()
        self.uploader = YouTubeUploader()
        self.processing_thread, self.processing_worker = None, None
        self.watcher_thread, self.folder_watcher = None, None
        self.is_processing = False

        self._init_ui()
        self._apply_stylesheet()

    # ==============================================================================
    # >> HÀM _log ĐÃ ĐƯỢC DI CHUYỂN LÊN ĐÂY ĐỂ SỬA LỖI <<
    # ==============================================================================
    def _log(self, message):
        if hasattr(self, 'log_textbox'):
            self.log_textbox.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def _init_ui(self):
        self._create_menu()
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # Left Panel (Queue)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        main_layout.addWidget(left_panel, 2)
        left_layout.addWidget(QLabel("<h2>Queue Dashboard</h2>"))
        self.queue_view = QTableView()
        self.queue_model = QStandardItemModel()
        self.queue_model.setHorizontalHeaderLabels(["Status", "Filename", "Editing Preset", "Upload To Channel"])
        self.queue_view.setModel(self.queue_model)
        header = self.queue_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents); header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents); header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.queue_view.selectionModel().selectionChanged.connect(self.on_queue_selection_changed)
        left_layout.addWidget(self.queue_view)

        # Right Panel (Tabs)
        main_area_widget = QWidget()
        main_area_layout = QVBoxLayout(main_area_widget)
        main_layout.addWidget(main_area_widget, 1)
        self._create_main_area_tabs(main_area_layout)

        # Right Sidebar (Controls)
        sidebar_widget = QWidget(); sidebar_widget.setFixedWidth(450)
        sidebar_layout = QVBoxLayout(sidebar_widget); scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True); scroll_area_content = QWidget()
        self.sidebar_content_layout = QVBoxLayout(scroll_area_content)
        self.sidebar_content_layout.setAlignment(Qt.AlignTop); scroll_area.setWidget(scroll_area_content)
        sidebar_layout.addWidget(QLabel("<h2>Controls</h2>")); sidebar_layout.addWidget(scroll_area)
        main_layout.addWidget(sidebar_widget, 1)

        self._create_queue_controls_section()
        self._create_watched_folder_section()
        self._create_batch_settings_section()
        self._create_processing_controls()
        self._log("Welcome! Manage presets and accounts from the 'Settings' menu.")

    def _create_main_area_tabs(self, layout):
        tab_widget = QTabWidget()
        # Log Tab
        log_widget = QWidget(); log_layout = QVBoxLayout(log_widget)
        log_layout.addWidget(QLabel("<h3>Logs</h3>")); self.log_textbox = QTextEdit()
        self.log_textbox.setReadOnly(True); log_layout.addWidget(self.log_textbox)
        # Preview Tab
        preview_widget = QWidget(); preview_layout = QVBoxLayout(preview_widget)
        preview_layout.addWidget(QLabel("<h3>Video Preview</h3>")); self.player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.video_widget = QVideoWidget(); self.player.setVideoOutput(self.video_widget)
        player_controls = QHBoxLayout(); play_btn, pause_btn, stop_btn = QPushButton("Play"), QPushButton("Pause"), QPushButton("Stop")
        play_btn.clicked.connect(self.player.play); pause_btn.clicked.connect(self.player.pause); stop_btn.clicked.connect(self.player.stop)
        player_controls.addWidget(play_btn); player_controls.addWidget(pause_btn); player_controls.addWidget(stop_btn)
        preview_layout.addWidget(self.video_widget); preview_layout.addLayout(player_controls)
        tab_widget.addTab(log_widget, "Logs"); tab_widget.addTab(preview_widget, "Preview")
        layout.addWidget(tab_widget); self.main_tabs = tab_widget

    def _create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        save_action = QAction("Save Session...", self); load_action = QAction("Load Session...", self)
        save_action.triggered.connect(self.save_session); load_action.triggered.connect(self.load_session)
        file_menu.addAction(save_action); file_menu.addAction(load_action)
        
        settings_menu = menubar.addMenu("Settings")
        presets_action = QAction("Manage Presets...", self)
        accounts_action = QAction("Manage YouTube Accounts...", self)
        presets_action.triggered.connect(self.open_presets_dialog)
        accounts_action.triggered.connect(self.open_accounts_dialog)
        settings_menu.addAction(presets_action); settings_menu.addAction(accounts_action)

    def open_presets_dialog(self):
        dialog = PresetsDialog(self.preset_manager, self)
        dialog.exec_()
        self.refresh_preset_combos()

    def open_accounts_dialog(self):
        dialog = AccountsDialog(self.account_manager, self)
        dialog.exec_()
        self.refresh_channel_combos()

    def _create_section(self, title):
        frame = QFrame(); frame.setObjectName("SectionFrame"); layout = QVBoxLayout(frame)
        layout.addWidget(QLabel(f"<h4>{title}</h4>")); self.sidebar_content_layout.addWidget(frame)
        return layout

    def on_queue_selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if not indexes:
            self.player.stop()
            return
        selected_row = indexes[0].row()
        path_item = self.queue_model.item(selected_row, 1)
        video_path = path_item.data(Qt.UserRole)
        if video_path and os.path.exists(video_path):
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(video_path)))
            self.main_tabs.setCurrentIndex(1)
            self.player.play()
        else:
            self.player.stop()

    def save_session(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Session", "", "JSON Files (*.json)")
        if not file_path: return
        session_data = {
            "batch_settings": {"output_folder": self.output_entry.text(), "title_template": self.title_entry.text()},
            "queue": []
        }
        for row in range(self.queue_model.rowCount()):
            channel_combo = self.queue_view.indexWidget(self.queue_model.index(row, 3))
            preset_combo = self.queue_view.indexWidget(self.queue_model.index(row, 2))
            session_data["queue"].append({
                "video_path": self.queue_model.item(row, 1).data(Qt.UserRole),
                "selected_token_file": channel_combo.currentData() if channel_combo else None,
                "selected_preset": preset_combo.currentText() if preset_combo else "None (No Effects)"
            })
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=4)
            self._log(f"Session saved successfully to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save session: {e}")

    def load_session(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Session", "", "JSON Files (*.json)")
        if not file_path: return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            self.clear_queue()
            self.output_entry.setText(session_data.get("batch_settings", {}).get("output_folder", ""))
            self.title_entry.setText(session_data.get("batch_settings", {}).get("title_template", ""))
            for task_data in session_data.get("queue", []):
                self._add_item_to_model(task_data["video_path"])
                new_row_index = self.queue_model.rowCount() - 1
                preset_combo = self.queue_view.indexWidget(self.queue_model.index(new_row_index, 2))
                if preset_combo:
                    index = preset_combo.findText(task_data["selected_preset"])
                    if index != -1: preset_combo.setCurrentIndex(index)
                channel_combo = self.queue_view.indexWidget(self.queue_model.index(new_row_index, 3))
                if channel_combo:
                    index = channel_combo.findData(task_data["selected_token_file"])
                    if index != -1: channel_combo.setCurrentIndex(index)
            self._log(f"Session loaded successfully from {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load session: {e}")

    def _create_queue_controls_section(self):
        layout = self._create_section("1. Queue Management")
        add_videos_btn, add_folder_btn = QPushButton("Add Videos"), QPushButton("Add Folder")
        remove_btn, clear_btn = QPushButton("Remove Selected"), QPushButton("Clear All")
        add_videos_btn.clicked.connect(self.add_videos_to_queue)
        add_folder_btn.clicked.connect(self.add_folder_to_queue)
        remove_btn.clicked.connect(self.remove_selected_from_queue)
        clear_btn.clicked.connect(self.clear_queue)
        btn_layout1 = QHBoxLayout(); btn_layout1.addWidget(add_videos_btn); btn_layout1.addWidget(add_folder_btn)
        btn_layout2 = QHBoxLayout(); btn_layout2.addWidget(remove_btn); btn_layout2.addWidget(clear_btn)
        layout.addLayout(btn_layout1); layout.addLayout(btn_layout2)

    def _create_watched_folder_section(self):
        layout = self._create_section("2. Watched Folder (Auto-Add)")
        self.watched_folder_entry = QLineEdit()
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.select_watched_folder)
        folder_layout = QHBoxLayout(); folder_layout.addWidget(self.watched_folder_entry); folder_layout.addWidget(browse_btn)
        layout.addLayout(folder_layout)
        self.watch_toggle_btn = QPushButton("Start Watching"); self.watch_toggle_btn.setCheckable(True)
        self.watch_toggle_btn.toggled.connect(self.toggle_watching)
        layout.addWidget(self.watch_toggle_btn)

    def _create_batch_settings_section(self):
        layout = self._create_section("3. Batch Settings")
        self.output_entry = self._add_file_selector(layout, "Output Folder:", is_folder=True)
        self.title_entry = self._add_line_edit(layout, "YouTube Title Template:")
        self.title_entry.setText("{filename} - My Awesome Video")
        self.title_entry.setToolTip("Use {filename} to insert the video's original name.")

    def _create_processing_controls(self):
        layout = self._create_section("4. Processing")
        self.btn_start = QPushButton("Start Queue Processing"); self.btn_start.setFixedHeight(40)
        self.btn_cancel = QPushButton("Cancel"); self.btn_cancel.setFixedHeight(40); self.btn_cancel.setEnabled(False)
        self.btn_start.clicked.connect(self.start_processing)
        self.btn_cancel.clicked.connect(self.cancel_processing)
        btn_layout = QHBoxLayout(); btn_layout.addWidget(self.btn_start); btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        self.overall_progress_label = QLabel("Ready")
        self.overall_progress_bar = QProgressBar()
        self.task_progress_bar = QProgressBar()
        layout.addWidget(self.overall_progress_label); layout.addWidget(self.overall_progress_bar)
        layout.addWidget(QLabel("Current File Progress:")); layout.addWidget(self.task_progress_bar)

    def _add_file_selector(self, layout, label_text, is_folder=False):
        layout.addWidget(QLabel(label_text))
        entry = QLineEdit()
        button = QPushButton("Browse")
        def select():
            path = QFileDialog.getExistingDirectory(self, "Select Folder") if is_folder else ""
            if path: entry.setText(path)
        button.clicked.connect(select)
        h_layout = QHBoxLayout(); h_layout.addWidget(entry); h_layout.addWidget(button)
        layout.addLayout(h_layout)
        return entry

    def _add_line_edit(self, layout, label_text):
        layout.addWidget(QLabel(label_text))
        entry = QLineEdit()
        layout.addWidget(entry)
        return entry
    
    def refresh_preset_combos(self):
        presets = ["None (No Effects)"] + list(self.preset_manager.get_presets().keys())
        for row in range(self.queue_model.rowCount()):
            combo = self.queue_view.indexWidget(self.queue_model.index(row, 2))
            if isinstance(combo, QComboBox):
                current_selection = combo.currentText()
                combo.clear()
                combo.addItems(presets)
                index = combo.findText(current_selection)
                if index != -1: combo.setCurrentIndex(index)

    def refresh_channel_combos(self):
        accounts = self.account_manager.get_accounts()
        for row in range(self.queue_model.rowCount()):
            combo = self.queue_view.indexWidget(self.queue_model.index(row, 3))
            if isinstance(combo, QComboBox):
                current_selection = combo.currentData()
                combo.clear()
                for acc in accounts: combo.addItem(acc['name'], acc['token_file'])
                index = combo.findData(current_selection)
                if index != -1: combo.setCurrentIndex(index)
    
    def _add_item_to_model(self, file_path):
        row_count = self.queue_model.rowCount()
        status_item = QStandardItem("Queued"); filename_item = QStandardItem(os.path.basename(file_path))
        filename_item.setData(file_path, Qt.UserRole)
        self.queue_model.appendRow([status_item, filename_item, QStandardItem(), QStandardItem()])
        
        preset_combo = QComboBox()
        preset_combo.addItem("None (No Effects)")
        for name in self.preset_manager.get_presets().keys():
            preset_combo.addItem(name)
        self.queue_view.setIndexWidget(self.queue_model.index(row_count, 2), preset_combo)
        
        channel_combo = QComboBox()
        for acc in self.account_manager.get_accounts():
            channel_combo.addItem(acc['name'], acc['token_file'])
        self.queue_view.setIndexWidget(self.queue_model.index(row_count, 3), channel_combo)

    def add_videos_to_queue(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Videos", "", "Video Files (*.mp4 *.mkv *.avi *.mov)")
        for file in files: self._add_item_to_model(file)

    def add_folder_to_queue(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            for root, _, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(('.mp4','.mkv','.avi','.mov')): self._add_item_to_model(os.path.join(root, file))

    def remove_selected_from_queue(self):
        indexes = self.queue_view.selectionModel().selectedRows()
        for index in sorted(indexes, reverse=True): self.queue_model.removeRow(index.row())

    def clear_queue(self): self.queue_model.removeRows(0, self.queue_model.rowCount())

    def select_watched_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Watch")
        if folder: self.watched_folder_entry.setText(folder)

    def toggle_watching(self, checked):
        if checked:
            folder = self.watched_folder_entry.text()
            if not os.path.isdir(folder):
                QMessageBox.warning(self, "Error", "Invalid folder."); self.watch_toggle_btn.setChecked(False); return
            self.watcher_thread = QThread(); self.folder_watcher = FolderWatcher(folder)
            self.folder_watcher.moveToThread(self.watcher_thread)
            self.folder_watcher.file_found.connect(self._add_item_to_model)
            self.watcher_thread.started.connect(self.folder_watcher.run)
            self.watcher_thread.start(); self.watch_toggle_btn.setText("Stop Watching"); self._log(f"Watching: {folder}")
        else:
            if self.folder_watcher: self.folder_watcher.stop()
            if self.watcher_thread: self.watcher_thread.quit(); self.watcher_thread.wait()
            self.watch_toggle_btn.setText("Start Watching"); self._log("Stopped watching.")
    
    def start_processing(self):
        if self.is_processing: return
        if self.queue_model.rowCount() == 0: return QMessageBox.information(self, "Info", "Queue is empty.")
        output_folder = self.output_entry.text()
        if not output_folder or not os.path.isdir(output_folder): return QMessageBox.critical(self, "Error", "Invalid output folder.")
        
        tasks = []
        for row in range(self.queue_model.rowCount()):
            channel_combo = self.queue_view.indexWidget(self.queue_model.index(row, 3))
            preset_combo = self.queue_view.indexWidget(self.queue_model.index(row, 2))
            if not channel_combo or channel_combo.currentIndex() == -1:
                return QMessageBox.critical(self, "Error", f"Select upload channel for row {row + 1}.")
            
            preset_name = preset_combo.currentText()
            settings = self.preset_manager.get_preset(preset_name) if preset_name != "None (No Effects)" else {}
            video_config = VideoConfig(**settings)
            
            tasks.append({
                'row': row, 'path': self.queue_model.item(row, 1).data(Qt.UserRole),
                'yt_config': YouTubeConfig(title=self.title_entry.text()),
                'token_file': channel_combo.currentData(), 'output_folder': output_folder,
                'video_config': video_config
            })
        
        self.is_processing = True; self.btn_start.setEnabled(False); self.btn_cancel.setEnabled(True)
        self.processing_thread = QThread()
        self.processing_worker = ProcessingWorker(tasks, self.processor, self.uploader)
        self.processing_worker.moveToThread(self.processing_thread)
        self.processing_thread.started.connect(self.processing_worker.run)
        self.processing_worker.log_updated.connect(self._log)
        self.processing_worker.overall_progress_updated.connect(lambda val, txt: (self.overall_progress_bar.setValue(val), self.overall_progress_label.setText(txt)))
        self.processing_worker.task_status_updated.connect(self.update_task_status)
        self.processing_worker.task_progress_updated.connect(self.task_progress_bar.setValue)
        self.processing_worker.task_finished.connect(self.on_task_finished)
        self.processing_thread.start()

    def update_task_status(self, row, status):
        item = self.queue_model.item(row, 0)
        item.setText(status)
        color = QColor("white")
        if "Completed" in status: color = QColor("#d4edda")
        elif "Error" in status: color = QColor("#f8d7da")
        elif "ing" in status: color = QColor("#fff3cd")
        for col in range(self.queue_model.columnCount()):
            self.queue_model.item(row, col).setBackground(color)

    def on_task_finished(self, message, is_error):
        if is_error: QMessageBox.critical(self, "Error", message)
        else: QMessageBox.information(self, "Finished", message)
        self.processing_thread.quit(); self.processing_thread.wait()
        self.is_processing = False; self.btn_start.setEnabled(True); self.btn_cancel.setEnabled(False)

    def cancel_processing(self):
        if self.is_processing and self.processing_worker: self.processing_worker.stop()
    
    def closeEvent(self, event):
        if self.folder_watcher: self.folder_watcher.stop()
        if self.processing_worker: self.processing_worker.stop()
        event.accept()
        
    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget { background-color: #F0F0F0; color: #000000; font-size: 10pt; }
            QMainWindow { background-color: #EAEAEA; }
            QFrame#SectionFrame { border: 1px solid #D0D0D0; border-radius: 5px; background-color: #FAFAFA; }
            QLabel { background-color: transparent; }
            QLineEdit, QTextEdit, QComboBox, QTableView { background-color: #FFFFFF; border: 1px solid #C0C0C0; border-radius: 4px; padding: 5px; }
            QPushButton { background-color: #0078D7; color: #FFFFFF; border: none; border-radius: 4px; padding: 8px 12px; font-weight: bold; }
            QPushButton:hover { background-color: #005A9E; } QPushButton:disabled { background-color: #A0A0A0; }
            QPushButton:checkable:checked { background-color: #c42b1c; }
            QProgressBar { border: 1px solid #C0C0C0; border-radius: 4px; text-align: center; }
            QProgressBar::chunk { background-color: #0078D7; border-radius: 3px; }
            QScrollArea { border: none; } QHeaderView::section { background-color: #EAEAEA; padding: 4px; border: 1px solid #D0D0D0; font-weight: bold; }
            QTabWidget::pane { border: 1px solid #D0D0D0; border-radius: 5px; }
            QTabBar::tab { background: #EAEAEA; border: 1px solid #D0D0D0; border-bottom-color: #C2C7CB; border-top-left-radius: 4px; border-top-right-radius: 4px; min-width: 8ex; padding: 5px; }
            QTabBar::tab:selected { background: #FAFAFA; border-color: #D0D0D0; border-bottom-color: #FAFAFA; }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AutoVideoTool()
    window.show()
    sys.exit(app.exec_())