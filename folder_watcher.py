import time
from PyQt5.QtCore import QObject, pyqtSignal
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv'}

class VideoFileEventHandler(FileSystemEventHandler):
    """Handles file system events and emits a signal when a video is created."""
    file_found = pyqtSignal(str)

    def on_created(self, event):
        if not event.is_directory:
            _, ext = os.path.splitext(event.src_path.lower())
            if ext in VIDEO_EXTENSIONS:
                self.file_found.emit(event.src_path)

class FolderWatcher(QObject):
    """
    Runs a watchdog observer in a separate thread to monitor a folder.
    """
    file_found = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, path_to_watch):
        super().__init__()
        self.path_to_watch = path_to_watch
        self.event_handler = VideoFileEventHandler()
        self.observer = Observer()
        # Connect the handler's signal to this worker's signal
        self.event_handler.file_found.connect(self.file_found)
        self._is_running = True

    def run(self):
        self.observer.schedule(self.event_handler, self.path_to_watch, recursive=False)
        self.observer.start()
        try:
            while self._is_running:
                time.sleep(1)
        finally:
            self.observer.stop()
            self.observer.join()
            self.finished.emit()

    def stop(self):
        self._is_running = False