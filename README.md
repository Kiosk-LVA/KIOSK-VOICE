# Valtec Vietnamese TTS

A Vietnamese Text-to-Speech system supporting multiple speakers with high-quality voice synthesis.

## Features

- Multi-speaker Vietnamese TTS
- **⚡ Ultra-fast inference** with GPU acceleration (RTF as low as **0.014**)
- Advanced Vietnamese text normalization and phonemization
- Natural prosody and intonation
- Auto-download pretrained models from Hugging Face
- Simple 2-line API for quick usage

## 🎧 Audio Examples

Listen to sample outputs from our TTS system:

| Speaker | Sample Text | Audio |
|---------|-------------|-------|
| 👨 **Male** | "Tiếng xe cộ nhộn nhịp và ánh nắng len qua từng con phố nhỏ." | [▶️ example_male.wav](examples/example_male.wav) |
| 👩 **Female** | "Tiếng xe cộ nhộn nhịp và ánh nắng len qua từng con phố nhỏ." | [▶️ example_female.wav](examples/example_female.wav) |

> 💡 **Tip**: Clone the repository and listen to the files in the `examples/` folder for the best audio quality.

## ⚡ Performance Benchmark

### Model Specifications

| Metric | Value |
|--------|-------|
| **Total Parameters** | **57.97M** (57,972,657) |
| Trainable Parameters | 57.97M |
| Sample Rate | 24,000 Hz |
| Architecture | VITS-based |

### Inference Speed

Benchmark conducted on:
- **CPU**: Intel Core i5-14500 (14 cores)
- **GPU**: NVIDIA GeForce RTX 4060 Ti (16GB VRAM, Compute Capability 8.9)
- **PyTorch**: 2.9.1+cu128
- **OS**: Linux

#### CPU Inference (Intel i5-14500)

| Input Length | Inference Time | Audio Length | RTF |
|-------------|----------------|--------------|-----|
| Short (15 chars) | 391.59ms ± 268.76ms | 0.73s | 0.5354 ✅ |
| Medium (52 chars) | 853.95ms ± 262.50ms | 2.23s | 0.3831 ✅ |
| Long (120 chars) | 1653.24ms ± 384.59ms | 4.91s | 0.3366 ✅ |

#### 🚀 CUDA Inference (RTX 4060 Ti)

| Input Length | Inference Time | Audio Length | RTF | Speedup vs CPU |
|-------------|----------------|--------------|-----|----------------|
| Short (15 chars) | **45.14ms** ± 24.69ms | 0.73s | **0.0617** ✅ | **8.7x** |
| Medium (52 chars) | **51.82ms** ± 29.35ms | 2.23s | **0.0232** ✅ | **16.5x** |
| Long (120 chars) | **68.88ms** ± 28.14ms | 4.91s | **0.0140** ✅ | **24.0x** |

> **RTF (Real-Time Factor)**: Ratio of processing time to audio duration. RTF < 1 means faster than real-time.
> 
> 🔥 **With CUDA, the model generates audio 70x faster than real-time for long texts!**

### GPU Speedup Summary

```
⚡ GPU Speedup over CPU:
   Short text:  8.7x faster
   Medium text: 16.5x faster  
   Long text:   24.0x faster
```

## Requirements

- Python 3.8+
- PyTorch 2.0+
- CUDA (optional, for GPU acceleration)
- **Linux recommended** for best phonemization quality (viphoneme)

> **Note:** On Windows, the system uses a fallback phonemizer. For production-quality Vietnamese pronunciation, please run on Linux or WSL.

## Installation

### From Git

```bash
pip install git+https://github.com/yourusername/valtec-tts.git
```

### From Source

```bash
git clone https://github.com/yourusername/valtec-tts.git
cd valtec-tts
pip install -e .
```

## Quick Start

### Simple Usage (2 lines)

```python
from valtec_tts import TTS

tts = TTS()  # Auto-downloads model from Hugging Face if not cached
tts.speak("Xin chào các bạn", output_path="hello.wav")
```

### Get Audio Array

```python
from valtec_tts import TTS

tts = TTS()
audio, sr = tts.synthesize("Xin chào các bạn")
```

### Choose Speaker

```python
from valtec_tts import TTS

tts = TTS()
print(tts.list_speakers())  # ['male', 'female']

tts.speak("Xin chào", speaker="female", output_path="hello.wav")
```

### Adjust Speed

```python
tts.speak("Nói nhanh hơn", speed=0.8, output_path="fast.wav")   # Faster
tts.speak("Nói chậm hơn", speed=1.3, output_path="slow.wav")    # Slower
```

### Select Device (CUDA/CPU)

```python
tts = TTS(device="cuda")  # Use GPU
tts = TTS(device="cpu")   # Use CPU
tts = TTS()               # Auto-detect (default)
```

### Use Local Model

```python
tts = TTS(model_path="./pretrained")
tts.speak("Xin chào", output_path="hello.wav")
```

## Command Line

```bash
# Single text synthesis
python infer.py --text "Xin chào các bạn" --speaker male --output hello.wav

# Interactive mode
python infer.py --interactive

# Batch processing from file
python infer.py --input_file texts.txt --output_dir ./outputs
```

## Gradio Demo

```bash
python demo_gradio.py
```

Then open your browser at `http://localhost:7860`

## Available Speakers

The pretrained model includes the following speakers:
- `male`
- `female`

## Synthesis Parameters

- `speed` (default: 1.0): Speech speed
  - < 1.0 = faster
  - > 1.0 = slower
- `noise_scale` (default: 0.667): Controls variability in generated speech
- `noise_scale_w` (default: 0.8): Controls duration variability
- `sdp_ratio` (default: 0.0): Stochastic Duration Predictor ratio
  - 0.0 = deterministic
  - 1.0 = fully stochastic

## Model Auto-Download

When you first use `TTS()` without specifying a model path, the pretrained model will be automatically downloaded from Hugging Face and cached locally:

- Windows: `%LOCALAPPDATA%\valtec_tts\models\`
- Linux/Mac: `~/.cache/valtec_tts/models/`

To use a custom Hugging Face repository:

```python
tts = TTS(hf_repo="valtecAI-team/valtec-tts-pretrained")
```

## Project Structure

```
valtec-tts/
├── valtec_tts/          # Main package
│   ├── __init__.py
│   └── tts.py           # Simple TTS API
├── src/
│   ├── models/          # Neural network models
│   ├── text/            # Text processing
│   ├── vietnamese/      # Vietnamese-specific modules
│   ├── nn/              # Neural network utilities
│   └── utils/           # General utilities
├── pretrained/          # Local pretrained models
├── infer.py             # Inference script
├── demo_gradio.py       # Gradio web demo
└── README.md
```

## License

This project is licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) (Creative Commons Attribution-NonCommercial 4.0 International).

- You may use, share, and adapt this project for non-commercial purposes only.
- Commercial use is strictly prohibited without prior written permission.
- You must give appropriate credit to the original authors.

## Acknowledgments

- Vietnamese phonemization support
- Valtec team for model training and development
