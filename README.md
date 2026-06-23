# AURA — Accessible Universal Response Assistant

A voice-driven AI assistant enabling fully independent computer use for blind and visually impaired users. Say **"Hey AURA"** followed by any command — open apps, navigate websites, read dashboards, manage files — entirely by voice.

---

## Complete Setup Guide (Copy-Paste Every Command)

> **OS:** Linux Mint / Ubuntu 24.04+  
> **Hardware:** NVIDIA GPU with 6GB+ VRAM recommended (tested on RTX 4050)  
> **Time:** ~2-3 hours (mostly waiting for downloads and training)

---

### Step 1 — Install System Prerequisites

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-full git espeak-ng espeak-ng-data \
  portaudio19-dev ffmpeg libespeak-ng-dev wget
```

### Step 2 — Install NVIDIA GPU Drivers (if not already installed)

```bash
# Check if already installed
nvidia-smi

# If not installed:
sudo apt install -y nvidia-driver-595-open
sudo reboot
# After reboot, verify:
nvidia-smi
```

### Step 3 — Install Ollama (for local LLM, used later in Goal 13+)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:1b
```

### Step 4 — Clone This Repo and Set Up Python Environment

```bash
# Clone the repo (replace YOUR_USERNAME with your GitHub username)
git clone https://github.com/YOUR_USERNAME/aura.git
cd aura

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# IMPORTANT: verify venv is active (should show path inside your project, not /usr)
echo $VIRTUAL_ENV
```

### Step 5 — Install Core Python Dependencies

```bash
# Core runtime (these version pins are tested and verified)
pip install openwakeword
pip install "torch==2.5.1" "torchaudio==2.5.1" "torchvision==0.20.1"
pip install faster-whisper piper-tts onnxruntime
pip install PyAudio sounddevice simpleaudio webrtcvad
pip install websockets spacy pyyaml requests tqdm numpy "scipy<1.15"
pip install onnx

# Verify torch sees the GPU
python3 -c "import torch; print('CUDA:', torch.cuda.is_available(), '| GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
```

### Step 6 — Train the "Hey AURA" Wake Word Model

This trains a custom openWakeWord model to detect the phrase "Hey AURA". Takes ~1-2 hours total.

#### 6a — Clone training repos

```bash
cd /tmp
git clone https://github.com/dscripka/openWakeWord.git openwakeword_training
cd openwakeword_training
```

#### 6b — Install training dependencies

```bash
# Make sure your project venv is still active
source ~/path/to/aura/venv/bin/activate

# Install openWakeWord training extras (one at a time to avoid version conflicts)
pip install "speechbrain>=0.5.14,<1" "audiomentations>=0.30.0,<1" "torch-audiomentations>=0.11.0,<1" "acoustics>=0.2.6,<1"
pip install "torchinfo>=1.8.0,<2" "torchmetrics>=0.11.4,<1"
pip install pronouncing mutagen espeak-phonemizer
pip install "setuptools<81"
pip install "datasets<3.0" huggingface_hub pyarrow

# Verify training imports work
python3 -c "import openwakeword; from openwakeword import train; print('Training imports OK')"
```

If you see a `pkg_resources` warning, that's fine — it's just a deprecation notice, not an error.

#### 6c — Clone the sample generator (dscripka's fork, NOT rhasspy's)

```bash
cd /tmp/openwakeword_training
git clone https://github.com/dscripka/piper-sample-generator
```

#### 6d — Download the TTS voice model

```bash
wget -O piper-sample-generator/models/en_US-libritts_r-medium.pt \
  'https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/en_US-libritts_r-medium.pt'

# Create symlink so training script finds it under its expected name
ln -sf en_US-libritts_r-medium.pt piper-sample-generator/models/en-us-libritts-high.pt
```

#### 6e — Download embedding models

```bash
wget https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/embedding_model.onnx \
  -O openwakeword/openwakeword/resources/models/embedding_model.onnx
wget https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/melspectrogram.onnx \
  -O openwakeword/openwakeword/resources/models/melspectrogram.onnx

# Create symlink so augmentation step can find models at expected path
mkdir -p openwakeword/resources
ln -sf $(pwd)/openwakeword/openwakeword/resources/models openwakeword/resources/models
```

#### 6f — Download pre-computed negative features (~16GB + 177MB)

```bash
mkdir -p training_data
cd training_data

# This file is ~16GB — use -c to resume if download is interrupted
wget -c https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/openwakeword_features_ACAV100M_2000_hrs_16bit.npy
wget https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/validation_set_features.npy

# Verify downloads
python3 -c "
import numpy as np
neg = np.load('openwakeword_features_ACAV100M_2000_hrs_16bit.npy', mmap_mode='r')
val = np.load('validation_set_features.npy', mmap_mode='r')
print('Negative features:', neg.shape)
print('Validation features:', val.shape)
"
cd ..
```

