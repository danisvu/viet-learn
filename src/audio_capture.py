"""System audio capture via BlackHole 2ch virtual device using PyAudio."""
from __future__ import annotations

import logging
import threading
import wave
from dataclasses import dataclass
from pathlib import Path

# PyAudio is an optional dependency (Phase 2). Import it lazily so the rest of
# the application can still run when it is not installed.
try:
    import pyaudio
except ImportError:
    pyaudio = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# 16-bit PCM: 2 bytes per sample frame
_SAMPLE_WIDTH = 2


class DeviceNotFoundError(Exception):
    """Raised when the requested audio input device cannot be found."""


@dataclass
class CaptureConfig:
    """Configuration for AudioCapture."""

    output_dir: str = "output/captures"
    device_name: str = "BlackHole 2ch"
    sample_rate: int = 44100
    channels: int = 2
    chunk_size: int = 1024


class AudioCapture:
    """Record system audio from a virtual device (e.g. BlackHole 2ch).

    Usage::

        capture = AudioCapture(config)
        capture.start("output/captures/lecture.wav")
        # ... user watches the Udemy lecture ...
        path = capture.stop()   # returns WAV path; blocks until thread exits

    The underlying PyAudio stream runs in a daemon thread so the main thread
    is never blocked during recording.
    """

    def __init__(self, config: CaptureConfig) -> None:
        self.config = config
        self._is_recording: bool = False
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._pa = None
        self._stream = None
        self._wav_file: wave.Wave_write | None = None
        self._output_path: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, output_path: str) -> None:
        """Begin recording audio to *output_path* (non-blocking).

        Args:
            output_path: Destination WAV file path.

        Raises:
            RuntimeError: If a recording is already in progress.
            ImportError: If PyAudio is not installed.
            DeviceNotFoundError: If the configured device cannot be found.
        """
        if self._is_recording:
            raise RuntimeError(
                "Already recording. Call stop() before starting a new capture."
            )
        if pyaudio is None:
            raise ImportError(
                "pyaudio is not installed. "
                "Install it with: pip install pyaudio"
            )

        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        pa = pyaudio.PyAudio()
        device_index = self.find_device_index(pa)

        stream = pa.open(
            format=pyaudio.paInt16,
            channels=self.config.channels,
            rate=self.config.sample_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=self.config.chunk_size,
        )

        wav_file = wave.open(output_path, "wb")
        wav_file.setnchannels(self.config.channels)
        wav_file.setsampwidth(_SAMPLE_WIDTH)
        wav_file.setframerate(self.config.sample_rate)

        stop_event = threading.Event()

        self._pa = pa
        self._stream = stream
        self._wav_file = wav_file
        self._stop_event = stop_event
        self._output_path = output_path
        self._is_recording = True

        self._thread = threading.Thread(
            target=self._record_loop,
            args=(stream, wav_file, stop_event),
            daemon=True,
            name="audio-capture",
        )
        self._thread.start()
        logger.info("Recording started → %s", output_path)

    def stop(self) -> str:
        """Stop recording, flush the WAV file, and release PyAudio resources.

        Blocks until the recording thread exits.

        Returns:
            Path to the saved WAV file.

        Raises:
            RuntimeError: If no recording is currently in progress.
        """
        if not self._is_recording:
            raise RuntimeError("No recording in progress. Call start() first.")

        # Signal the thread and wait for it to exit cleanly.
        self._stop_event.set()
        self._thread.join()

        # Finalise the WAV file (writes chunk-size headers).
        self._wav_file.close()

        # Release the PyAudio stream and host API.
        self._stream.stop_stream()
        self._stream.close()
        self._pa.terminate()

        self._is_recording = False
        output_path = self._output_path

        # Reset state for potential re-use.
        self._pa = self._stream = self._wav_file = self._thread = None
        self._stop_event = None
        self._output_path = None

        logger.info("Recording saved → %s", output_path)
        return output_path

    def is_recording(self) -> bool:
        """Return True while a recording is in progress."""
        return self._is_recording

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def find_device_index(self, pa) -> int:
        """Search PyAudio device list for *config.device_name* and return its index.

        Matching is case-insensitive substring search so "BlackHole" matches
        "BlackHole 2ch".

        Raises:
            DeviceNotFoundError: If no matching input device is found.
        """
        target = self.config.device_name.lower()
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if target in info["name"].lower():
                return info["index"]
        raise DeviceNotFoundError(
            f"Audio device '{self.config.device_name}' not found. "
            "Is BlackHole 2ch installed and visible in Audio MIDI Setup?"
        )

    def _record_loop(
        self,
        stream,
        wav_file: wave.Wave_write,
        stop_event: threading.Event,
    ) -> None:
        """Read audio chunks from *stream* and write them to *wav_file*.

        Exits when *stop_event* is set. Runs in a daemon thread.
        ``exception_on_overflow=False`` prevents crashes when the app is busy.
        """
        while not stop_event.is_set():
            data = stream.read(self.config.chunk_size, exception_on_overflow=False)
            wav_file.writeframes(data)


def load_audio_capture_from_config(
    config_path: str = "config/config.yaml",
    output_dir: str | None = None,
) -> AudioCapture:
    """Create an AudioCapture from a YAML config file.

    Args:
        config_path: Path to the YAML config file.
        output_dir: Override for the output directory. If None, reads from config.

    Returns:
        Configured AudioCapture instance.
    """
    from src.config_loader import load_config

    cfg = load_config(config_path)
    capture_cfg = CaptureConfig(
        output_dir=output_dir or cfg.get("capture.output_dir", default="output/captures"),
        device_name=cfg.get("capture.device_name", default="BlackHole 2ch"),
        sample_rate=cfg.get("capture.sample_rate", default=44100),
        channels=cfg.get("capture.channels", default=2),
        chunk_size=cfg.get("capture.chunk_size", default=1024),
    )
    return AudioCapture(capture_cfg)
