"""Integration checks using a generated AAC/M4A fixture; no user recordings needed."""

from pathlib import Path
import subprocess
import tempfile
import time
import tkinter as tk
import unittest
import wave

from convert_to_wav import convert_file, find_ffmpeg
from gui import ConverterApp


class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wav-test-", dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.source = self.directory / "한글 녹음.M4A"
        self.output = self.directory / "변환 결과"
        subprocess.run(
            [find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin",
             "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=0.3",
             "-ac", "2", "-c:a", "aac", str(self.source)],
            check=True, capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def test_conversion_settings_and_preserve_existing(self):
        original = self.source.read_bytes()
        first = convert_file(self.source, self.output)
        saved = first.read_bytes()
        with wave.open(str(first), "rb") as audio:
            self.assertEqual((audio.getframerate(), audio.getnchannels(), audio.getsampwidth()),
                             (44100, 2, 2))
            self.assertGreater(audio.getnframes(), 1000)
        second = convert_file(self.source, self.output, sample_rate=16000, channels=1)
        self.assertEqual(second.name, "한글 녹음 (1).wav")
        with wave.open(str(second), "rb") as audio:
            self.assertEqual((audio.getframerate(), audio.getnchannels(), audio.getsampwidth()),
                             (16000, 1, 2))
        self.assertEqual(first.read_bytes(), saved)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertFalse(list(self.output.glob(".converting-*")))

    def test_invalid_input_leaves_no_output(self):
        broken = self.directory / "손상.m4a"
        broken.write_bytes(b"not an audio file")
        with self.assertRaises(RuntimeError):
            convert_file(broken, self.output)
        self.assertFalse(list(self.output.iterdir()))
        with self.assertRaises(ValueError):
            convert_file(self.directory / "missing.m4a", self.output)

    def test_gui_conversion(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        app = ConverterApp(root)
        app.files.append(self.source)
        app.output.set(str(self.output))
        app.rate.set("24000")
        app.channels.set("모노")
        app.start()
        deadline = time.monotonic() + 15
        while app.busy and time.monotonic() < deadline:
            root.update()
            time.sleep(0.02)
        self.assertFalse(app.busy, "GUI conversion did not finish")
        self.assertIn("성공 1개 / 실패 0개", app.status.get())
        with wave.open(str(self.output / "한글 녹음.wav"), "rb") as audio:
            self.assertEqual((audio.getframerate(), audio.getnchannels()), (24000, 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
