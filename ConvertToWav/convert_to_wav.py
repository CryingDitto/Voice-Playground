"""M4A -> PCM WAV converter, usable from Python or the command line."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def find_ffmpeg(explicit: str | None = None) -> str:
    if explicit:
        candidate = shutil.which(explicit)
        if candidate:
            return candidate
        raise RuntimeError("지정한 FFmpeg 실행 파일을 찾을 수 없습니다.")
    local = Path(__file__).parent / "ffmpeg.exe"
    if local.is_file():
        return str(local)
    installed = shutil.which("ffmpeg")
    if installed:
        return installed
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise RuntimeError(
            "FFmpeg를 찾을 수 없습니다. 실행.bat를 실행하거나 "
            "python -m pip install -r requirements.txt로 설치하세요."
        ) from exc


def convert_file(
    source: str | Path,
    output_dir: str | Path,
    *,
    sample_rate: int | None = None,
    channels: int | None = None,
    ffmpeg: str | None = None,
) -> Path:
    """Decode one file. Preserve existing outputs, including concurrent writes."""
    source = Path(source).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"입력 파일을 찾을 수 없습니다: {source}")
    if source.suffix.lower() != ".m4a":
        raise ValueError("입력 파일은 .m4a 형식이어야 합니다.")
    if sample_rate is not None and sample_rate not in (8000, 16000, 22050, 24000, 44100, 48000):
        raise ValueError("지원하지 않는 샘플레이트입니다.")
    if channels not in (None, 1, 2):
        raise ValueError("채널은 원본 유지, 모노(1), 스테레오(2) 중 선택하세요.")
    executable = find_ffmpeg(ffmpeg)
    output_dir.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".converting-", suffix=".wav", dir=output_dir)
    os.close(descriptor)
    temp_path = Path(temporary)
    try:
        command = [executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                   "-i", str(source), "-map", "0:a:0", "-vn", "-c:a", "pcm_s16le"]
        if sample_rate is not None:
            command.extend(["-ar", str(sample_rate)])
        if channels is not None:
            command.extend(["-ac", str(channels)])
        command.extend(["-f", "wav", str(temp_path)])
        result = subprocess.run(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "오디오 변환에 실패했습니다.")
        # Windows rename refuses existing targets and works on non-NTFS drives too.
        number = 0
        while True:
            suffix = f" ({number})" if number else ""
            destination = output_dir / f"{source.stem}{suffix}.wav"
            try:
                if os.name == "nt":
                    os.rename(temp_path, destination)
                else:
                    os.link(temp_path, destination)
                return destination
            except FileExistsError:
                number += 1
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="M4A 파일을 16비트 PCM WAV로 변환합니다.")
    parser.add_argument("inputs", type=Path, nargs="+", help="변환할 M4A 파일")
    parser.add_argument("-o", "--output-dir", type=Path,
                        default=Path(__file__).parent / "output")
    parser.add_argument("--sample-rate", type=int, choices=[8000, 16000, 22050, 24000, 44100, 48000])
    parser.add_argument("--channels", type=int, choices=[1, 2])
    parser.add_argument("--ffmpeg", help="FFmpeg 실행 파일 경로")
    args = parser.parse_args()
    failed = False
    for source in args.inputs:
        try:
            output = convert_file(source, args.output_dir, sample_rate=args.sample_rate,
                                  channels=args.channels, ffmpeg=args.ffmpeg)
            print(f"완료: {output}")
        except (OSError, ValueError, RuntimeError) as exc:
            failed = True
            print(f"실패: {source}\n{exc}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
