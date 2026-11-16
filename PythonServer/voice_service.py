"""Sequential external-PCM adapter. No microphone, speaker, or background worker."""

from pathlib import Path
from types import SimpleNamespace
import os
import sys
import threading
import time

import numpy as np


ENGINE_ROOT = Path(__file__).resolve().parents[1] / "seed-vc-realtime"


def create_engine():
    os.environ.setdefault("HF_HOME", str(ENGINE_ROOT / "checkpoints" / "hf-home"))
    os.environ.setdefault("MODELSCOPE_CACHE", str(ENGINE_ROOT / "checkpoints" / "modelscope"))
    # The upstream imports audio_modules by its top-level name.
    sys.path.insert(0, str(ENGINE_ROOT))
    from realtime_vc_engine import RealtimeVCEngine

    return RealtimeVCEngine(
        SimpleNamespace(gpu=0, fp16=False, checkpoint_path=None, config_path=None),
        enumerate_devices=False,
    )


class VoiceConversionService:
    """One service owns one engine and one streaming session.

    Call from a single worker in Phase 2. This synchronous API intentionally applies
    backpressure instead of introducing an unbounded asynchronous audio queue.
    flush() finalizes the session; it preserves sample count, not zero DSP latency.
    """

    def __init__(self, reference_path, *, engine_factory=None, settings=None):
        self.reference_path = Path(reference_path).resolve()
        self._factory = engine_factory or create_engine
        self._settings = dict(settings or {})
        self._lock = threading.Lock()
        self._engine = None
        self._pending = np.empty(0, dtype=np.float32)
        self._finished = False
        self._failed = False
        self.block_seconds = []
        self.input_samples = 0
        self.output_samples = 0

    def _enter(self):
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("Concurrent service calls are not supported")

    def initialize(self):
        self._enter()
        try:
            if self._failed or self._finished:
                raise RuntimeError("Create a new service after failure or finalization")
            if self._engine is not None:
                return
            if not self.reference_path.is_file():
                raise FileNotFoundError(self.reference_path)
            allowed = {
                "block_time", "crossfade_time", "extra_time_ce", "extra_time",
                "extra_time_right", "diffusion_steps", "inference_cfg_rate",
                "max_prompt_length",
            }
            unknown = self._settings.keys() - allowed
            if unknown:
                raise ValueError(f"Unsupported settings: {sorted(unknown)}")
            for name, value in self._settings.items():
                if not np.isfinite(value):
                    raise ValueError(f"{name} must be finite")
            engine = self._factory()
            engine.set_config(**self._settings)
            c = engine.config
            if c.block_time < 0.06 or c.crossfade_time < 0.02:
                raise ValueError("block_time >= 0.06 and crossfade_time >= 0.02 required")
            if c.extra_time_ce < c.extra_time or c.extra_time < 0:
                raise ValueError("Require extra_time_ce >= extra_time >= 0")
            if c.extra_time_right < 0.02 or c.max_prompt_length <= 0:
                raise ValueError("Require extra_time_right >= 0.02 and positive prompt length")
            if c.diffusion_steps < 1 or int(c.diffusion_steps) != c.diffusion_steps:
                raise ValueError("diffusion_steps must be a positive integer")
            engine.set_config(reference_audio_path=str(self.reference_path), sr_type="sr_model")
            engine._prepare_buffers(external_audio=True)
            self._engine = engine
            self.sample_rate = int(engine.config.samplerate)
            self.block_size = int(engine.block_frame)
        except Exception:
            self._failed = True
            raise
        finally:
            self._lock.release()

    def _check_active(self):
        if self._engine is None or self._failed or self._finished:
            raise RuntimeError("Service must be initialized, active, and healthy")

    def _convert(self, block):
        started = time.perf_counter()
        try:
            result = self._engine._process_block(block, strict=True)
            result = np.asarray(result, dtype=np.float32)
            if result.shape != (self.block_size,) or not np.isfinite(result).all():
                raise RuntimeError(
                    f"Engine returned invalid PCM: shape={result.shape}, "
                    f"expected=({self.block_size},), nonfinite={np.count_nonzero(~np.isfinite(result))}"
                )
            # Upstream output may share the engine's next SOLA buffer: take ownership.
            return result.copy()
        except Exception:
            self._failed = True
            raise
        finally:
            self.block_seconds.append(time.perf_counter() - started)

    def process_pcm(self, pcm):
        self._enter()
        try:
            self._check_active()
            pcm = np.asarray(pcm)
            if pcm.dtype != np.float32 or pcm.ndim != 1 or not np.isfinite(pcm).all():
                raise ValueError("Expected finite one-dimensional mono float32 PCM")
            self.input_samples += len(pcm)
            data = np.concatenate((self._pending, pcm))
            full_end = len(data) // self.block_size * self.block_size
            chunks = [self._convert(data[i:i + self.block_size])
                      for i in range(0, full_end, self.block_size)]
            self._pending = data[full_end:].copy()
            output = np.concatenate(chunks) if chunks else np.empty(0, dtype=np.float32)
            self.output_samples += len(output)
            return output
        finally:
            self._lock.release()

    def flush(self):
        """Pad the last block and trim padding; no real-time output-ring priming."""
        self._enter()
        try:
            self._check_active()
            size = len(self._pending)
            result = (self._convert(np.pad(self._pending, (0, self.block_size - size)))[:size]
                      if size else np.empty(0, dtype=np.float32))
            self._pending = np.empty(0, dtype=np.float32)
            self.output_samples += len(result)
            self._finished = True
            return result
        finally:
            self._lock.release()
