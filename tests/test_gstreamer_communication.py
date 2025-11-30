"""
GStreamer communication tests for Streamer (TX) and Listener (RX).

These tests verify that audio data can be streamed from a Streamer
and received by a Listener using GStreamer pipelines.
"""

import time

import gi
import numpy as np
import pytest

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402


class TestGStreamerBasics:
    """Test basic GStreamer functionality."""

    def test_gstreamer_init(self):
        """Test that GStreamer can be initialized."""
        Gst.init(None)
        assert Gst.is_initialized()

    def test_gstreamer_version(self):
        """Test that GStreamer version is available."""
        Gst.init(None)
        version = Gst.version()
        assert version is not None
        print(f"GStreamer version: {version[0]}.{version[1]}.{version[2]}")


class TestPipelineParsing:
    """Test pipeline parsing without actual streaming."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Initialize GStreamer before each test."""
        Gst.init(None)

    def test_audio_tx_pipeline_parse(self):
        """Test that TX audio pipeline can be parsed."""
        pipeline_str = """
            audiotestsrc is-live=true num-buffers=10 !
            audio/x-raw,rate=48000,channels=1 !
            opusenc !
            rtpopuspay pt=97 !
            udpsink host=127.0.0.1 port=15001
        """
        pipeline = Gst.parse_launch(pipeline_str)
        assert pipeline is not None
        pipeline.set_state(Gst.State.NULL)

    def test_audio_rx_pipeline_parse(self):
        """Test that RX audio pipeline can be parsed."""
        pipeline_str = (
            "udpsrc port=15002 "
            'caps="application/x-rtp,media=audio,encoding-name=OPUS,payload=97" ! '
            "rtpopusdepay ! "
            "opusdec ! "
            "audioconvert ! "
            "audio/x-raw,format=F32LE,rate=48000,channels=1 ! "
            "appsink name=audio_sink emit-signals=true sync=false"
        )
        pipeline = Gst.parse_launch(pipeline_str)
        assert pipeline is not None
        pipeline.set_state(Gst.State.NULL)


class TestAudioStreaming:
    """Test actual audio streaming between TX and RX."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Initialize GStreamer before each test."""
        Gst.init(None)
        self.received_samples = []
        self.sample_count = 0

    def _on_new_sample(self, sink):
        """Callback for receiving audio samples."""
        sample = sink.emit("pull-sample")
        if sample:
            buffer = sample.get_buffer()
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if success:
                self.received_samples.append(bytes(map_info.data))
                self.sample_count += 1
                buffer.unmap(map_info)
        return Gst.FlowReturn.OK

    def test_audio_loopback_streaming(self):
        """Test audio streaming from TX to RX via UDP loopback."""
        # Use unique ports for this test
        audio_port = 16001
        num_buffers = 50  # Number of buffers to send

        # Create TX pipeline (sender)
        tx_pipeline_str = (
            f"audiotestsrc is-live=true num-buffers={num_buffers} wave=sine ! "
            "audio/x-raw,rate=48000,channels=1 ! "
            "opusenc ! "
            "rtpopuspay pt=97 ! "
            f"udpsink host=127.0.0.1 port={audio_port}"
        )
        tx_pipeline = Gst.parse_launch(tx_pipeline_str)

        # Create RX pipeline (receiver)
        rx_caps = "application/x-rtp,media=audio,encoding-name=OPUS,payload=97"
        rx_pipeline_str = (
            f'udpsrc port={audio_port} caps="{rx_caps}" ! '
            "rtpopusdepay ! "
            "opusdec ! "
            "audioconvert ! "
            "audio/x-raw,format=F32LE,rate=48000,channels=1 ! "
            "appsink name=audio_sink emit-signals=true sync=false"
        )
        rx_pipeline = Gst.parse_launch(rx_pipeline_str)

        # Connect appsink callback
        audio_sink = rx_pipeline.get_by_name("audio_sink")
        audio_sink.connect("new-sample", self._on_new_sample)

        try:
            # Start RX first to be ready for incoming data
            rx_pipeline.set_state(Gst.State.PLAYING)
            time.sleep(0.2)  # Give RX time to start

            # Start TX
            tx_pipeline.set_state(Gst.State.PLAYING)

            # Wait for streaming (with timeout)
            timeout = 5.0  # seconds
            start_time = time.time()

            while time.time() - start_time < timeout:
                # Check if TX is done
                tx_bus = tx_pipeline.get_bus()
                msg = tx_bus.pop_filtered(Gst.MessageType.EOS | Gst.MessageType.ERROR)
                if msg:
                    if msg.type == Gst.MessageType.EOS:
                        break
                    elif msg.type == Gst.MessageType.ERROR:
                        err, debug = msg.parse_error()
                        pytest.fail(f"TX Error: {err}, {debug}")

                time.sleep(0.1)

            # Give RX some time to process remaining packets
            time.sleep(0.5)

            # Verify we received audio data
            print(f"Received {self.sample_count} audio samples")
            assert self.sample_count > 0, "No audio samples received"

            # Verify the data is not empty
            total_bytes = sum(len(s) for s in self.received_samples)
            print(f"Total bytes received: {total_bytes}")
            assert total_bytes > 0, "Received empty audio data"

        finally:
            # Cleanup
            tx_pipeline.set_state(Gst.State.NULL)
            rx_pipeline.set_state(Gst.State.NULL)

    def test_audio_data_format(self):
        """Test that received audio data is in expected F32LE format."""
        audio_port = 16002
        num_buffers = 20

        # Create TX pipeline
        tx_pipeline_str = (
            f"audiotestsrc is-live=true num-buffers={num_buffers} wave=sine freq=440 ! "
            "audio/x-raw,rate=48000,channels=1 ! "
            "opusenc ! "
            "rtpopuspay pt=97 ! "
            f"udpsink host=127.0.0.1 port={audio_port}"
        )
        tx_pipeline = Gst.parse_launch(tx_pipeline_str)

        # Create RX pipeline
        rx_caps = "application/x-rtp,media=audio,encoding-name=OPUS,payload=97"
        rx_pipeline_str = (
            f'udpsrc port={audio_port} caps="{rx_caps}" ! '
            "rtpopusdepay ! "
            "opusdec ! "
            "audioconvert ! "
            "audio/x-raw,format=F32LE,rate=48000,channels=1 ! "
            "appsink name=audio_sink emit-signals=true sync=false"
        )
        rx_pipeline = Gst.parse_launch(rx_pipeline_str)

        audio_sink = rx_pipeline.get_by_name("audio_sink")
        audio_sink.connect("new-sample", self._on_new_sample)

        try:
            rx_pipeline.set_state(Gst.State.PLAYING)
            time.sleep(0.2)
            tx_pipeline.set_state(Gst.State.PLAYING)

            # Wait for some samples
            timeout = 3.0
            start_time = time.time()
            while self.sample_count < 5 and time.time() - start_time < timeout:
                time.sleep(0.1)

            time.sleep(0.3)

            assert len(self.received_samples) > 0, "No samples received"

            # Convert to numpy and verify format
            for sample_bytes in self.received_samples[:5]:
                # F32LE means each sample is 4 bytes
                assert len(sample_bytes) % 4 == 0, "Sample size not multiple of 4 (F32LE)"

                # Convert to numpy array
                audio_array = np.frombuffer(sample_bytes, dtype=np.float32)

                # Verify it's valid audio data (should be in range [-1, 1] approximately)
                assert audio_array.min() >= -2.0, "Audio values too low"
                assert audio_array.max() <= 2.0, "Audio values too high"

                print(
                    f"Sample shape: {audio_array.shape}, "
                    f"range: [{audio_array.min():.3f}, {audio_array.max():.3f}]"
                )

        finally:
            tx_pipeline.set_state(Gst.State.NULL)
            rx_pipeline.set_state(Gst.State.NULL)