#### 6g — Prepare background audio datasets (MIT RIR + AudioSet)

```bash
cd /tmp/openwakeword_training

# MIT Room Impulse Response dataset
python3 -c "
import os, numpy as np, scipy.io.wavfile, datasets
from tqdm import tqdm
output_dir = './mit_rirs'
os.makedirs(output_dir, exist_ok=True)
rir_dataset = datasets.load_dataset('davidscripka/MIT_environmental_impulse_responses', split='train', streaming=True)
for row in tqdm(rir_dataset):
    name = row['audio']['path'].split('/')[-1]
    scipy.io.wavfile.write(os.path.join(output_dir, name), 16000, (row['audio']['array']*32767).astype(np.int16))
print('RIR done:', len(os.listdir(output_dir)), 'clips')
"

# AudioSet background noise (one shard, via pyarrow to avoid datasets version issues)
python3 -c "
import os, io, numpy as np, scipy.io.wavfile, scipy.signal
import pyarrow.parquet as pq, soundfile as sf
from tqdm import tqdm
output_dir = './audioset_16k'
os.makedirs(output_dir, exist_ok=True)
table = pq.read_table('hf://datasets/agkphysics/AudioSet/data/bal_train/09.parquet')
rows = table.to_pylist()
for row in tqdm(rows):
    audio_bytes = row['audio']['bytes']
    name = row['audio']['path'].split('/')[-1].replace('.flac', '.wav')
    try:
        data, sr = sf.read(io.BytesIO(audio_bytes))
        if data.ndim > 1: data = data.mean(axis=1)
        if sr != 16000:
            n = int(len(data) * 16000 / sr)
            data = scipy.signal.resample(data, n)
        scipy.io.wavfile.write(os.path.join(output_dir, name), 16000, (data * 32767).astype(np.int16))
    except Exception as e:
        print(f'Skipping {name}: {e}')
print('AudioSet done:', len(os.listdir(output_dir)), 'clips')
"
```

#### 6h — Patch train.py to accept custom model path

The training script hardcodes a model filename that doesn't match ours. This patch adds `model=` to all `generate_samples()` calls:

```bash
cd /tmp/openwakeword_training
sed -i 's/generate_samples(text=/generate_samples(model=config["piper_model_path"], text=/' openwakeword/train.py

# Patch the first multi-line call site separately
python3 -c "
content = open('openwakeword/train.py').read()
old = '''            generate_samples(
                text=config'''
new = '''            generate_samples(
                model=config[\"piper_model_path\"],
                text=config'''
content = content.replace(old, new)
open('openwakeword/train.py', 'w').write(content)
print('Patched')
"

# Verify all 4 call sites are patched
grep -c 'model=config\["piper_model_path"\]' openwakeword/train.py
# Should print: 4
```

#### 6i — Copy training config

```bash
# Copy the config from the cloned repo
cp ~/path/to/aura/training/configs/hey_aura.yaml /tmp/openwakeword_training/hey_aura.yaml
```

Or create it manually:

```bash
cat > /tmp/openwakeword_training/hey_aura.yaml << 'EOF'
model_name: "hey_aura"
target_phrase:
  - "hey aura"
custom_negative_phrases: []
n_samples: 30000
n_samples_val: 3000
tts_batch_size: 50
augmentation_batch_size: 16
piper_sample_generator_path: "./piper-sample-generator"
piper_model_path: "./piper-sample-generator/models/en_US-libritts_r-medium.pt"
output_dir: "./my_custom_model"
rir_paths:
  - "./mit_rirs"
background_paths:
  - "./audioset_16k"
background_paths_duplication_rate:
  - 1
false_positive_validation_data_path: "./training_data/validation_set_features.npy"
augmentation_rounds: 1
feature_data_files:
  "ACAV100M_sample": "./training_data/openwakeword_features_ACAV100M_2000_hrs_16bit.npy"
batch_n_per_class:
  "ACAV100M_sample": 1024
  "adversarial_negative": 50
  "positive": 50
model_type: "dnn"
layer_size: 32
steps: 30000
max_negative_weight: 1500
target_false_positives_per_hour: 0.2
EOF
```

#### 6j — Run the full training pipeline

```bash
cd /tmp/openwakeword_training

# Step 1: Generate synthetic "Hey AURA" voice samples (~20-30 min)
python3 openwakeword/train.py --training_config hey_aura.yaml --generate_clips

# Step 2: Augment with room acoustics and background noise (~45-60 min)
python3 openwakeword/train.py --training_config hey_aura.yaml --augment_clips

# Step 3: Train the model (~15-30 min on GPU)
python3 openwakeword/train.py --training_config hey_aura.yaml --train_model
# Note: the TFLite conversion error at the very end is expected and harmless —
# the ONNX model is saved successfully before that error.
```

