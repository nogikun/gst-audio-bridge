"""
Base class for GStreamer pipeline wrappers.
"""

import gi

gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst  # noqa: E402


class GStreamerPipelineBase:
    """
    Base class for GStreamer pipeline management with common functionality.
    """

    def __init__(self):
        """Initialize GStreamer and common attributes."""
        Gst.init(None)
        self.pipeline: Gst.Pipeline | None = None
        self.loop: GLib.MainLoop | None = None
        self.bus: Gst.Bus | None = None
        self.is_running: bool = False

    def _setup_bus(self) -> None:
        """Setup the GStreamer bus for message handling."""
        if self.pipeline is None:
            raise RuntimeError("Pipeline not initialized")
        
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
                old_state, new_state, _ = message.parse_state_changed()
                print(f"Pipeline state changed: {old_state.value_nick} -> {new_state.value_nick}")

        return True

    def stop(self) -> None:
        """Stop the GStreamer pipeline and quit the main loop."""
        if not self.is_running:
            return

        print("Stopping pipeline...")
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        self.is_running = False

        if self.loop and self.loop.is_running():
            self.loop.quit()

    def __del__(self) -> None:
        """Stop the GStreamer pipeline upon deletion of the object."""
        self.stop()
