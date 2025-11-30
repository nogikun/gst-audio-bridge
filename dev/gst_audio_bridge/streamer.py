"""
GStreamer TX (Transmitter/Streamer) pipeline wrapper.
"""

import gi

gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst  # noqa: E402

from gst_audio_bridge.base import GStreamerPipelineBase  # noqa: E402
from gst_audio_bridge.constants import (  # noqa: E402
    DEFAULT_AUDIO_CHANNELS,
    DEFAULT_AUDIO_RATE,
    DEFAULT_VIDEO_FPS,
    DEFAULT_VIDEO_HEIGHT,
    DEFAULT_VIDEO_WIDTH,
    RTP_PAYLOAD_H264,
    RTP_PAYLOAD_OPUS,
)
from gst_audio_bridge.schemas.streamer import StreamerInitArgs  # noqa: E402


class Streamer(GStreamerPipelineBase):
    """
    A simple GStreamer wrapper class to create and manage a GStreamer TX pipeline.
    Supports video and audio streaming via UDP using RTP.
    """

    def __init__(self, args: StreamerInitArgs):
        """
        Initialize the GStreamer TX pipeline.

        Args:
            args: StreamerInitArgs containing destination IP, ports,
                  and optional video/audio configs.
        """
        super().__init__()
        self.args = args

        # Build and create the pipeline
        self.pipeline_str = self._build_pipeline_string()
        self.pipeline = Gst.parse_launch(self.pipeline_str)

        # Setup bus for message handling
        self._setup_bus()

    def _get_video_config_values(self) -> tuple[int, int, int]:
        """Get video configuration values with defaults."""
        if self.args.video_config:
            return (
                self.args.video_config.width,
                self.args.video_config.height,
                self.args.video_config.fps,
            )
        return DEFAULT_VIDEO_WIDTH, DEFAULT_VIDEO_HEIGHT, DEFAULT_VIDEO_FPS

    def _get_audio_config_values(self) -> tuple[int, int]:
        """Get audio configuration values with defaults."""
        if self.args.audio_config:
            return self.args.audio_config.rate, self.args.audio_config.channels
        return DEFAULT_AUDIO_RATE, DEFAULT_AUDIO_CHANNELS

    def _build_pipeline_string(self) -> str:
        """Build the GStreamer pipeline string with configuration."""
        video_width, video_height, video_fps = self._get_video_config_values()
        audio_rate, audio_channels = self._get_audio_config_values()

        return """
            videotestsrc is-live=true !
            video/x-raw,width={VIDEO_WIDTH},height={VIDEO_HEIGHT},framerate={VIDEO_FPS}/1 !
            x264enc tune=zerolatency speed-preset=ultrafast !
            rtph264pay config-interval=1 pt={H264_PT} !
            udpsink host={DEST_IP} port={VIDEO_PORT}

            audiotestsrc is-live=true !
            audio/x-raw,rate={AUDIO_RATE},channels={AUDIO_CHANNELS} !
            opusenc !
            rtpopuspay pt={OPUS_PT} !
            udpsink host={DEST_IP} port={AUDIO_PORT}
        """.format(
            DEST_IP=self.args.dest_ip,
            VIDEO_PORT=self.args.video_port,
            AUDIO_PORT=self.args.audio_port,
            VIDEO_WIDTH=video_width,
            VIDEO_HEIGHT=video_height,
            VIDEO_FPS=video_fps,
            AUDIO_RATE=audio_rate,
            AUDIO_CHANNELS=audio_channels,
            H264_PT=RTP_PAYLOAD_H264,
            OPUS_PT=RTP_PAYLOAD_OPUS,
        )

    def start(self) -> None:
        """
        Start the GStreamer pipeline and run the main loop.
        This method blocks until stop() is called or an error occurs.
        """
        if self.is_running:
            print("Pipeline is already running.")
            return

        print(
            f"TX Streaming to {self.args.dest_ip} "
            f"(Video:{self.args.video_port}, Audio:{self.args.audio_port})..."
        )
        self.pipeline.set_state(Gst.State.PLAYING)
        self.is_running = True

        # Create and run the main loop
        self.loop = GLib.MainLoop()
        try:
            self.loop.run()
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received.")
        finally:
            self.stop()

    def __call__(self) -> None:
        """Start the GStreamer pipeline (alias for start())."""
        self.start()


if __name__ == "__main__":
    # Example usage
    from gst_audio_bridge.schemas.streamer import AudioConfig, VideoConfig

    args = StreamerInitArgs(
        dest_ip="127.0.0.1",
        video_port=5000,
        audio_port=5001,
        video_config=VideoConfig(width=640, height=480, fps=30),
        audio_config=AudioConfig(rate=48000, channels=1),
    )

    streamer = Streamer(args)
    streamer.start()
