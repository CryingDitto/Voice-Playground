"""Run from any directory; model cache is pinned to the upstream repository."""

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import time
import traceback
from importlib.metadata import version, PackageNotFoundError

import numpy as np
import soundfile as sf

from voice_service import ENGINE_ROOT, VoiceConversionService


def main():
    parser = argparse.ArgumentParser(description="Phase 1: WAV -> external PCM -> Seed-VC -> WAV")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--settings", type=Path, help="Explicit service settings JSON")
    parser.add_argument("--chunk-ms", type=float, default=20)
    parser.add_argument("--max-seconds", type=float, help="Limit source duration for smoke tests")
    parser.add_argument("--cpu-baseline", action="store_true",
                        help="Diagnostic CPU settings: one Torch thread and disable oneDNN/MKLDNN")
    args = parser.parse_args()
    if not np.isfinite(args.chunk_ms) or args.chunk_ms <= 0:
        parser.error("--chunk-ms must be positive and finite")
    if args.max_seconds is not None and (not np.isfinite(args.max_seconds) or args.max_seconds <= 0):
        parser.error("--max-seconds must be positive and finite")
    source, reference, output = [p.resolve() for p in (args.input, args.reference, args.output)]
    report_path = output.with_suffix(".report.json")
    if output in (source, reference) or report_path in (source, reference):
        parser.error("Output must not overwrite an input or reference")
    if output.exists() or report_path.exists():
        parser.error("Choose a new output path; existing results are preserved")
    settings = json.loads(args.settings.read_text(encoding="utf-8")) if args.settings else {}
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {"status": "started", "input": str(source), "reference": str(reference),
              "output": str(output), "python": platform.python_version(),
              "chunk_ms": args.chunk_ms, "requested_settings": settings,
              "max_seconds": args.max_seconds, "packages": {}}
    for name in ("torch", "torchaudio", "numpy", "librosa", "funasr", "transformers"):
        try:
            report["packages"][name] = version(name)
        except PackageNotFoundError:
            report["packages"][name] = None
    report["upstream_commit"] = None
    try:
        report["upstream_commit"] = subprocess.check_output(
            ["git", "-C", str(ENGINE_ROOT), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.PIPE, timeout=5).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        # Source archives need no Git installation or repository metadata.
        report["upstream_commit_error"] = (
            exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError)
            else str(exc)
        )
    # Upstream model loaders use relative checkpoint and config paths.
    os.chdir(ENGINE_ROOT)
    started = time.perf_counter()
    service = None
    try:
        import torch
        cpu_baseline = args.cpu_baseline and not torch.cuda.is_available()
        if cpu_baseline:
            torch.set_num_threads(1)
            torch.backends.mkldnn.enabled = False
        report.update(torch_cuda_available=torch.cuda.is_available(),
                      device=torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
                      cpu_baseline=cpu_baseline, torch_threads=torch.get_num_threads(),
                      mkldnn_enabled=torch.backends.mkldnn.enabled)
        with sf.SoundFile(source) as audio:
            source_rate = audio.samplerate
            frames = int(args.max_seconds * source_rate) if args.max_seconds else -1
            pcm = audio.read(frames=frames, dtype="float32", always_2d=True).mean(axis=1)
        if not len(pcm):
            raise ValueError("Input audio is empty")
        service = VoiceConversionService(reference, settings=settings)
        service.initialize()
        report["initialization_seconds"] = time.perf_counter() - started
        report["sample_rate"] = service.sample_rate
        report["block_size"] = service.block_size
        report["effective_settings"] = vars(service._engine.config)
        if source_rate != service.sample_rate:
            import librosa
            pcm = librosa.resample(pcm, orig_sr=source_rate, target_sr=service.sample_rate)
        chunk_size = max(1, round(service.sample_rate * args.chunk_ms / 1000))
        chunks = []
        for i in range(0, len(pcm), chunk_size):
            chunks.append(service.process_pcm(pcm[i:i + chunk_size]))
        chunks.append(service.flush())
        converted = np.concatenate(chunks)
        if len(converted) != len(pcm):
            raise RuntimeError("Input/output sample count mismatch")
        sf.write(output, converted, service.sample_rate, subtype="FLOAT")
        report.update(status="success", input_samples=service.input_samples,
                      output_samples=service.output_samples, block_seconds=service.block_seconds,
                      output_peak=float(np.max(np.abs(converted))),
                      output_rms=float(np.sqrt(np.mean(converted ** 2))),
                      processing_realtime_factor=sum(service.block_seconds) / (len(pcm) / service.sample_rate),
                      note="No device priming. DSP look-ahead/SOLA latency remains; listening comparison required.")
        print(f"Saved {output}")
        return 0
    except Exception:
        report.update(status="failed", error=traceback.format_exc())
        print(report["error"])
        return 1
    finally:
        if service is not None:
            report.update(input_samples=service.input_samples, output_samples=service.output_samples,
                          block_seconds=service.block_seconds)
        report["elapsed_seconds"] = time.perf_counter() - started
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report: {report_path}")


if __name__ == "__main__":
    raise SystemExit(main())
