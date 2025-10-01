from typing import Callable, Optional, Tuple
from moviepy.editor import VideoFileClip, AudioFileClip, vfx, ColorClip, CompositeVideoClip
import os
from config import VideoConfig

class VideoProcessor:
    def __init__(self):
        # Processor is now fully stateless
        pass

    def process_video(self, input_path: str, output_path: str,
                      video_config: VideoConfig,
                      cancel_requested: bool,
                      progress_callback: Optional[Callable[[float], None]] = None
                     ) -> Tuple[bool, str]:
        try:
            if cancel_requested:
                return (True, "Processing cancelled by user.")

            clip = VideoFileClip(input_path)
            original_size = clip.size
            
            # 1. Apply Effects based on VideoConfig
            if video_config.flip_mode == "Horizontal":
                clip = clip.fx(vfx.mirror_x)
            elif video_config.flip_mode == "Vertical":
                clip = clip.fx(vfx.mirror_y)

            if video_config.rotation_angle != 0:
                clip = clip.rotate(video_config.rotation_angle)

            if video_config.zoom_factor > 1.0:
                zoom = video_config.zoom_factor
                w, h = original_size
                crop_w, crop_h = int(w / zoom), int(h / zoom)
                clip = clip.fx(vfx.crop, width=crop_w, height=crop_h, x_center=w/2, y_center=h/2).resize(original_size)

            if video_config.overlay_opacity > 0:
                overlay = ColorClip(size=original_size, color=(0, 0, 0), duration=clip.duration)
                overlay = overlay.set_opacity(video_config.overlay_opacity)
                clip = CompositeVideoClip([clip, overlay])
            
            if video_config.speed != 1.0:
                clip = clip.speedx(video_config.speed)

            if video_config.brightness != 1.0:
                clip = clip.fx(vfx.colorx, video_config.brightness)
            
            # ... Add contrast and saturation if needed, colorx can only do one at a time.
            # For multiple color effects, a custom function with fl_image is better.

            if progress_callback: progress_callback(50)

            # 2. Audio Processing
            if video_config.audio_mode == "Remove":
                clip = clip.without_audio()
            elif video_config.audio_mode == "Replace" and video_config.audio_path:
                try:
                    audio_clip = AudioFileClip(video_config.audio_path)
                    clip = clip.set_audio(audio_clip.set_duration(clip.duration))
                except Exception as e:
                    clip.close()
                    return (False, f"Audio replacement failed: {e}")
            
            if cancel_requested:
                clip.close()
                return (True, "Processing cancelled during transformation.")

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            clip.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
            clip.close()

            if progress_callback: progress_callback(100)
            return (True, output_path)

        except Exception as e:
            if 'clip' in locals() and clip:
                clip.close()
            return (False, f"Video processing error: {str(e)}")