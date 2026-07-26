"""music2emo inference server v2.

Long-lived child process inside the dedicated engine venv. All models are
preloaded once at startup; inference runs fully in memory on GPU.

Protocol v2 (binary on stdin, JSON lines on stdout):
  - server prints "READY v2" after all models are loaded and warmed up
  - request: 8-byte header struct "<II" (sample_rate, frame_count,
    little-endian) followed by frame_count*4 bytes of float32 mono PCM
  - frame_count == 0xFFFFFFFF shuts the server down cleanly
  - response: one JSON line {"valence","arousal","moods","device"} or {"error"}
  - M2E_MERT_MODEL env var overrides the MERT backbone name
"""

import json
import os
import shutil
import struct
import sys
import tempfile
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(_HERE, "music2emo_repo")

os.chdir(REPO_DIR)
sys.path.insert(0, REPO_DIR)

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

sys.modules.setdefault("gradio", types.ModuleType("gradio"))
sys.modules.setdefault("pytorch_lightning", types.ModuleType("pytorch_lightning"))

EXIT_FRAME_COUNT = 0xFFFFFFFF
RESAMPLE_RATE = 24000
SEGMENT_SECONDS = 30
MERT_LAYERS = [5, 6]
EMBEDDING_DIM = 1536
HEADER = struct.Struct("<II")


