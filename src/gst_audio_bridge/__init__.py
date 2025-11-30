"""
gst-audio-bridge: A lightweight GStreamer wrapper for real-time audio streaming.
"""

from gst_audio_bridge.listener import Listener
from gst_audio_bridge.schemas.listener import (
    ListenerConfig,
    ListenerInitArgs,
)
from gst_audio_bridge.schemas.streamer import (
    AudioConfig,
    StreamerInitArgs,
    VideoConfig,
)
from gst_audio_bridge.streamer import Streamer

__version__ = "0.1.0"
__all__ = [
    "Streamer",
    "Listener",
    "StreamerInitArgs",
    "VideoConfig",
    "AudioConfig",
    "ListenerInitArgs",
    "ListenerConfig",
]
