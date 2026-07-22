"""End-to-end sanity check for the music2emo engine.

Starts the server subprocess, feeds it a synthetic wav, and prints the
predicted valence/arousal/moods. Run after install.bat completes:

    music2emo_engine\\.venv\\Scripts\\python.exe music2emo_engine\\verify.py

First run triggers the MERT model download (hundreds of MB) — be patient.
"""

import os
import sys
import time

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
VENV_PY = os.path.join(HERE, ".venv", "Scripts", "python.exe")
SERVER = os.path.join(HERE, "server.py")

sys.path.insert(0, PROJECT)
from core.music2emo_client import Music2EmoClient  # noqa: E402


def main() -> int:
    if not os.path.isfile(VENV_PY):
        print(f"[ERROR] venv python not found: {VENV_PY}")
        print("Run music2emo_engine\\install.bat first.")
        return 1

    sr = 48000
    duration = 12
    t = np.arange(sr * duration) / sr
    tone = np.sin(2 * np.pi * 440 * t) * 0.2
    noise = np.random.randn(sr * duration) * 0.05
    audio = (tone + noise).astype(np.float32).reshape(1, -1)

    client = Music2EmoClient(VENV_PY, SERVER)
    print("Starting server (first run downloads MERT, may take several minutes)...")
    t0 = time.time()
    try:
        out = client.predict_audio(audio, sr)
    finally:
        client.stop()
    elapsed = time.time() - t0

    print(f"\npredict took {elapsed:.1f}s")
    if "error" in out:
        print(f"[FAIL] server returned error: {out['error']}")
        return 1
    print(f"valence  = {out['valence']:.2f} (1-9 scale)")
    print(f"arousal  = {out['arousal']:.2f} (1-9 scale)")
    print(f"device   = {out.get('device', 'unknown')}")
    print(f"moods    = {out.get('moods', [])}")
    a_norm = (out["arousal"] - 5.0) / 4.0
    v_norm = (out["valence"] - 5.0) / 4.0
    print(f"normalized -> arousal={a_norm:.2f}, valence={v_norm:.2f}")
    print("[OK] music2emo engine works end-to-end.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