class Engine:
    def __init__(self):
        import numpy as np
        import torch
        from model.linear_mt_attn_ck import FeedforwardModelMTAttnCK
        from utils.btc_model import BTC_model
        from utils.hparams import HParams
        from utils.mert import FeatureExtractorMERT
        from utils.mir_eval_modules import idx2voca_chord

        self._np = np
        self._torch = torch
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        mert_name = os.environ.get("M2E_MERT_MODEL", "m-a-p/MERT-v1-95M")
        self.mert = FeatureExtractorMERT(model_name=mert_name, device=self.device, sr=RESAMPLE_RATE)

        self.head = FeedforwardModelMTAttnCK(
            input_size=EMBEDDING_DIM,
            output_size_classification=56,
            output_size_regression=2,
        )
        ckpt = torch.load("saved_models/J_all.ckpt", map_location=self.device, weights_only=False)
        state_dict = {k.replace("model.", ""): v for k, v in ckpt["state_dict"].items()}
        model_keys = set(self.head.state_dict().keys())
        self.head.load_state_dict({k: v for k, v in state_dict.items() if k in model_keys})
        self.head.to(self.device).eval()

        self.btc_config = HParams.load("./inference/data/run_config.yaml")
        self.btc_config.feature["large_voca"] = True
        self.btc_config.model["num_chords"] = 170
        self.btc = BTC_model(config=self.btc_config.model).to(self.device)
        btc_ckpt = torch.load("./inference/data/btc_model_large_voca.pt", map_location=self.device)
        self.btc_mean = btc_ckpt["mean"]
        self.btc_std = btc_ckpt["std"]
        self.btc.load_state_dict(btc_ckpt["model"])
        self.btc.eval()
        self.idx_to_chord = idx2voca_chord()

        with open("inference/data/chord.json") as f:
            self.chord_to_idx = json.load(f)
        with open("inference/data/chord_root.json") as f:
            self.chord_root_dic = json.load(f)
        with open("inference/data/chord_attr.json") as f:
            self.chord_attr_dic = json.load(f)

        self.tag_list = [t.replace("mood/theme---", "")
                         for t in list(np.load("./inference/data/tag_list.npy"))[127:]]

    def predict_pcm(self, pcm, sr: int) -> dict:
        np = self._np
        torch = self._torch

        waveform = torch.from_numpy(np.ascontiguousarray(pcm, dtype=np.float32))
        if sr != RESAMPLE_RATE:
            import torchaudio.transforms as T
            waveform = T.Resample(sr, RESAMPLE_RATE)(waveform)

        mert_vec = self._mert_embedding(waveform)
        chords, root, attr, mode = self._chord_key_features(waveform)

        inputs = {
            "x_mert": torch.from_numpy(mert_vec).unsqueeze(0),
            "x_chord": chords.unsqueeze(0),
            "x_chord_root": root.unsqueeze(0),
            "x_chord_attr": attr.unsqueeze(0),
            "x_key": mode.unsqueeze(0),
        }
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            classification_output, regression_output = self.head(inputs)
        probs = torch.sigmoid(classification_output).squeeze().tolist()
        moods = [self.tag_list[i] for i, p in enumerate(probs) if p > 0.5]
        valence, arousal = regression_output.squeeze().tolist()
        return {
            "valence": float(valence),
            "arousal": float(arousal),
            "moods": moods,
            "device": "cuda" if self.device.type == "cuda" else "cpu",
        }

    def _mert_embedding(self, waveform):
        np = self._np
        torch = self._torch
        seg_samples = SEGMENT_SECONDS * RESAMPLE_RATE
        if waveform.numel() <= seg_samples:
            segments = [waveform]
        else:
            segments = [waveform[i:i + seg_samples]
                        for i in range(0, waveform.numel(), seg_samples)]
        embs = []
        for seg in segments:
            inputs = self.mert.processor(seg.float(), sampling_rate=RESAMPLE_RATE,
                                         return_tensors="pt")
            inputs = inputs.to(self.device)
            with torch.no_grad():
                outputs = self.mert.model(**inputs, output_hidden_states=True)
            layers = torch.stack(outputs.hidden_states).squeeze()[1:, :, :].unsqueeze(0)
            feats = layers.mean(dim=2).cpu().numpy()
            embs.append(np.concatenate([feats[:, i, :] for i in MERT_LAYERS], axis=1).squeeze())
        return np.mean(np.array(embs), axis=0).astype(np.float32)

    def _chord_key_features(self, waveform):
        np = self._np
        torch = self._torch
        import librosa
        import mir_eval
        import pretty_midi as pm
        from music21 import converter

        cfg = self.btc_config
        sr = cfg.mp3["song_hz"]
        samples = waveform.numpy()
        if sr != RESAMPLE_RATE:
            samples = librosa.resample(samples, orig_sr=RESAMPLE_RATE, target_sr=sr)

        inst = int(sr * cfg.mp3["inst_len"])
        feature = None
        pos = 0
        while pos + inst <= len(samples):
            tmp = librosa.cqt(samples[pos:pos + inst], sr=sr,
                              n_bins=cfg.feature["n_bins"],
                              bins_per_octave=cfg.feature["bins_per_octave"],
                              hop_length=cfg.feature["hop_length"])
            feature = tmp if feature is None else np.concatenate((feature, tmp), axis=1)
            pos += inst
        if pos < len(samples):
            tmp = librosa.cqt(samples[pos:], sr=sr,
                              n_bins=cfg.feature["n_bins"],
                              bins_per_octave=cfg.feature["bins_per_octave"],
                              hop_length=cfg.feature["hop_length"])
            feature = tmp if feature is None else np.concatenate((feature, tmp), axis=1)
        feature = np.log(np.abs(feature) + 1e-6)

        feature = ((feature.T - self.btc_mean) / self.btc_std).astype(np.float32)
        time_unit = cfg.mp3["inst_len"] / cfg.model["timestep"]
        n_timestep = cfg.model["timestep"]
        num_pad = n_timestep - (feature.shape[0] % n_timestep)
        feature = np.pad(feature, ((0, num_pad), (0, 0)), mode="constant")
        num_instance = feature.shape[0] // n_timestep

        lines = []
        start_time = 0.0
        with torch.no_grad():
            feat_t = torch.tensor(feature).unsqueeze(0).to(self.device)
            for t in range(num_instance):
                attn_out, _ = self.btc.self_attn_layers(
                    feat_t[:, n_timestep * t:n_timestep * (t + 1), :])
                prediction, _ = self.btc.output_layer(attn_out)
                prediction = prediction.squeeze()
                for i in range(n_timestep):
                    if t == 0 and i == 0:
                        prev_chord = prediction[i].item()
                        continue
                    if prediction[i].item() != prev_chord:
                        lines.append((start_time, time_unit * (n_timestep * t + i),
                                      self.idx_to_chord[prev_chord]))
                        start_time = time_unit * (n_timestep * t + i)
                        prev_chord = prediction[i].item()
                    if t == num_instance - 1 and i + num_pad == n_timestep:
                        if start_time != time_unit * (n_timestep * t + i):
                            lines.append((start_time, time_unit * (n_timestep * t + i),
                                          self.idx_to_chord[prev_chord]))
                        break
        if not lines:
            lines = [(0.0, time_unit, "N")]

        workdir = tempfile.mkdtemp(prefix="m2e_")
        lab_path = os.path.join(workdir, "clip.lab")
        with open(lab_path, "w") as f:
            for s, e, c in lines:
                f.write("%.3f %.3f %s\n" % (s, e, c))

        starts, ends, pitchs = [], [], []
        intervals, chords_lab = mir_eval.io.load_labeled_intervals(lab_path)
        for p in range(12):
            for i, (interval, chord) in enumerate(zip(intervals, chords_lab)):
                root_num, relative_bitmap, _ = mir_eval.chord.encode(chord)
                tmp_label = mir_eval.chord.rotate_bitmap_to_root(relative_bitmap, root_num)[p]
                if i == 0:
                    start_time = interval[0]
                    label = tmp_label
                    continue
                if tmp_label != label:
                    if label == 1.0:
                        starts.append(start_time), ends.append(interval[0]), pitchs.append(p + 48)
                    start_time = interval[0]
                    label = tmp_label
                if i == len(intervals) - 1 and label == 1.0:
                    starts.append(start_time), ends.append(interval[1]), pitchs.append(p + 48)

        midi = pm.PrettyMIDI()
        instrument = pm.Instrument(program=0)
        for start, end, pitch in zip(starts, ends, pitchs):
            instrument.notes.append(pm.Note(velocity=120, pitch=pitch, start=start, end=end))
        midi.instruments.append(instrument)
        midi_path = lab_path.replace(".lab", ".midi")
        midi.write(midi_path)

        try:
            key_signature = str(converter.parse(midi_path).analyze("key"))
        except Exception:
            key_signature = "None"
        key_parts = key_signature.split()
        key_signature = key_parts[0].replace("-", "b") if key_parts[0] != "None" else "None"
        key_type = key_parts[1] if len(key_parts) > 1 else "major"

        mode_signatures = ["major", "minor"]
        mode_to_idx = {m: i for i, m in enumerate(mode_signatures)}
        if key_signature == "None":
            mode = "major"
        else:
            mode = key_signature.split()[-1]
        mode_idx = mode_to_idx.get(mode, 0)

        shift = 0
        if key_signature != "None" and len(key_signature) >= 1:
            pitch_num_dic = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
                             "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
            minor_major_dic2 = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
            key = key_signature[0].upper() + key_signature[1:]
            key = minor_major_dic2.get(key, key)
            if key in pitch_num_dic:
                shift = pitch_num_dic[key] if key_type == "major" else (pitch_num_dic[key] + 3) % 12

        pitch_class = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        encoded, encoded_root, encoded_attr = [], [], []
        for s, e, chord in lines:
            c = chord
            if c not in ("N", "X"):
                parts = c.split(":")
                root_name = parts[0]
                if root_name in pitch_num_dic:
                    new_root = pitch_class[(pitch_num_dic[root_name] - shift) % 12]
                    c = new_root + (":" + parts[1] if len(parts) > 1 else "")
            if c in ("N", "X"):
                c = "N"
            arr = c.split(":")
            root_id = self.chord_root_dic.get(arr[0], self.chord_root_dic.get("N", 0))
            attr_id = 0
            if len(arr) == 2:
                attr_id = self.chord_attr_dic.get(arr[1], 0)
            elif arr[0] not in ("N", "X"):
                attr_id = 1
            encoded_root.append(root_id)
            encoded_attr.append(attr_id)
            encoded.append(self.chord_to_idx.get(c, self.chord_to_idx.get("N", 0)))

        max_len = 100
        encoded = encoded[:max_len]
        encoded_root = encoded_root[:max_len]
        encoded_attr = encoded_attr[:max_len]
        pad = max_len - len(encoded)
        encoded = encoded + [0] * pad
        encoded_root = encoded_root + [0] * pad
        encoded_attr = encoded_attr + [0] * pad

        shutil.rmtree(workdir, ignore_errors=True)
        return (
            torch.tensor(encoded, dtype=torch.long),
            torch.tensor(encoded_root, dtype=torch.long),
            torch.tensor(encoded_attr, dtype=torch.long),
            torch.tensor([mode_idx], dtype=torch.long),
        )


