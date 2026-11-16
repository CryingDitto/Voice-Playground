"""Contract tests use deterministic stateful audio processing, without model downloads."""

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import numpy as np

from voice_service import VoiceConversionService


class FakeEngine:
    def __init__(self):
        self.config = SimpleNamespace(
            block_time=0.26, crossfade_time=0.04, extra_time_ce=2.5,
            extra_time=0.5, extra_time_right=0.02, max_prompt_length=3,
            diffusion_steps=10, samplerate=24000)
        self.block_frame = 8
        self.calls = []
        self.previous = np.float32(0)
        self.prepared = 0
        self.fail = False
        self.invalid_output = False

    def set_config(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self.config, k, v)

    def _prepare_buffers(self, *, external_audio):
        assert external_audio
        self.prepared += 1

    def _process_block(self, block, *, strict):
        assert strict
        if self.fail:
            raise RuntimeError("inference failed")
        self.calls.append(block.copy())
        # Stateful causal filter exposes ordering/reset/aliasing mistakes.
        out = block + np.concatenate(([self.previous], block[:-1]))
        self.previous = block[-1]
        return out[:-1] if self.invalid_output else out


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.reference = Path(self.temp.name) / "reference.wav"
        self.reference.touch()
        self.engine = FakeEngine()
        self.service = VoiceConversionService(self.reference, engine_factory=lambda: self.engine)
        self.service.initialize()

    def test_chunk_boundaries_preserve_state_and_samples(self):
        pcm = np.arange(43, dtype=np.float32)
        out = []
        for start in range(0, len(pcm), 3):
            out.append(self.service.process_pcm(pcm[start:start + 3]))
        out.append(self.service.flush())
        expected = pcm + np.concatenate(([0], pcm[:-1]))
        np.testing.assert_array_equal(np.concatenate(out), expected)
        self.assertEqual(self.service.input_samples, 43)
        self.assertEqual(self.service.output_samples, 43)
        self.assertEqual(len(self.engine.calls), 6)
        self.assertTrue(np.all(self.engine.calls[-1][3:] == 0))

    def test_full_blocks_empty_input_and_initialize_once(self):
        self.service.initialize()
        self.assertEqual(self.engine.prepared, 1)
        self.assertEqual(len(self.service.process_pcm(np.empty(0, dtype=np.float32))), 0)
        self.assertEqual(len(self.service.process_pcm(np.ones(16, dtype=np.float32))), 16)
        self.assertEqual(len(self.service.flush()), 0)
        self.assertEqual(len(self.engine.calls), 2)
        with self.assertRaises(RuntimeError):
            self.service.process_pcm(np.ones(1, dtype=np.float32))

    def test_invalid_input_does_not_mutate_session(self):
        for pcm in (np.ones(3, dtype=np.float64), np.ones((2, 1), dtype=np.float32),
                    np.array([np.nan], dtype=np.float32), np.array([np.inf], dtype=np.float32)):
            with self.assertRaises(ValueError):
                self.service.process_pcm(pcm)
        self.assertEqual(self.service.input_samples, 0)
        self.assertEqual(len(self.service.flush()), 0)

    def test_inference_failure_poisoned_session(self):
        self.engine.fail = True
        with self.assertRaisesRegex(RuntimeError, "inference failed"):
            self.service.process_pcm(np.ones(8, dtype=np.float32))
        with self.assertRaises(RuntimeError):
            self.service.flush()

    def test_invalid_output_is_failure(self):
        self.engine.invalid_output = True
        with self.assertRaisesRegex(RuntimeError, "invalid PCM"):
            self.service.process_pcm(np.ones(8, dtype=np.float32))

    def test_overlapping_calls_rejected(self):
        self.service._lock.acquire()
        try:
            with self.assertRaisesRegex(RuntimeError, "Concurrent"):
                self.service.process_pcm(np.ones(8, dtype=np.float32))
        finally:
            self.service._lock.release()

    def test_missing_reference_and_invalid_settings(self):
        missing = VoiceConversionService(self.reference.with_name("missing.wav"), engine_factory=FakeEngine)
        with self.assertRaises(FileNotFoundError):
            missing.initialize()
        for settings in ({"extra_time_right": 0}, {"crossfade_time": 0},
                         {"extra_time_ce": -1}, {"diffusion_steps": 0},
                         {"function": "im"}, {"block_time": float("nan")}):
            with self.subTest(settings=settings):
                service = VoiceConversionService(self.reference, engine_factory=FakeEngine, settings=settings)
                with self.assertRaises(ValueError):
                    service.initialize()


if __name__ == "__main__":
    unittest.main()
