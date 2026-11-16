"""The file runner must work from source archives without Git metadata."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf

import convert_wav


class PassthroughService:
    def __init__(self, *args, **kwargs):
        self.sample_rate = 22050
        self.block_size = 441
        self.input_samples = self.output_samples = 0
        self.block_seconds = []
        self._engine = type("Engine", (), {"config": type("Config", (), {})()})()

    def initialize(self):
        pass

    def process_pcm(self, pcm):
        self.input_samples += len(pcm)
        self.output_samples += len(pcm)
        return pcm.copy()

    def flush(self):
        return np.empty(0, dtype=np.float32)


class RunnerTests(unittest.TestCase):
    def test_conversion_and_report_survive_unavailable_git(self):
        for error in (FileNotFoundError("git missing"),
                      subprocess.CalledProcessError(128, "git", stderr="not a repository"),
                      subprocess.TimeoutExpired("git", 5)):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as folder:
                source = Path(folder) / "input.wav"
                output = Path(folder) / "output.wav"
                sf.write(source, np.ones(441, dtype=np.float32) * 0.1, 22050)
                args = ["convert_wav", "--input", str(source), "--reference", str(source),
                        "--output", str(output)]
                cwd = Path.cwd()
                try:
                    with patch.object(sys, "argv", args), \
                         patch.object(convert_wav.subprocess, "check_output", side_effect=error), \
                         patch.object(convert_wav, "VoiceConversionService", PassthroughService):
                        self.assertEqual(convert_wav.main(), 0)
                finally:
                    os.chdir(cwd)
                report = json.loads(output.with_suffix(".report.json").read_text(encoding="utf-8"))
                self.assertEqual(report["status"], "success")
                self.assertIsNone(report["upstream_commit"])
                self.assertTrue(report["upstream_commit_error"])
                data, _ = sf.read(output)
                self.assertEqual(len(data), 441)
                self.assertTrue(np.isfinite(data).all())
