import ctypes
import threading
import time
from collections import deque
from ctypes import wintypes
from dataclasses import dataclass

import numpy as np
from process_audio_capture import ProcessAudioCapture


@dataclass
class AudioSample:
    data: np.ndarray
    sample_rate: int
    timestamp: float


class AudioCaptureManager:
    BUFFER_SECONDS = 25

    def __init__(self):
        self._buffer: deque[AudioSample] = deque()
        self._max_buffer_samples: int = 48000 * self.BUFFER_SECONDS
        self._capture: ProcessAudioCapture | None = None
        self._pipe_name: str = ""
        self._pipe_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._connected_event = threading.Event()
        self._pipe_handle: int | None = None
        self._capturing = False
        self._header_parsed = False
        self._data_offset: int | None = None
        self._header_buffer = bytearray()

    @property
    def is_capturing(self) -> bool:
        return self._capturing

    def find_apple_music_pid(self) -> int | None:
        try:
            processes = ProcessAudioCapture.enumerate_audio_processes()
        except OSError:
            return None
        for proc in processes:
            name_lower = proc.name.lower()
            if "applemusic" in name_lower or "apple music" in name_lower or "amplibraryagent" in name_lower:
                return proc.pid
        return None

    def start(self) -> bool:
        pid = self.find_apple_music_pid()
        if pid is None:
            return False

        self._pipe_name = fr'\\.\pipe\mc_audio_{int(time.time())}_{id(self)}'
        self._stop_event.clear()
        self._connected_event.clear()
        self._header_parsed = False
        self._data_offset = None
        self._header_buffer.clear()
        self._buffer.clear()

        PIPE_ACCESS_INBOUND = 0x00000001
        PIPE_TYPE_BYTE = 0x00000000
        PIPE_WAIT = 0x00000000
        INVALID_HANDLE_VALUE = -1

        self._pipe_handle = ctypes.windll.kernel32.CreateNamedPipeW(
            self._pipe_name,
            PIPE_ACCESS_INBOUND,
            PIPE_TYPE_BYTE | PIPE_WAIT,
            1, 65536, 65536, 0, None
        )

        if self._pipe_handle == INVALID_HANDLE_VALUE:
            return False

        self._pipe_thread = threading.Thread(target=self._pipe_reader, daemon=True)
        self._pipe_thread.start()

        try:
            self._capture = ProcessAudioCapture(
                pid=pid,
                output_path=self._pipe_name,
                level_callback=lambda db: None
            )
            self._capture.__enter__()
            self._capture.start()
        except Exception:
            self._cleanup_pipe()
            return False

        if not self._connected_event.wait(timeout=5.0):
            self.stop()
            return False

        self._capturing = True
        return True

    def stop(self) -> None:
        self._stop_event.set()
        self._capturing = False

        if self._capture is not None:
            try:
                self._capture.stop()
                self._capture.__exit__(None, None, None)
            except Exception:
                pass
            self._capture = None

        self._cleanup_pipe()

    def get_snapshot(self, seconds: float = 5.0) -> np.ndarray | None:
        if not self._buffer:
            return None

        target_samples = int(seconds * 48000)
        collected = []
        available = 0

        buffer_snapshot = list(self._buffer)
        for sample in reversed(buffer_snapshot):
            collected.append(sample.data)
            available += sample.data.shape[1]
            if available >= target_samples:
                break

        if not collected:
            return None

        collected.reverse()
        combined = np.concatenate(collected, axis=1)

        if combined.shape[1] > target_samples:
            combined = combined[:, -target_samples:]

        return combined

    def _pipe_reader(self) -> None:
        ctypes.windll.kernel32.ConnectNamedPipe(self._pipe_handle, None)
        self._connected_event.set()

        buffer = ctypes.create_string_buffer(65536)
        bytes_read = wintypes.DWORD()

        while not self._stop_event.is_set():
            success = ctypes.windll.kernel32.ReadFile(
                self._pipe_handle,
                buffer,
                len(buffer),
                ctypes.byref(bytes_read),
                None
            )

            if not success or bytes_read.value == 0:
                break

            raw = buffer.raw[:bytes_read.value]

            if not self._header_parsed:
                self._header_buffer.extend(raw)
                offset = self._parse_wav_header(bytes(self._header_buffer))
                if offset is not None:
                    self._header_parsed = True
                    pcm_data = self._header_buffer[offset:]
                    self._header_buffer.clear()
                    if pcm_data:
                        self._store_pcm(pcm_data)
                continue

            self._store_pcm(raw)

    def _store_pcm(self, raw: bytes) -> None:
        float_data = np.frombuffer(raw, dtype=np.float32)
        total_floats = float_data.shape[0]
        if total_floats < 2:
            return
        if total_floats % 2 != 0:
            float_data = float_data[:total_floats - 1]
            total_floats = float_data.shape[0]
        num_samples = total_floats // 2
        stereo = float_data[:num_samples * 2].reshape(2, num_samples)

        sample = AudioSample(
            data=stereo.copy(),
            sample_rate=48000,
            timestamp=time.time()
        )
        self._buffer.append(sample)
        self._trim_buffer()

    def _trim_buffer(self) -> None:
        total = sum(s.data.shape[1] for s in self._buffer)
        while total > self._max_buffer_samples and len(self._buffer) > 1:
            removed = self._buffer.popleft()
            total -= removed.data.shape[1]

    def _parse_wav_header(self, data: bytes) -> int | None:
        if len(data) < 12:
            return None

        if data[:4] != b'RIFF' or data[8:12] != b'WAVE':
            return None

        pos = 12
        while pos + 8 <= len(data):
            chunk_id = data[pos:pos + 4]
            chunk_size = int.from_bytes(data[pos + 4:pos + 8], 'little')

            if chunk_id == b'fmt ':
                if chunk_size < 16:
                    return None
                audio_format = int.from_bytes(data[pos+8:pos+10], 'little')
                num_channels = int.from_bytes(data[pos+10:pos+12], 'little')
                bits_per_sample = int.from_bytes(data[pos+22:pos+24], 'little')
                if audio_format != 3 or num_channels != 2 or bits_per_sample != 32:
                    # Only IEEE float stereo 32-bit is supported
                    return None

            if chunk_id == b'data':
                return pos + 8

            pos += 8 + chunk_size
            if chunk_size % 2:
                pos += 1

        return None

    def _cleanup_pipe(self) -> None:
        if self._pipe_handle is not None:
            try:
                ctypes.windll.kernel32.DisconnectNamedPipe(self._pipe_handle)
            except Exception:
                pass
            try:
                ctypes.windll.kernel32.CloseHandle(self._pipe_handle)
            except Exception:
                pass
            self._pipe_handle = None

        if self._pipe_thread is not None:
            self._pipe_thread.join(timeout=2.0)
            self._pipe_thread = None
