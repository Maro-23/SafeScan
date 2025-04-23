# services/video.py
import cv2
import tkinter as tk
from PIL import Image, ImageTk
from typing import Optional, Tuple

class VideoStream:
    def __init__(self, video_source: str):
        self.cap = cv2.VideoCapture(video_source)
        if not self.cap.isOpened():
            raise IOError(f"Cannot open video source: {video_source}")
        
        # Original video properties
        self.original_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.original_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
    def get_frame(self, target_size: Optional[Tuple[int, int]] = None) -> Optional[ImageTk.PhotoImage]:
        """Returns a Tkinter-compatible image frame"""
        ret, frame = self.cap.read()
        if not ret:
            return None
            
        # Resize if target specified
        if target_size:
            frame = cv2.resize(frame, target_size)
        
        # Convert to RGB and then to ImageTk format
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return ImageTk.PhotoImage(image=Image.fromarray(rgb_frame))
    
    def get_scaled_dimensions(self, scale_factor: float = 0.5) -> Tuple[int, int]:
        """Returns scaled width/height while maintaining aspect ratio"""
        return (
            int(self.original_width * scale_factor),
            int(self.original_height * scale_factor)
        )
    
    def release(self) -> None:
        self.cap.release()
    
    def restart(self) -> None:
        """Reset video to first frame"""
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)