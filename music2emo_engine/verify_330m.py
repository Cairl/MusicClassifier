"""Check whether MERT-v1-330M embeddings fit the existing regression head.

Run with the engine venv:
    music2emo_engine\\.venv\\Scripts\\python.exe music2emo_engine\\verify_330m.py

Exit 0 if compatible, 1 if not (expected: 330M hidden=1024 -> 2048 != 1536).
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(_HERE, "music2emo_repo")
os.chdir(REPO_DIR)
sys.path.insert(0, REPO_DIR)

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ["M2E_MERT_MODEL"] = "m-a-p/MERT-v1-330M"

import numpy as np
import torch
from utils.mert import FeatureExtractorMERT

EXPECTED_DIM = 1536


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    extractor = FeatureExtractorMERT(
        model_name=os.environ["M2E_MERT_MODEL"], device=device, sr=24000)
    seg = np.random.randn(24000 * 5).astype(np.float32) * 0.05
    inputs = extractor.processor(seg, sampling_rate=24000, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = extractor.model(**inputs, output_hidden_states=True)
    layers = torch.stack(outputs.hidden_states).squeeze()[1:, :, :].unsqueeze(0)
    feats = layers.mean(dim=2).cpu().numpy()
    concat = np.concatenate([feats[:, 5, :], feats[:, 6, :]], axis=1).squeeze()
    print(f"330M embedding dim (layers 5,6 concat): {concat.shape[0]}")
    print(f"regression head expects: {EXPECTED_DIM}")
    if concat.shape[0] == EXPECTED_DIM:
        print("COMPATIBLE: backbone swap possible without retraining.")
        return 0
    print("INCOMPATIBLE: head retrain on 330M embeddings required (DEAM).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
