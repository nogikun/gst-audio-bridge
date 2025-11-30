from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ListenerConfig(BaseModel):
    """
    A Pydantic model representing Listener configuration options.
    """

    data_format: Literal["raw", "encoded", "torch_audio"] = Field(
        "raw",
        description="Format of the audio data: 'raw' (bytes), 'encoded' (opus), "
        "'torch_audio' (torch.Tensor).",
    )
    chunk_duration_ms: int = Field(
        20,
        description="Duration of each audio chunk in milliseconds. "
        "Common values: 10, 20, 40, 60ms.",
    )
    sample_rate: int = Field(
        48000,
        description="Sample rate of the audio in Hz.",
    )
    channels: int = Field(
        1,
        description="Number of audio channels.",
    )


class ListenerInitArgs(BaseModel):
    """
    A Pydantic model representing a Listener configuration.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    listen_ip: str = Field("0.0.0.0", description="IP address to listen on for incoming streams.")
    audio_port: int = Field(..., description="UDP port for audio streaming.")
    video_port: Optional[int] = Field(None, description="UDP port for video streaming (optional).")
    config: ListenerConfig = Field(
        default_factory=ListenerConfig, description="Listener configuration options."
    )
