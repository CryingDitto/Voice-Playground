"""Actual engine DSP path, replacing only the neural models with deterministic doubles.

Imports the real engine dependencies, but does not download checkpoints or open devices.
This is a DSP integration check, not a voice-quality test.
"""

from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "seed-vc-realtime"))
from realtime_vc_engine import RealtimeVCEngine
from voice_service import VoiceConversionService


class Vad:
    def generate(self, **kwargs):
        return [{"value": [[0, -1]]}]


class EngineDSPTests(unittest.TestCase):
    def test_vad_uses_complete_local_cache_and_falls_back_when_missing(self):
        for cached in (True, False):
            with self.subTest(cached=cached), \
                 patch.object(RealtimeVCEngine, "_load_models", return_value=(None,) * 6), \
                 patch("realtime_vc_engine.os.path.isfile", return_value=cached), \
                 patch("realtime_vc_engine.AutoModel", return_value=Vad()) as loader:
                RealtimeVCEngine(SimpleNamespace(gpu=0, fp16=False), enumerate_devices=False)
                model = loader.call_args.kwargs["model"]
                if cached:
                    self.assertTrue(model.endswith("speech_fsmn_vad_zh-cn-16k-common-pytorch"))
                else:
                    self.assertEqual(model, "fsmn-vad")

    def test_default_gui_path_keeps_device_initialization(self):
        with tempfile.TemporaryDirectory() as folder:
            reference = Path(folder) / "ref.wav"
            sf.write(reference, np.zeros(2400, dtype=np.float32), 24000)
            with patch.object(RealtimeVCEngine, "_load_models", return_value=(None,) * 5 + ({"sampling_rate": 24000},)), \
                 patch("realtime_vc_engine.AutoModel", return_value=Vad()), \
                 patch.object(RealtimeVCEngine, "update_devices") as enumerate_devices:
                engine = RealtimeVCEngine(SimpleNamespace(gpu=0, fp16=False))
                enumerate_devices.assert_called_once_with()
                engine.set_config(reference_audio_path=str(reference), sr_type="sr_device")
                with patch.object(engine, "get_device_samplerate", return_value=48000) as rate, \
                     patch.object(engine, "get_device_channels", return_value=2) as channels:
                    engine._prepare_buffers()
                    rate.assert_called_once_with()
                    channels.assert_called_once_with()
                    self.assertEqual(engine.config.samplerate, 48000)
                    self.assertEqual(engine.config.channels, 2)

    def test_external_audio_uses_real_buffers_vad_and_sola_without_devices(self):
        with tempfile.TemporaryDirectory() as folder:
            reference = Path(folder) / "ref.wav"
            sf.write(reference, np.zeros(2400, dtype=np.float32), 24000)
            model_set = (None, None, None, None, None, {"sampling_rate": 24000})
            with patch.object(RealtimeVCEngine, "_load_models", return_value=model_set), \
                 patch("realtime_vc_engine.AutoModel", return_value=Vad()), \
                 patch("realtime_vc_engine.sd.query_devices", side_effect=AssertionError("device query")), \
                 patch("realtime_vc_engine.sd.query_hostapis", side_effect=AssertionError("host query")), \
                 patch("realtime_vc_engine.sd.Stream", side_effect=AssertionError("device stream")):
                engine = RealtimeVCEngine(SimpleNamespace(gpu=0, fp16=False), enumerate_devices=False)
                service = VoiceConversionService(reference, engine_factory=lambda: engine,
                                                 settings={"block_time": 0.26, "extra_time_right": 0.02})
                service.initialize()
                self.assertEqual(engine.config.channels, 1)
                self.assertEqual(service.sample_rate, 24000)
                calls = []

                def infer(_):
                    calls.append(engine.input_wav_res.clone())
                    size = engine.block_frame + engine.sola_buffer_frame + engine.sola_search_frame
                    return torch.linspace(0.01, 0.2, size, device=engine.device)

                engine._custom_infer = infer
                a = service.process_pcm(np.ones(service.block_size, dtype=np.float32) * 0.1)
                state = engine.sola_buffer.clone()
                b = service.process_pcm(np.ones(service.block_size, dtype=np.float32) * 0.2)
                self.assertTrue(engine.vad_speech_detected)
                self.assertEqual(len(calls), 2)
                self.assertFalse(torch.equal(calls[0], calls[1]))
                self.assertTrue(torch.any(state != 0))
                self.assertTrue(np.isfinite(a).all() and np.isfinite(b).all())
                self.assertGreater(float(np.max(np.abs(b))), 0)
                self.assertEqual(len(a) + len(b), 2 * service.block_size)
                self.assertIsNone(engine.stream)
                self.assertIsNone(engine._worker)
                self.assertEqual(len(service.flush()), 0)

    def test_strict_errors_are_not_silently_replaced_with_silence(self):
        # Reuse the full setup, with an inference failure in place of the double.
        with tempfile.TemporaryDirectory() as folder:
            reference = Path(folder) / "ref.wav"
            sf.write(reference, np.zeros(2400, dtype=np.float32), 24000)
            with patch.object(RealtimeVCEngine, "_load_models", return_value=(None,) * 5 + ({"sampling_rate": 24000},)), \
                 patch("realtime_vc_engine.AutoModel", return_value=Vad()):
                engine = RealtimeVCEngine(SimpleNamespace(gpu=0, fp16=False), enumerate_devices=False)
                service = VoiceConversionService(reference, engine_factory=lambda: engine,
                                                 settings={"extra_time_right": 0.02})
                service.initialize()
                engine._custom_infer = lambda _: (_ for _ in ()).throw(RuntimeError("model failure"))
                with self.assertRaisesRegex(RuntimeError, "model failure"):
                    service.process_pcm(np.ones(service.block_size, dtype=np.float32))
                engine._prepare_buffers(external_audio=True)
                engine.vad_model.generate = lambda **kwargs: [{"value": []}]
                engine._custom_infer = lambda _: torch.full(
                    (engine.block_frame + engine.sola_buffer_frame + engine.sola_search_frame,), float("nan"))
                with self.assertRaisesRegex(FloatingPointError, "before VAD"):
                    engine._process_block(np.zeros(service.block_size, dtype=np.float32), strict=True)


if __name__ == "__main__":
    unittest.main()
