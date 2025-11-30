from typing import Optional

from pydantic import BaseModel, Field


class VideoConfig(BaseModel):
    """
    A Pydantic model representing video configuration options.
    """

    width: int = Field(640, description="Width of the video.")
    height: int = Field(480, description="Height of the video.")
    fps: int = Field(30, description="Frame rate of the video.")


class AudioConfig(BaseModel):
    """
    A Pydantic model representing audio configuration options.
    """

    rate: int = Field(48000, description="Sample rate of the audio.")
    channels: int = Field(1, description="Number of audio channels.")


class StreamerInitArgs(BaseModel):
    """
    A Pydantic model representing a Streamer configuration.
    """

    dest_ip: str = Field(..., description="Destination IP address for the stream.")
    video_port: int = Field(..., description="UDP port for video streaming.")
    audio_port: int = Field(..., description="UDP port for audio streaming.")
    video_config: Optional[VideoConfig] = Field(
        default_factory=VideoConfig, description="Video configuration options."
    )
    audio_config: Optional[AudioConfig] = Field(
        default_factory=AudioConfig, description="Audio configuration options."
    )
