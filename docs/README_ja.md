# gst-audio-bridge
リアルタイム音声ストリーミングのための軽量GStreamerラッパー

# 🚀 はじめに

## インストール

### 前提条件

- Python 3.11以上
- GStreamer 1.0 とプラグイン（base, good, bad, ugly）
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

# パッケージのインストール
pip install gst-audio-bridge

# またはソースからインストール
pip install -e .

# オプション: torch_audio形式を使用する場合
pip install gst-audio-bridge[torch]
```

## クイックスタート

### 送信側 (TX) - Streamer

```python
from gst_audio_bridge import Streamer, StreamerInitArgs, VideoConfig, AudioConfig

# Streamerの設定
args = StreamerInitArgs(
    dest_ip="127.0.0.1",      # 送信先IPアドレス
    video_port=5000,          # 映像用UDPポート
    audio_port=5001,          # 音声用UDPポート
    video_config=VideoConfig(width=640, height=480, fps=30),
    audio_config=AudioConfig(rate=48000, channels=1),
)

# Streamerを作成して開始
streamer = Streamer(args)
streamer.start()  # 停止されるまでブロック
```

### 受信側 (RX) - Listener

```python
from gst_audio_bridge import Listener, ListenerInitArgs, ListenerConfig

# Listenerの設定
config = ListenerConfig(
    data_format="torch_audio",  # "raw", "encoded", または "torch_audio"
    chunk_duration_ms=20,       # 音声チャンクの長さ（ミリ秒）
    sample_rate=48000,
    channels=1,
)

args = ListenerInitArgs(
    audio_port=5001,           # Streamerと同じポート
    video_port=5000,           # オプション: 映像用
    config=config,
)

# Listenerを作成
listener = Listener(args)

# 方法1: コールバック方式（リアルタイム処理に推奨）
def on_audio(audio_tensor):
    print(f"音声を受信: shape={audio_tensor.shape}")
    # ここで音声を処理...

listener.set_audio_callback(on_audio)
listener.start(blocking=False)  # ノンブロッキングモード

# 方法2: ポーリング方式
listener.start(blocking=False)
while True:
    data = listener.get_audio_data(timeout=0.1)
    if data is not None:
        # 音声データを処理
        pass
```

## データフォーマット

| フォーマット | 出力型 | 説明 |
|-------------|--------|------|
| `raw` | `bytes` | 生PCM音声データ（F32LE） |
| `encoded` | `bytes` | Opusエンコード済み音声データ |
| `torch_audio` | `torch.Tensor` | 形状: `(channels, samples)` |

## APIリファレンス

### Streamer

| メソッド | 説明 |
|----------|------|
| `start()` | ストリーミングを開始（ブロッキング） |
| `stop()` | パイプラインを停止 |

### Listener

| メソッド | 説明 |
|----------|------|
| `start(blocking=True)` | 受信を開始。`blocking=False`でノンブロッキングモード |
| `stop()` | パイプラインを停止 |
| `set_audio_callback(fn)` | リアルタイム音声処理用のコールバックを設定 |
| `get_audio_data(timeout)` | キューから次の音声チャンクを取得 |
| `get_all_audio_data()` | 利用可能な全ての音声チャンクを取得 |

## 開発

```bash
# リポジトリをクローン
git clone https://github.com/nogikun/gst-audio-bridge.git
cd gst-audio-bridge

# 開発用依存関係と共にインストール
pip install -e ".[dev]"

# テストを実行
pytest tests/ -v
```
