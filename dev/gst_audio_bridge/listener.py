"""
GStreamer RX (Receiver/Listener) pipeline wrapper.
"""

from queue import Empty, Queue
from threading import Thread
from typing import Any, Callable

import gi
import numpy as np

gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst  # noqa: E402

from gst_audio_bridge.base import GStreamerPipelineBase  # noqa: E402
from gst_audio_bridge.constants import (  # noqa: E402
    DEFAULT_APPSINK_MAX_BUFFERS,
    DEFAULT_QUEUE_MAX_SIZE,
    RTP_PAYLOAD_H264,
    RTP_PAYLOAD_OPUS,
)
from gst_audio_bridge.schemas.listener import ListenerInitArgs  # noqa: E402


class Listener(GStreamerPipelineBase):
    """
    A simple GStreamer wrapper class to create and manage a GStreamer RX pipeline.
    Supports audio receiving via UDP using RTP with real-time data access.

    Data formats:
        - "raw": Raw PCM audio bytes
        - "encoded": Opus encoded audio bytes
        - "torch_audio": torch.Tensor in shape (channels, samples)
    """

    def __init__(self, args: ListenerInitArgs):
        """
        Initialize the GStreamer RX pipeline.

        Args:
            args: ListenerInitArgs containing listen IP, ports, and config.
        """
        super().__init__()
        self.args = args
        self.config = args.config

        # Audio data queue for real-time access
        self._audio_queue: Queue = Queue(maxsize=DEFAULT_QUEUE_MAX_SIZE)

        # Callback for audio data
        self._audio_callback: Callable[[Any], None] | None = None

        # Calculate samples per chunk based on duration
        self._samples_per_chunk = int(
            self.config.sample_rate * self.config.chunk_duration_ms / 1000
        )

        # Build the pipeline
        self._build_pipeline()

        # Setup bus for message handling
        self._setup_bus()

    def _build_audio_pipeline(self) -> str:
        """Build the audio pipeline string based on configuration."""
        if self.config.data_format == "encoded":
            # Capture encoded Opus data before decoding
            return (
                f"udpsrc port={self.args.audio_port} "
                f'caps="application/x-rtp,media=audio,encoding-name=OPUS,payload={RTP_PAYLOAD_OPUS}" ! '
                "rtpopusdepay ! "
                "appsink name=audio_sink emit-signals=true sync=false"
            )
        else:
            # Capture raw PCM data after decoding (raw or torch_audio format)
            return (
                f"udpsrc port={self.args.audio_port} "
                f'caps="application/x-rtp,media=audio,encoding-name=OPUS,payload={RTP_PAYLOAD_OPUS}" ! '
                "rtpopusdepay ! "
                "opusdec ! "
                "audioconvert ! "
                f"audio/x-raw,format=F32LE,rate={self.config.sample_rate},"
                f"channels={self.config.channels} ! "
                f"appsink name=audio_sink emit-signals=true sync=false "
                f"max-buffers={DEFAULT_APPSINK_MAX_BUFFERS} drop=true"
            )

    def _build_video_pipeline(self) -> str:
        """Build the video pipeline string."""
        return (
            f"udpsrc port={self.args.video_port} "
            f'caps="application/x-rtp,media=video,encoding-name=H264,payload={RTP_PAYLOAD_H264}" ! '
            "rtph264depay ! "
            "h264parse ! "
            "avdec_h264 ! "
            "videoconvert ! "
            "autovideosink sync=false"
        )

    def _build_pipeline(self) -> None:
        """Build the GStreamer pipeline based on the configuration."""
        pipeline_elements = [self._build_audio_pipeline()]

        # Add video pipeline if video port is specified
        if self.args.video_port is not None:
            pipeline_elements.append(self._build_video_pipeline())

        self.pipeline_str = " ".join(pipeline_elements)

        # Create the pipeline
        self.pipeline = Gst.parse_launch(self.pipeline_str)

        # Connect appsink signal for audio data
        audio_sink = self.pipeline.get_by_name("audio_sink")
        if audio_sink:
            audio_sink.connect("new-sample", self._on_new_audio_sample)

    def _on_new_audio_sample(self, sink: Gst.Element) -> Gst.FlowReturn:
        """
        Callback for new audio samples from appsink.

        Args:
            sink: The appsink element.

        Returns:
            Gst.FlowReturn.OK to continue receiving samples.
        """
        sample = sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.ERROR

        buffer = sample.get_buffer()
        success, map_info = buffer.map(Gst.MapFlags.READ)

        if not success:
            return Gst.FlowReturn.ERROR

        try:
            data = self._convert_audio_data(map_info.data)
            self._enqueue_audio_data(data)

            # Call callback if registered
            if self._audio_callback is not None:
                self._audio_callback(data)

        finally:
            buffer.unmap(map_info)

        return Gst.FlowReturn.OK

    def _enqueue_audio_data(self, data: Any) -> None:
        """
        Add audio data to the queue, dropping oldest if full.

        Args:
            data: Audio data to enqueue.
        """
        try:
            self._audio_queue.put_nowait(data)
        except Exception:
            # Queue is full, drop oldest and add new
            try:
                self._audio_queue.get_nowait()
                self._audio_queue.put_nowait(data)
            except Exception:
                pass

    def _convert_to_torch_tensor(self, audio_array: np.ndarray) -> Any:
        """
        Convert numpy array to torch tensor.

        Args:
            audio_array: Input numpy array.

        Returns:
            Torch tensor in (channels, samples) format.
        """
        try:
            import torch
        except ImportError:
            raise ImportError(
                "torch is required for 'torch_audio' format. "
                "Install with: pip install torch torchaudio"
            )

        # Reshape to (channels, samples) format for torchaudio compatibility
        if self.config.channels > 1:
            # Interleaved to planar conversion
            audio_array = audio_array.reshape(-1, self.config.channels).T
        else:
            audio_array = audio_array.reshape(1, -1)

        # Convert to torch tensor
        return torch.from_numpy(audio_array.copy())

    def _convert_audio_data(self, raw_data: bytes) -> Any:
        """
        Convert raw audio data to the configured format.

        Args:
            raw_data: Raw PCM audio bytes (F32LE format).

        Returns:
            Converted audio data in the configured format.
        """
        if self.config.data_format == "raw":
            return raw_data

        elif self.config.data_format == "encoded":
            return raw_data

        elif self.config.data_format == "torch_audio":
            # Convert bytes to numpy array (F32LE = float32 little-endian)
            audio_array = np.frombuffer(raw_data, dtype=np.float32)
            return self._convert_to_torch_tensor(audio_array)

        else:
            return raw_data

    def set_audio_callback(self, callback: Callable[[Any], None]) -> None:
        """
        Set a callback function to be called when new audio data is available.

        Args:
            callback: A callable that takes the audio data as argument.
                     Data format depends on config.data_format:
                     - "raw": bytes
                     - "encoded": bytes
                     - "torch_audio": torch.Tensor (channels, samples)
        """
        self._audio_callback = callback

    def get_audio_data(self, timeout: float | None = None) -> Any | None:
        """
        Get the next available audio data chunk from the queue.

        Args:
            timeout: Maximum time to wait in seconds. None for non-blocking.

        Returns:
            Audio data in the configured format, or None if no data available.
        """
        try:
            if timeout is None:
                return self._audio_queue.get_nowait()
            else:
                return self._audio_queue.get(timeout=timeout)
        except Empty:
            return None

    def get_all_audio_data(self) -> list:
        """
        Get all available audio data chunks from the queue.

        Returns:
            List of audio data chunks.
        """
        chunks = []
        while True:
            data = self.get_audio_data()
            if data is None:
                break
            chunks.append(data)
        return chunks

    def _run_loop(self) -> None:
        """Run the GLib main loop in a background thread."""
        try:
            self.loop.run()
        except Exception as e:
            print(f"Main loop error: {e}")
        finally:
            self.is_running = False

    def start(self, blocking: bool = True) -> None:
        """
        Start the GStreamer pipeline.

        Args:
            blocking: If True, run the main loop (blocks until stop()).
                     If False, start pipeline in background thread.
        """
        if self.is_running:
            print("Pipeline is already running.")
            return

        print(
            f"RX Listening on (Audio:{self.args.audio_port}"
            f"{f', Video:{self.args.video_port}' if self.args.video_port else ''})..."
        )
        self.pipeline.set_state(Gst.State.PLAYING)
        self.is_running = True

        if blocking:
            # Create and run the main loop
            self.loop = GLib.MainLoop()
            try:
                self.loop.run()
            except KeyboardInterrupt:
                print("\nKeyboard interrupt received.")
            finally:
                self.stop()
        else:
            # Run main loop in background thread
            self.loop = GLib.MainLoop()
            self._loop_thread = Thread(target=self._run_loop, daemon=True)
            self._loop_thread.start()

    def __call__(self) -> None:
        """Start the GStreamer pipeline (alias for start())."""
        self.start()


if __name__ == "__main__":
    # Example usage with torch_audio format
    import time

    from gst_audio_bridge.schemas.listener import ListenerConfig

    config = ListenerConfig(
        data_format="torch_audio",
        chunk_duration_ms=20,
        sample_rate=48000,
        channels=1,
    )

    args = ListenerInitArgs(
        listen_ip="0.0.0.0",
        audio_port=5001,
        video_port=None,  # Audio only
        config=config,
    )

    # Callback example
    def on_audio(audio_tensor):
        print(f"Received audio: shape={audio_tensor.shape}, dtype={audio_tensor.dtype}")

    listener = Listener(args)
    listener.set_audio_callback(on_audio)

    # Start in non-blocking mode
    listener.start(blocking=False)

    # Poll for data
    try:
        while True:
            data = listener.get_audio_data(timeout=0.1)
            if data is not None:
                print(f"Polled audio: shape={data.shape}")
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