class TestStreamerListenerIntegration:
    """Test integration with actual Streamer and Listener classes."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Initialize GStreamer and import classes."""
        Gst.init(None)

    def test_schema_imports(self):
        """Test that schema classes can be imported."""
        from gst_audio_bridge.schemas.listener import ListenerConfig, ListenerInitArgs
        from gst_audio_bridge.schemas.streamer import StreamerInitArgs

        # Test Streamer config
        streamer_args = StreamerInitArgs(
            dest_ip="127.0.0.1",
            video_port=5000,
            audio_port=5001,
        )
        assert streamer_args.dest_ip == "127.0.0.1"

        # Test Listener config
        listener_config = ListenerConfig(
            data_format="raw",
            sample_rate=48000,
            channels=1,
        )
        listener_args = ListenerInitArgs(
            audio_port=5001,
            config=listener_config,
        )
        assert listener_args.audio_port == 5001

    def test_listener_class_import(self):
        """Test that Listener class can be imported and instantiated."""
        from gst_audio_bridge import Listener, ListenerConfig, ListenerInitArgs

        config = ListenerConfig(
            data_format="raw",
            sample_rate=48000,
            channels=1,
        )
        args = ListenerInitArgs(
            audio_port=17001,
            config=config,
        )

        listener = Listener(args)
        assert listener is not None
        assert listener.args.audio_port == 17001

    def test_streamer_listener_communication(self):
        """Test actual communication between Streamer and Listener classes."""
        from gst_audio_bridge import Listener, ListenerConfig, ListenerInitArgs

        # Configuration
        audio_port = 17002
        received_data = []

        # Create Listener
        config = ListenerConfig(
            data_format="raw",
            sample_rate=48000,
            channels=1,
        )
        args = ListenerInitArgs(
            audio_port=audio_port,
            config=config,
        )
        listener = Listener(args)

        # Set callback
        def on_audio(data):
            received_data.append(data)

        listener.set_audio_callback(on_audio)

        # Create a simple TX pipeline (using GStreamer directly for controlled test)
        tx_pipeline_str = (
            f"audiotestsrc is-live=true num-buffers=30 wave=sine ! "
            "audio/x-raw,rate=48000,channels=1 ! "
            "opusenc ! "
            "rtpopuspay pt=97 ! "
            f"udpsink host=127.0.0.1 port={audio_port}"
        )
        tx_pipeline = Gst.parse_launch(tx_pipeline_str)

        try:
            # Start listener in non-blocking mode
            listener.start(blocking=False)
            time.sleep(0.3)

            # Start TX
            tx_pipeline.set_state(Gst.State.PLAYING)

            # Wait for data
            timeout = 5.0
            start_time = time.time()
            while len(received_data) < 5 and time.time() - start_time < timeout:
                time.sleep(0.1)

            time.sleep(0.5)

            print(f"Received {len(received_data)} audio chunks via Listener class")
            assert len(received_data) > 0, "No audio data received through Listener"

        finally:
            listener.stop()
            tx_pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
