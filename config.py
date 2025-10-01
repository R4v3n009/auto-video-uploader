from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
import os
import json

@dataclass
class VideoConfig:
    speed: float = 1.0
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    flip_mode: str = "None" # None, Horizontal, Vertical
    audio_mode: str = "Keep Original" # Keep Original, Remove, Replace
    logo_path: Optional[str] = None
    audio_path: Optional[str] = None
    
    # --- Các thuộc tính  cho Preset ---
    zoom_factor: float = 1.0      # e.g., 1.2 for 20% zoom
    rotation_angle: float = 0.0   # in degrees
    overlay_opacity: float = 0.0  # 0.0 to 1.0

@dataclass
class YouTubeConfig:
    title: str = ""
    description: str = ""
    tags: str = "" 
    privacy_status: str = "private" 
    schedule_datetime: Optional[str] = None 

class AppState:
    """A singleton class to hold the application's state."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppState, cls).__new__(cls)
            cls._instance.is_processing = False
            cls._instance.cancel_requested = False
            cls._instance.input_path: Optional[str] = None
            cls._instance.output_folder: Optional[str] = None
            cls._instance.video_config = VideoConfig()
            cls._instance.youtube_config = YouTubeConfig()
        return cls._instance

    def reset_processing_flags(self):
        self.is_processing = False
        self.cancel_requested = False

    def request_cancel(self):

        self.cancel_requested = True
