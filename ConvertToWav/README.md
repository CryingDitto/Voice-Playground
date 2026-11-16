# M4A → WAV 변환기

## 실행

Windows에서 `실행.bat`를 더블 클릭합니다. 처음 실행 시 전용 가상환경과 FFmpeg가 포함된 패키지를 설치하므로 인터넷 연결이 필요합니다. Python 3.10 이상(공식 Python의 Tkinter 포함)이 필요합니다.

1. **파일 추가…**에서 M4A 파일을 하나 이상 선택합니다.
2. **저장 폴더**를 지정합니다. 기본값은 이 폴더 아래의 `output`입니다.
3. 필요하면 샘플레이트와 모노/스테레오를 선택합니다.
4. **WAV로 변환**을 클릭합니다. 완료 여부와 파일 경로가 아래 기록에 표시됩니다.

기본 출력은 **16비트 PCM WAV**, 원본 샘플레이트·채널 수 유지입니다. 음성 처리에 필요하면 16000/24000/44100/48000 Hz 및 모노 등을 선택하세요. 샘플레이트를 올려도 원본 음질이 개선되지는 않습니다.

원본은 수정하지 않습니다. 같은 이름의 WAV가 있으면 `이름 (1).wav`, `이름 (2).wav`처럼 저장합니다. 변환이 실패한 파일은 기록에 표시하고 다음 파일을 계속 처리합니다. 진행률은 파일 개수 기준입니다. 한 파일에 오디오 트랙이 여러 개 있으면 첫 번째 오디오 트랙을 변환합니다. DRM 보호 파일은 지원하지 않습니다.

## 파이썬 / 명령줄

이 폴더에서 다음 명령을 실행할 수도 있습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe gui.py
```

GUI 없이 변환:

```powershell
.\.venv\Scripts\python.exe convert_to_wav.py "C:\Audio\녹음.m4a" -o "C:\Audio\WAV"
.\.venv\Scripts\python.exe convert_to_wav.py "a.m4a" "b.m4a" -o output --sample-rate 24000 --channels 1
```

코드에서 사용:

```python
from convert_to_wav import convert_file

saved_path = convert_file("녹음.m4a", "output", sample_rate=24000, channels=1)
print(saved_path)
```

FFmpeg는 이 폴더의 `ffmpeg.exe`, 시스템 PATH의 FFmpeg, `imageio-ffmpeg`에 포함된 실행 파일 순서로 찾습니다. 명령줄에서는 `--ffmpeg "경로\ffmpeg.exe"`로 지정할 수 있습니다. 설치 후 변환은 인터넷 없이 동작합니다.