def _read_exact(stream, n: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def main() -> int:
    import numpy as np

    try:
        engine = Engine()
        if engine.device.type != "cuda":
            raise RuntimeError("CUDA unavailable in engine venv; rerun music2emo_engine\\install.bat")
        warm = np.zeros(RESAMPLE_RATE * 3, dtype=np.float32)
        engine.predict_pcm(warm, RESAMPLE_RATE)
    except Exception as exc:
        sys.stdout.write(json.dumps({"error": f"model_load_failed: {exc}"}) + "\n")
        sys.stdout.flush()
        return 1

    sys.stdout.write("READY v2\n")
    sys.stdout.flush()

    stream = sys.stdin.buffer
    while True:
        header = _read_exact(stream, HEADER.size)
        if header is None:
            break
        sr, frame_count = HEADER.unpack(header)
        if frame_count == EXIT_FRAME_COUNT:
            break
        payload = _read_exact(stream, frame_count * 4)
        if payload is None:
            break
        try:
            pcm = np.frombuffer(payload, dtype=np.float32)
            out = engine.predict_pcm(pcm, sr)
            sys.stdout.write(json.dumps(out) + "\n")
        except Exception as exc:
            sys.stdout.write(json.dumps({"error": str(exc)}) + "\n")
        sys.stdout.flush()

    return 0


if __name__ == "__main__":
    sys.exit(main())
