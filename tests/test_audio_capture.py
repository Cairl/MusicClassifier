import time
from unittest.mock import patch, MagicMock
import numpy as np
import pytest

from core.audio_capture import AudioCaptureManager, AudioSample


class TestAudioSample:
    def test_creation(self):
        data = np.zeros((2, 48000), dtype=np.float32)
        sample = AudioSample(data=data, sample_rate=48000, timestamp=1.0)
        assert sample.sample_rate == 48000
        assert sample.data.shape == (2, 48000)
        assert sample.timestamp == 1.0


class TestFindAppleMusicPid:
    @patch("core.audio_capture.ProcessAudioCapture")
    def test_finds_apple_music_pid(self, mock_pac):
        mock_proc = MagicMock()
        mock_proc.name = "AppleMusic.exe"
        mock_proc.pid = 1234
        mock_pac.enumerate_audio_processes.return_value = [mock_proc]

        manager = AudioCaptureManager()
        pid = manager.find_apple_music_pid()
        assert pid == 1234

    @patch("core.audio_capture.ProcessAudioCapture")
    def test_finds_apple_music_with_space(self, mock_pac):
        mock_proc = MagicMock()
        mock_proc.name = "Apple Music.exe"
        mock_proc.pid = 5678
        mock_pac.enumerate_audio_processes.return_value = [mock_proc]

        manager = AudioCaptureManager()
        pid = manager.find_apple_music_pid()
        assert pid == 5678

    @patch("core.audio_capture.ProcessAudioCapture")
    def test_returns_none_when_not_found(self, mock_pac):
        mock_proc = MagicMock()
        mock_proc.name = "Chrome.exe"
        mock_proc.pid = 9999
        mock_pac.enumerate_audio_processes.return_value = [mock_proc]

        manager = AudioCaptureManager()
        pid = manager.find_apple_music_pid()
        assert pid is None

    @patch("core.audio_capture.ProcessAudioCapture")
    def test_returns_none_when_no_processes(self, mock_pac):
        mock_pac.enumerate_audio_processes.return_value = []

        manager = AudioCaptureManager()
        pid = manager.find_apple_music_pid()
        assert pid is None


class TestRingBuffer:
    def test_get_snapshot_returns_none_when_empty(self):
        manager = AudioCaptureManager()
        result = manager.get_snapshot(5.0)
        assert result is None

    def test_get_snapshot_returns_recent_data(self):
        manager = AudioCaptureManager()
        data = np.ones((2, 48000), dtype=np.float32)
        manager._buffer.append(AudioSample(data=data, sample_rate=48000, timestamp=time.time()))
        result = manager.get_snapshot(1.0)
        assert result is not None
        assert result.shape[0] == 2

    def test_buffer_discards_old_data(self):
        manager = AudioCaptureManager()
        manager._max_buffer_samples = 48000 * 2
        data = np.ones((2, 48000), dtype=np.float32)
        manager._buffer.append(AudioSample(data=data, sample_rate=48000, timestamp=time.time()))
        manager._buffer.append(AudioSample(data=data, sample_rate=48000, timestamp=time.time()))
        manager._buffer.append(AudioSample(data=data, sample_rate=48000, timestamp=time.time()))
        total_samples = sum(s.data.shape[1] for s in manager._buffer)
        assert total_samples <= manager._max_buffer_samples + 48000


class TestWavHeaderParsing:
    def test_parse_wav_header_locates_data_offset(self):
        manager = AudioCaptureManager()
        fmt_chunk = b'\x00' * 40
        header = (
            b'RIFF' + (68).to_bytes(4, 'little') + b'WAVE'
            + b'fmt ' + (40).to_bytes(4, 'little') + fmt_chunk
            + b'data' + (0).to_bytes(4, 'little')
        )
        offset = manager._parse_wav_header(header)
        assert offset is not None
        assert offset == 12 + 8 + 40 + 8

    def test_parse_wav_header_returns_none_for_incomplete(self):
        manager = AudioCaptureManager()
        offset = manager._parse_wav_header(b'RIFF')
        assert offset is None


class TestStartStop:
    @patch("core.audio_capture.ProcessAudioCapture")
    def test_start_returns_false_when_pid_not_found(self, mock_pac):
        mock_pac.enumerate_audio_processes.return_value = []
        manager = AudioCaptureManager()
        result = manager.start()
        assert result is False

    @patch("core.audio_capture.ProcessAudioCapture")
    def test_is_capturing_reflects_state(self, mock_pac):
        manager = AudioCaptureManager()
        assert manager.is_capturing is False
