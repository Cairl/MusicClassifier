"""music2emo inference server.

Runs inside the dedicated music2emo venv as a long-lived child process so the
model is loaded once and reused across calls. The main app talks to it over
stdin/stdout to keep music2emo's heavy deps (torch/MERT) fully isolated from
the PySide6/PaddlePaddle host environment.

Line protocol (UTF-8):
  - server prints "READY" once the model finished loading
  - main app writes one wav path per line
  - server replies with one JSON line: {"valence","arousal","moods"} or {"error"}
  - "EXIT" line shuts the server down cleanly
"""

import json
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(_HERE, "music2emo_repo")

os.chdir(REPO_DIR)
sys.path.insert(0, REPO_DIR)

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

# music2emo.py and model/linear_mt_attn_ck.py import gradio and
# pytorch_lightning at module top but never use them in predict(). Stub them
# so we don't pull in those heavy training-only deps.
sys.modules.setdefault("gradio", types.ModuleType("gradio"))
sys.modules.setdefault("pytorch_lightning", types.ModuleType("pytorch_lightning"))


def main() -> int:
    try:
        from music2emo import Music2emo

        model = Music2emo()
    except Exception as exc:
        sys.stdout.write(json.dumps({"error": f"model_load_failed: {exc}"}) + "\n")
        sys.stdout.flush()
        return 1

    sys.stdout.write("READY\n")
    sys.stdout.flush()

    for raw in sys.stdin:
        wav_path = raw.strip()
        if not wav_path:
            continue
        if wav_path == "EXIT":
            break
        try:
            out = model.predict(wav_path)
            sys.stdout.write(json.dumps({
                "valence": float(out["valence"]),
                "arousal": float(out["arousal"]),
                "moods": list(out.get("predicted_moods", [])),
            }) + "\n")
        except Exception as exc:
            sys.stdout.write(json.dumps({"error": str(exc)}) + "\n")
        sys.stdout.flush()

    return 0


if __name__ == "__main__":
    sys.exit(main())
