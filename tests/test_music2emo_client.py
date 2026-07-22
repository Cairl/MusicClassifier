import itertools
import json
import struct
from unittest.mock import MagicMock, patch

import numpy as np

from core.music2emo_client import Music2EmoClient


def make_client():
    return Music2EmoClient("fake_python", "fake_server.py")


def make_proc(response: dict, version: str = "READY v2"):
    proc = MagicMock()
    proc.poll.return_value = None
    replies = itertools.cycle([version + "\n", json.dumps(response) + "\n"])
    proc.stdout.readline.side_effect = lambda: next(replies)

    written = bytearray()

    class Stdin:
        def write(self, data):
            written.extend(data)

        def flush(self):
            pass

    proc.stdin = Stdin()
    return proc, written


def test_predict_audio_sends_binary_frame_and_parses_response():
    response = {"valence": 6.5, "arousal": 3.0, "moods": ["happy"], "device": "cuda"}
    proc, written = make_proc(response)
    client = make_client()

    with patch("subprocess.Popen", return_value=proc):
        audio = np.ones((2, 4800), dtype=np.float32) * 0.5
        out = client.predict_audio(audio, 48000)

    assert client.server_version == "READY v2"
    header = struct.unpack("<II", bytes(written[:8]))
    assert header == (48000, 4800)
    pcm = np.frombuffer(bytes(written[8:]), dtype=np.float32)
    assert pcm.shape == (4800,)
    np.testing.assert_allclose(pcm, 0.5, rtol=1e-6)
    assert out["valence"] == 6.5
    assert out["device"] == "cuda"


def test_predict_audio_converts_stereo_to_mono():
    response = {"valence": 5.0, "arousal": 5.0}
    proc, written = make_proc(response)
    client = make_client()

    audio = np.zeros((2, 100), dtype=np.float32)
    audio[0, :] = 1.0
    audio[1, :] = -1.0

    with patch("subprocess.Popen", return_value=proc):
        client.predict_audio(audio, 48000)

    pcm = np.frombuffer(bytes(written[8:]), dtype=np.float32)
    np.testing.assert_allclose(pcm, 0.0, atol=1e-6)


def test_restart_kills_process_and_forces_relaunch():
    response = {"valence": 5.0, "arousal": 5.0}
    proc, _ = make_proc(response)
    client = make_client()

    with patch("subprocess.Popen", return_value=proc) as popen:
        client.predict_audio(np.zeros(100, dtype=np.float32), 48000)
        assert popen.call_count == 1
        client.restart()
        proc.poll.return_value = 0
        client.predict_audio(np.zeros(100, dtype=np.float32), 48000)
        assert popen.call_count == 2
