# gst-audio-bridge
A lightweight GStreamer wrapper for real-time audio streaming.

# 🚀 Getting Started

## Installation

### Prerequisites

- Python 3.11+
- GStreamer 1.0 with plugins (base, good, bad, ugly)
- PyGObject

```bash
# Ubuntu/Debian
sudo apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    python3-gi \
    gir1.2-gst-plugins-base-1.0

# Install the package
pip install gst-audio-bridge

# Or install from source
pip install -e .

# Optional: For torch_audio format
pip install gst-audio-bridge[torch]
```

## Quick Start

### Sender (TX) - Streamer

```python
from gst_audio_bridge import Streamer, StreamerInitArgs, VideoConfig, AudioConfig

# Configure the streamer
args = StreamerInitArgs(
    dest_ip="127.0.0.1",      # Destination IP address
    video_port=5000,          # UDP port for video
    audio_port=5001,          # UDP port for audio
    video_config=VideoConfig(width=640, height=480, fps=30),
    audio_config=AudioConfig(rate=48000, channels=1),
)

# Create and start the streamer
streamer = Streamer(args)
streamer.start()  # Blocks until stopped
```

### Receiver (RX) - Listener

```python
from gst_audio_bridge import Listener, ListenerInitArgs, ListenerConfig

# Configure the listener
config = ListenerConfig(
    data_format="torch_audio",  # "raw", "encoded", or "torch_audio"
    chunk_duration_ms=20,       # Audio chunk duration in ms
    sample_rate=48000,
    channels=1,
)

args = ListenerInitArgs(
    audio_port=5001,           # Same port as streamer
    video_port=5000,           # Optional: for video
    config=config,
)

# Create the listener
listener = Listener(args)

# Option 1: Callback-based (recommended for real-time processing)
def on_audio(audio_tensor):
    print(f"Received audio: shape={audio_tensor.shape}")
    # Process audio here...

listener.set_audio_callback(on_audio)
listener.start(blocking=False)  # Non-blocking mode

# Option 2: Polling-based
listener.start(blocking=False)
while True:
    data = listener.get_audio_data(timeout=0.1)
    if data is not None:
        # Process audio data
        pass
```

## Data Formats

| Format | Output Type | Description |
|--------|-------------|-------------|
| `raw` | `bytes` | Raw PCM audio data (F32LE) |
| `encoded` | `bytes` | Opus encoded audio data |
| `torch_audio` | `torch.Tensor` | Shape: `(channels, samples)` |

## API Reference

### Streamer

| Method | Description |
|--------|-------------|
| `start()` | Start streaming (blocking) |
| `stop()` | Stop the pipeline |

### Listener

| Method | Description |
|--------|-------------|
| `start(blocking=True)` | Start listening. Set `blocking=False` for non-blocking mode |
| `stop()` | Stop the pipeline |
| `set_audio_callback(fn)` | Set callback for real-time audio processing |
| `get_audio_data(timeout)` | Get next audio chunk from queue |
| `get_all_audio_data()` | Get all available audio chunks |

## Development

```bash
# Clone the repository
git clone https://github.com/nogikun/gst-audio-bridge.git
cd gst-audio-bridge

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```
