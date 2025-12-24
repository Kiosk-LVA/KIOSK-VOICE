#!/usr/bin/env python3
"""Generate example audio files for README demonstration."""

import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from valtec_tts import TTS

def main():
    # Create examples directory
    examples_dir = Path("examples")
    examples_dir.mkdir(exist_ok=True)
    
    # Initialize TTS
    print("Loading TTS model...")
    tts = TTS(device="cuda")
    
    # Example text
    text = "Xin chào, đây là hệ thống tổng hợp giọng nói tiếng Việt Valtec TTS."
    
    # Generate male voice
    print("Generating male voice...")
    tts.speak(
        text,
        speaker="male",
        output_path=str(examples_dir / "example_male.wav")
    )
    
    # Generate female voice  
    print("Generating female voice...")
    tts.speak(
        text,
        speaker="female", 
        output_path=str(examples_dir / "example_female.wav")
    )
    
    print(f"\n✅ Audio examples generated in {examples_dir}/")
    print("   - example_male.wav")
    print("   - example_female.wav")

if __name__ == "__main__":
    main()