#### 6k — Copy the trained model to your project

```bash
cp /tmp/openwakeword_training/my_custom_model/hey_aura.onnx ~/path/to/aura/models/

# Verify
python3 -c "
import onnxruntime as ort
sess = ort.InferenceSession('~/path/to/aura/models/hey_aura.onnx')
print('Model loaded OK')
"
```

#### 6l — Clean up training data (optional, frees ~20GB)

```bash
rm -rf /tmp/openwakeword_training
```

---

## Project Structure

```
aura/
├── main.py                 # Entry point — starts voice interaction loop
├── requirements.txt        # All Python dependencies with version pins
├── pyproject.toml          # Package metadata
├── GOALS.md                # 43-goal sequenced build plan
├── CHANGELOG.md            # Progress log
├── aura/                   # Core Python package
│   ├── audio/              # Wake word, ASR, TTS, audio state cues
│   │   ├── wake_word.py    # openWakeWord integration
│   │   ├── asr.py          # faster-whisper speech-to-text
│   │   ├── tts.py          # Piper TTS text-to-speech
│   │   └── cues.py         # Non-visual audio state indicators
│   ├── accessibility/      # OS accessibility API bridge
│   │   └── bridge.py       # UIA (Win) / AX (Mac) / AT-SPI (Linux)
│   ├── actions/            # Application control & file management
│   │   └── executor.py     # Open apps, navigate, file ops
│   ├── dialogue/           # Conversation & intent understanding
│   │   ├── intent.py       # Tiered intent classifier (Grammar → LLM)
│   │   └── manager.py      # Context memory & session state
│   ├── llm/                # Language model integration
│   │   └── engine.py       # Local GPU LLM + optional cloud tier
│   ├── safety/             # Action safety & confirmation
│   │   └── classifier.py   # Risk classification & double-confirm
│   └── config/             # User preferences & aliases
│       └── profile.py      # Persistent local profile storage
├── browser_extension/      # Chrome/Edge/Firefox companion extension
│   ├── manifest.json
│   ├── background.js       # WebSocket bridge to Python backend
│   └── content.js          # DOM/ARIA reader + MutationObserver
├── training/               # Wake word training configs & docs
│   ├── configs/hey_aura.yaml
│   └── README.md
├── models/                 # Trained model files (not in git)
├── scripts/                # Utility scripts
│   └── benchmark.py        # Phase 0 hardware validation
├── tests/                  # Test suite
│   ├── test_safety.py
│   └── test_profile.py
├── assets/sounds/          # Audio cue WAV files
└── docs/                   # Documentation
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AURA Pipeline                            │
│                                                                 │
│  ┌──────────┐  ┌──────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Wake Word│→ │ ASR  │→ │   Intent     │→ │    Action      │  │
│  │ Detector │  │Engine│  │ Classifier   │  │   Executor     │  │
│  │(always-on)  │(local)  │              │  │                │  │
│  └──────────┘  └──────┘  │ Tier 1:Rules │  │ App Control    │  │
│                          │ Tier 2:LLM   │  │ File Ops       │  │
│                          │ Tier 3:Cloud  │  │ Navigation     │  │
│                          └──────┬───────┘  └───────┬────────┘  │
│                                 │                   │           │
│  ┌──────────┐  ┌──────────────┐ │  ┌──────────────┐│           │
│  │   TTS    │← │   Dialogue   │←┘  │ Accessibility││           │
│  │  Engine  │  │   Manager    │    │    Bridge    │←┘           │
│  │ (Piper)  │  │(context/mem) │    │(OS APIs+DOM)│             │
│  └──────────┘  └──────────────┘    └──────────────┘             │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Safety & Confirmation Layer                  │   │
│  │  (classifies every action, enforces double-confirm)      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Current Status

**Goal 2 of 43** — Custom "Hey AURA" wake word model (training pipeline complete, model training in progress).

See [GOALS.md](GOALS.md) for the full 43-goal build sequence.

## Design Principles

1. **Accessibility-first** — every feature designed for non-visual use from day one
2. **Predictable over clever** — never guess destructively; ask when uncertain
3. **Graceful degradation** — AI failure falls back to literal behavior, never silence
4. **Confirm before harm** — destructive actions always require double confirmation
5. **Narrate state changes** — always tell the user what changed on screen
6. **Offline-first** — everything works without internet; cloud tier is strictly opt-in

## License

MIT — see [LICENSE](LICENSE)
