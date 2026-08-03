import time
from typing import Dict, Optional, List
import logging
from app.core.video_stream import VideoStreamReader
from app.core.auto_framing import AutoFramingEngine
from app.core.config import settings

logger = logging.getLogger("CameraManager")

class CameraManager:
    def __init__(self):
        self.cameras: Dict[str, VideoStreamReader] = {}
        self.framing_engines: Dict[str, AutoFramingEngine] = {}
        self.fixed_camera_id: Optional[str] = None
        self._camera_ids: List[str] = []
        self._round_robin_idx: int = 0
        self._last_rotation_time: float = time.time()
        self.rotation_interval: float = 2.0 # Rotate every 2 seconds

    def add_camera(self, camera_id: str, source: str):
        if camera_id not in self.cameras:
            logger.info(f"Adding camera {camera_id} (source: {source})")
            reader = VideoStreamReader(source=source, target_fps=settings.MAX_FPS)
            reader.start()
            self.cameras[camera_id] = reader
            self.framing_engines[camera_id] = AutoFramingEngine()
            if camera_id not in self._camera_ids:
                self._camera_ids.append(camera_id)
        return self.cameras[camera_id]

    def remove_camera(self, camera_id: str):
        if camera_id in self.cameras:
            self.cameras[camera_id].stop()
            del self.cameras[camera_id]
            del self.framing_engines[camera_id]
            if camera_id in self._camera_ids:
                self._camera_ids.remove(camera_id)
            if self.fixed_camera_id == camera_id:
                self.fixed_camera_id = None

    def get_reader(self, camera_id: str) -> Optional[VideoStreamReader]:
        return self.cameras.get(camera_id)

    def get_framing_engine(self, camera_id: str) -> Optional[AutoFramingEngine]:
        return self.framing_engines.get(camera_id)

    def get_active_inference_camera(self) -> Optional[str]:
        if not self._camera_ids:
            return None
            
        if self.fixed_camera_id and self.fixed_camera_id in self.cameras:
            return self.fixed_camera_id
            
        now = time.time()
        if now - self._last_rotation_time > self.rotation_interval:
            self._round_robin_idx = (self._round_robin_idx + 1) % len(self._camera_ids)
            self._last_rotation_time = now
            
        return self._camera_ids[self._round_robin_idx]

camera_manager = CameraManager()

# Initialize from env vars
sources = str(settings.VIDEO_SOURCE).split(",")
for i, src in enumerate(sources):
    src = src.strip()
    if src:
        # if the user just specifies "0", it'll be cam_0
        camera_manager.add_camera(f"cam_{i}", src)
