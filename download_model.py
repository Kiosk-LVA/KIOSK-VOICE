"""
Script to pre-download V-TTS model weights from Hugging Face Hub.
Can be executed during Docker build or deployment setup to ensure offline capability.
"""

import sys
import argparse
from pathlib import Path
from huggingface_hub import snapshot_download

DEFAULT_HF_REPO = "letrggghieu/v-tts-pretrained"
DEFAULT_TARGET_DIR = "./models/vits-vietnamese"

def download_model(repo_id: str = DEFAULT_HF_REPO, target_dir: str = DEFAULT_TARGET_DIR):
    target_path = Path(target_dir).resolve()
    print(f"Downloading model from Hugging Face: '{repo_id}' -> '{target_path}'...")
    
    target_path.mkdir(parents=True, exist_ok=True)
    
    try:
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(target_path),
            local_dir_use_symlinks=False,
        )
        print(f"SUCCESS: Model downloaded successfully to '{target_path}'")
    except Exception as e:
        print(f"ERROR: Failed to download model: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-download V-TTS model weights")
    parser.add_argument("--repo", default=DEFAULT_HF_REPO, help="Hugging Face repo ID")
    parser.add_argument("--target", default=DEFAULT_TARGET_DIR, help="Target local directory")
    args = parser.parse_args()
    
    download_model(repo_id=args.repo, target_dir=args.target)
