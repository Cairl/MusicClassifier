"""Client for the isolated music2emo inference server.

The host app (PySide6/PaddlePaddle env) talks to music2emo through this client
over a stdin/stdout pipe so torch/MERT stay in their own venv. The server is
lazy-started on first predict and kept alive for reuse.
"""

import json
import os
import subprocess
import tempfile
import time

import numpy as np


class Music2EmoClient:
    """Manages a long-lived music2emo server subprocess."""

    def __init__(self, venv_python: str, server_script: str,
                 startup_timeout: float = 300.0, call_timeout: float = 90.0):
        self._python = venv_python
        self._script = server_script
        self._startup_timeout = startup_timeout
        self._call_timeout = call_timeout
        self._proc: subprocess.Popen | None = None

    @property
    def available(self) -> bool:
        return bool(self._python and self._script
                    and os.path.isfile(self._python)
                    and os.path.isfile(self._script))

    def _ensure_running(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self._proc = subprocess.Popen(
            [self._python, self._script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            cwd=os.path.dirname(self._script),
        )
        deadline = time.time() + self._startup_timeout
        while time.time() < deadline:
            line = self._proc.stdout.readline()
            if not line:
                err = ""
                if self._proc.stderr:
                    err = self._proc.stderr.read()
                raise RuntimeError(
                    f"music2emo server exited during startup: {err[-2000:]}"
                )
            line = line.strip()
            if line == "READY":
                return
            try:
                payload = json.loads(line)
                if "error" in payload:
                    raise RuntimeError(payload["error"])
            except json.JSONDecodeError:
                pass
        raise TimeoutError("music2emo server startup timed out (model load?)")

    def predict_audio(self, audio: np.ndarray, sr: int) -> dict:
        """Write audio to a temp wav and predict. audio: float in [-1,1]."""
        import soundfile as sf

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        data = audio.T if audio.ndim == 2 else audio
        sf.write(tmp.name, data, sr, subtype="FLOAT")
        try:
            return self.predict_file(tmp.name)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def predict_file(self, wav_path: str) -> dict:
        self._ensure_running()
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(wav_path + "\n")
        self._proc.stdin.flush()
        line = self._proc.stdout.readline()
        if not line:
            err = ""
            if self._proc.stderr:
                err = self._proc.stderr.read()
            self._kill()
            raise RuntimeError(f"music2emo server returned nothing: {err[-2000:]}")
        return json.loads(line)

    def stop(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.stdin and self._proc.poll() is None:
                self._proc.stdin.write("EXIT\n")
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
