# Training the "Hey AURA" Wake Word Model

This directory contains configuration and helper scripts for training a custom
openWakeWord model for the "Hey AURA" wake phrase.

## Prerequisites

- NVIDIA GPU with CUDA support (training is GPU-accelerated)
- ~20GB free disk space for training data
- Python 3.10+ with the project's venv activated

## Quick Start

### 1. Clone the training dependencies

```bash
# From the project root:
git clone https://github.com/dscripka/openWakeWord.git openwakeword_training
cd openwakeword_training
pip install -e ".[full]"

# Clone the sample generator (dscripka's fork, not rhasspy's)
git clone https://github.com/dscripka/piper-sample-generator
```

### 2. Download the TTS voice model

```bash
wget -O piper-sample-generator/models/en_US-libritts_r-medium.pt \
  'https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/en_US-libritts_r-medium.pt'
```

### 3. Download pre-computed negative features

```bash
mkdir -p training_data
cd training_data
wget https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/openwakeword_features_ACAV100M_2000_hrs_16bit.npy
wget https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/validation_set_features.npy
```

### 4. Prepare background audio datasets

See `prepare_audioset.py` and `prepare_training_data.py` for downloading and
converting MIT RIR and AudioSet data.

### 5. Train

```bash
# Generate synthetic "hey aura" clips
python3 openwakeword/train.py --training_config ../training/configs/hey_aura.yaml --generate_clips

# Augment with room acoustics and background noise
python3 openwakeword/train.py --training_config ../training/configs/hey_aura.yaml --augment_clips

# Train the model
python3 openwakeword/train.py --training_config ../training/configs/hey_aura.yaml --train_model
```

The trained model will be saved as `my_custom_model/hey_aura.onnx`. Copy it to
`models/hey_aura.onnx` in the project root.

## Configuration

See `configs/hey_aura.yaml` for all training parameters. Key settings:

- `n_samples`: Number of positive training samples (30,000 recommended)
- `n_samples_val`: Number of validation samples (3,000 recommended)
- `steps`: Maximum training steps (30,000 recommended)
- `target_false_positives_per_hour`: Target FP rate (0.2 default)

## Notes

- Training requires `torch` with CUDA, `speechbrain`, `audiomentations`, and
  several other ML packages. These are installed as part of openWakeWord's
  `[full]` extras.
- TensorFlow is NOT required — the TFLite conversion step is optional and
  skipped in this project (we use ONNX format exclusively).
- The 16GB negative features file (`openwakeword_features_ACAV100M_2000_hrs_16bit.npy`)
  is the largest download. Use `wget -c` to resume if the download is interrupted.
