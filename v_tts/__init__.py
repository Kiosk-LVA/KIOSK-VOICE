"""
V-TTS - Text to Speech for Vietnamese

Simple usage:
    from v_tts import TTS
    
    tts = TTS()
    tts.speak("Xin chào các bạn", output_path="output.wav")
"""

__version__ = "1.0.0"
__author__ = "V-TTS"

# Python 3.12 compatibility polyfill for legacy 'vinorm' package
import os
import sys
import types
try:
    import imp
except ImportError:
    import importlib
    import importlib.util
    imp = types.ModuleType('imp')
    def _find_module(name, path=None):
        spec = importlib.util.find_spec(name, path)
        if spec and spec.origin:
            return (None, os.path.dirname(spec.origin), ('', '', 1))
        raise ImportError(f"No module named '{name}'")
    imp.find_module = _find_module
    imp.reload = importlib.reload
    sys.modules['imp'] = imp

from .tts import TTS
from .zeroshot import ZeroShotTTS

__all__ = ["TTS", "ZeroShotTTS", "__version__"]
