"""
GStreamer TX (Transmitter/Streamer) pipeline wrapper.
"""

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib  # noqa: E402

from gst_audio_bridge.schemas.streamer import StreamerInitArgs  # noqa: E402


class Streamer:
    """
    A simple GStreamer wrapper class to create and manage a GStreamer TX pipeline.
    Supports video and audio streaming via UDP using RTP.
    """

    def __init__(self, args: StreamerInitArgs):
        """
        Initialize the GStreamer TX pipeline.

        Args:
            args: StreamerInitArgs containing destination IP, ports, and optional video/audio configs.
        """
        Gst.init(None)

        self.args = args
        self.loop: GLib.MainLoop | None = None
        self.is_running: bool = False

        # Build pipeline string with configuration
        self.pipeline_str = """
            videotestsrc is-live=true !
            video/x-raw,width={VIDEO_WIDTH},height={VIDEO_HEIGHT},framerate={VIDEO_FRAMERATE}/1 !
            x264enc tune=zerolatency speed-preset=ultrafast !
            rtph264pay config-interval=1 pt=96 !
            udpsink host={DEST_IP} port={VIDEO_PORT}

            audiotestsrc is-live=true !
            audio/x-raw,rate={AUDIO_RATE},channels={AUDIO_CHANNELS} !
            opusenc !
            rtpopuspay pt=97 !
            udpsink host={DEST_IP} port={AUDIO_PORT}
        """.format(
            DEST_IP=args.dest_ip,
            VIDEO_PORT=args.video_port,
            AUDIO_PORT=args.audio_port,
            VIDEO_WIDTH=args.video_config.width if args.video_config else 640,
            VIDEO_HEIGHT=args.video_config.height if args.video_config else 480,
            VIDEO_FRAMERATE=args.video_config.fps if args.video_config else 30,
            AUDIO_RATE=args.audio_config.rate if args.audio_config else 48000,
            AUDIO_CHANNELS=args.audio_config.channels if args.audio_config else 1,
        )

        # Create the pipeline
        self.pipeline = Gst.parse_launch(self.pipeline_str)

        # Setup bus for message handling
        self._setup_bus()

    def _setup_bus(self) -> None:
        """
        Setup the GStreamer bus for message handling.
        """
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self._on_message)

    def _on_message(self, bus: Gst.Bus, message: Gst.Message) -> bool:
        """
        Callback for handling GStreamer bus messages.

        Args:
            bus: The GStreamer bus.
            message: The message received.

        Returns:
            True to continue receiving messages.
        """
        msg_type = message.type

        if msg_type == Gst.MessageType.EOS:
            print("End of Stream")
            self.stop()
        elif msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err}, {debug}")
            self.stop()
        elif msg_type == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            print(f"Warning: {warn}, {debug}")
        elif msg_type == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old_state, new_state, pending_state = message.parse_state_changed()
                print(
                    f"Pipeline state changed: {old_state.value_nick} -> {new_state.value_nick}"
                )

        return True

    def start(self) -> None:
        """
        Start the GStreamer pipeline and run the main loop.
        This method blocks until stop() is called or an error occurs.
        """
        if self.is_running:
            print("Pipeline is already running.")
            return

        print(
            f"TX Streaming to {self.args.dest_ip} (Video:{self.args.video_port}, Audio:{self.args.audio_port})..."
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

    def stop(self) -> None:
        """
        Stop the GStreamer pipeline and quit the main loop.
        """
        if not self.is_running:
            return

        print("Stopping pipeline...")
        self.pipeline.set_state(Gst.State.NULL)
        self.is_running = False

        if self.loop and self.loop.is_running():
            self.loop.quit()

    def __call__(self) -> None:
        """
        Start the GStreamer pipeline (alias for start()).
        """
        self.start()

    def __del__(self) -> None:
        """
        Stop the GStreamer pipeline upon deletion of the object.
        """
        self.stop()


if __name__ == "__main__":
    # Example usage
    from gst_audio_bridge.schemas.streamer import VideoConfig, AudioConfig

    args = StreamerInitArgs(
        dest_ip="127.0.0.1",
        video_port=5000,
        audio_port=5001,
        video_config=VideoConfig(width=640, height=480, fps=30),
        audio_config=AudioConfig(rate=48000, channels=1),
    )

    streamer = Streamer(args)
    streamer.start()
