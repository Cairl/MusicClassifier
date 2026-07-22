"""Client for the isolated music2emo inference server (protocol v2).

The host app talks to the engine subprocess with binary PCM frames on stdin
and JSON lines on stdout, keeping torch/MERT isolated in their own venv.
"""

import json
import os
import struct
import subprocess
import time

import numpy as np

EXIT_FRAME_COUNT = 0xFFFFFFFF
HEADER = struct.Struct("<II")


class Music2EmoClient:
    """Manages a long-lived music2emo server subprocess."""

    def __init__(self, venv_python: str, server_script: str,
                 startup_timeout: float = 300.0):
        self._python = venv_python
        self._script = server_script
        self._startup_timeout = startup_timeout
        self._proc: subprocess.Popen | None = None
        self.server_version: str = ""

    @property
    def available(self) -> bool:
        return bool(self._python and self._script
                    and os.path.isfile(self._python)
                    and os.path.isfile(self._script))

    @staticmethod
    def _readline_text(proc: subprocess.Popen) -> str:
        line = proc.stdout.readline()
        if not line:
            return ""
        if isinstance(line, bytes):
            return line.decode("utf-8", errors="replace")
        return line

    def _ensure_running(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self._proc = subprocess.Popen(
            [self._python, self._script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(self._script),
        )
        deadline = time.time() + self._startup_timeout
        while time.time() < deadline:
            line = self._readline_text(self._proc).strip()
            if not line:
                self._kill()
                raise RuntimeError("music2emo server exited during startup")
            if line.startswith("READY"):
                self.server_version = line
                return
            try:
                payload = json.loads(line)
                if "error" in payload:
                    self._kill()
                    raise RuntimeError(payload["error"])
            except json.JSONDecodeError:
                pass
        self._kill()
        raise TimeoutError("music2emo server startup timed out (model load?)")

    def warmup(self) -> None:
        self._ensure_running()

    def predict_audio(self, audio: np.ndarray, sr: int) -> dict:
        """Send PCM frames to the server. audio: float in [-1,1], mono or 2ch."""
        self._ensure_running()
        assert self._proc is not None and self._proc.stdin is not None

        if audio.ndim == 2:
            mono = audio.mean(axis=0)
        else:
            mono = audio
        pcm = np.ascontiguousarray(mono, dtype=np.float32)

        self._proc.stdin.write(HEADER.pack(sr, pcm.shape[0]))
        self._proc.stdin.write(pcm.tobytes())
        self._proc.stdin.flush()

        line = self._readline_text(self._proc)
        if not line:
            self._kill()
            raise RuntimeError("music2emo server returned nothing")
        return json.loads(line)

    def restart(self) -> None:
        self._kill()

    def stop(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.stdin and self._proc.poll() is None:
                self._proc.stdin.write(HEADER.pack(0, EXIT_FRAME_COUNT))
                self._proc.stdin.flush()
                self._proc.wait(timeout=5)
        except Exception:
            pass
        self._kill()

    def _kill(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.kill()
        except Exception:
            pass
        self._proc = None
