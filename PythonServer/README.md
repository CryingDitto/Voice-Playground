# Phase 1: 외부 PCM으로 Seed-VC 실행

`VoiceConversionService`는 기존 엔진의 `_process_block()`을 순차 호출한다. 오디오 장치를 조회하거나 열지 않고 모델 샘플레이트의 mono float32 PCM을 받는다. GUI의 기본 실행 경로는 유지한다.

**상태(2026-10-30): 어댑터 구현 및 자동 검사 12개 통과. 현재 CUDA 환경에서 실제 변환 WAV 생성 성공. GUI 직접 실행과 음질 비교는 미완료다.**

## 실행

PowerShell에서 저장소 루트로 이동한 뒤 실행한다. `C:\Audio\source.wav`와 `C:\Audio\reference.wav`는 사용자가 사용할 파일 경로로 바꾼다. 예제 음성은 저장소에 포함하지 않는다.

```powershell
$env:HF_HOME = "$PWD\seed-vc-realtime\checkpoints\hf-home"
& .\seed-vc-realtime\.venv\Scripts\python.exe .\PythonServer\convert_wav.py `
  --input C:\Audio\source.wav `
  --reference C:\Audio\reference.wav `
  --output .\PythonServer\results\my_conversion.wav `
  --settings .\PythonServer\phase1_settings.json
```

최초 실행에는 모델 다운로드가 필요하다. WAV 옆에 `.report.json`을 저장하며 실패 시에도 원인을 기록한다. 기존 출력 파일은 덮어쓰지 않는다. 짧은 초기 검사는 `--max-seconds 1`을 추가한다. 모델·reference를 한 번 초기화하고 입력 파일을 mono로 합친 뒤 필요한 리샘플링을 수행한다.

현재 `.venv`는 Python 3.12.10, PyTorch/torchaudio 2.4.0+cu121, FunASR 1.4.17이며 RTX 4070 SUPER에서 CUDA 사용을 확인했다. 과거 실패 보고서는 Python 3.11.9, PyTorch 2.4.0+cpu, FunASR 1.4.16 환경의 기록이다. 여러 버전이 달라져 과거 오류의 원인을 CUDA 유무만으로 단정하지 않는다. 이번 수정에서 패키지를 추가 설치하거나 교체하지 않았다. `create_engine()`의 `fp16=False`를 유지해 Float32로 검증했다.

Git 저장소 정보가 없거나 Git 실행이 실패하면 보고서의 `upstream_commit`은 null이고 `upstream_commit_error`에 이유를 기록하며 변환은 계속한다. VAD는 `MODELSCOPE_CACHE` 또는 엔진의 `checkpoints/modelscope` 아래에 config.yaml/model.pt/am.mvn이 갖춰져 있으면 로컬 경로로 로드한다. 캐시가 없으면 기존 원격 다운로드를 사용한다.

## 호출 계약

```python
import numpy as np
from voice_service import VoiceConversionService

service = VoiceConversionService("reference.wav", settings={"extra_time_right": 0.02})
service.initialize()
# pcm은 service.sample_rate의 1차원 float32 배열이어야 한다.
converted = service.process_pcm(np.zeros(service.sample_rate // 50, dtype=np.float32))
tail = service.flush()
```

- `process_pcm()`은 동기 호출이다. 한 모델 블록 미만이면 빈 배열을 반환한다.
- 한 서비스는 한 세션을 소유하며, 동시 호출을 거절한다. 추론 실패 후에는 새 서비스를 생성한다.
- 각 블록에서 VAD 캐시·오디오 문맥·SOLA를 유지한다. 변환 출력은 엔진 내부 버퍼와 분리해 반환한다.
- `flush()`는 잔여 입력을 0으로 패딩해 한 번 처리하고 패딩 분량을 제거한 뒤 세션을 종료한다. 빈 세션도 종료할 수 있다.
- 모델 블록은 20ms 격자에 맞춰 반올림된다. 실험 설정의 0.26초는 격자에 정확히 맞고 VAD 청크 크기와도 일치한다.
- 파일의 입력·출력 샘플 수는 같지만 알고리즘의 look-ahead와 SOLA 지연이 남는다. 마지막 발화 꼬리가 잘리지 않는지 청감 비교해야 한다. 장치용 2블록 priming 무음은 파일 출력에 붙이지 않는다.
- 기존 VAD는 일부 상태 만료에 실제 경과 시간을 사용한다. 오프라인 고속 처리와 실시간 GUI의 무음 경계가 완전히 같다고 보장하지 않는다.
- strict 경로는 VAD 무음 처리 전 모델 출력도 검사한다. 비정상 값을 무음으로 덮어 정상 변환으로 처리하지 않는다.
- WAV 파일 실행기는 상위 코드의 상대 경로를 위해 작업 디렉터리를 엔진 폴더로 바꾼다. 서버 임베딩 시에는 프로세스 초기화 때 작업 디렉터리·캐시 경로를 고정한다.

## 자동 검사

```powershell
$env:HF_HOME = "$PWD\seed-vc-realtime\checkpoints\hf-home"
& .\seed-vc-realtime\.venv\Scripts\python.exe -m unittest discover -s .\PythonServer -p 'test_*.py' -v
```

모델 다운로드 없이 12개 검사를 실행한다. 기존 서비스 검사 7개와 엔진 검사 3개에 Git 조회 실패 시 변환·보고서 저장 검사, 로컬 VAD 캐시 선택/다운로드 경로 검사 2개를 추가했다. 이 검사는 실제 변환 음질을 검증하지 않는다. 당시 실행 로그는 로컬 `results/cuda_unittest.log`에 보관했다.

## 검증 기록

- 2026-10-30: CUDA 실제 변환 1/3/10/30/60초 성공. 저장 WAV 재검사에서 유한성·입출력 샘플 수 일치·비무음 확인. 10/30/60초는 기존 예제를 반복한 시험 입력이다. 자동 검사 12개 통과. 상세 내용과 수치는 [CUDA 검증 기록](issues_cuda_validation.md)에 정리했다.
- 아래는 초기 CPU 환경에서의 과거 기록이다.
- 2026-10-28: 자동 검사 10개 통과.
- 초기 오프라인 실행: checkpoint 미보유로 실패. `results/phase1_offline.report.json`.
- 제한된 네트워크에서 첫 온라인 실행: 이름 조회 실패. `results/phase1_online.report.json`.
- 기본 checkpoint(sample rate 22,050Hz)·CAMPPlus·HiFT·XLS-R·VAD 모델 확보. XLS-R은 초기 연결 종료 이후 구간별 다운로드로 복구하고 SHA256 `d5e490574712ad0a6736923b9ed11d4cd51c78609c36205f704fc4e87b11d2e0`과 일치를 확인했다.
- CPU FP16 실행은 느린 추론 때문에 중단. Float32 실행에서도 비정상 값이 관찰돼 WAV 저장을 거절했다(`results/phase1_diagnostic.report.json`).
- 단계별 진단에서 reference semantic encoder 또는 DiT 출력의 비정상 값이 관찰됐다. 정확한 원인은 미확정이다.
- 스레드 1개·MKLDNN 비활성화·임시 attention fallback 실험에서 첫 모델 블록은 통과했지만, 3초 입력의 VAD에서 `ValueError: math domain error`가 발생했다(`results/phase1_cpu_safe.report.json`). 이 보고서의 `cpu_safe` 명칭은 과거 실험 이름이며 안정화 성공을 뜻하지 않는다.
- 임시 attention fallback은 효과가 입증되지 않아 최종 코드에서 제거했다. `--cpu-baseline`은 스레드 1개·MKLDNN 비활성화 재현용 옵션이며 해결책으로 검증되지 않았다.
- 환경 패키지 목록: `results/environment-packages.txt`.

## 이후 완료할 검증

현재 CUDA 환경에서 실제 WAV 생성에 성공했다. 이번에 확인된 문제와 상세 결과는 [CUDA 검증 기록](issues_cuda_validation.md)에 정리했다. 과거 CPU 보고서와 환경 패키지 목록 등 `results/`의 원본 산출물은 로컬에 보관하며 Git에는 포함하지 않는다.

다음은 GUI 직접 실행과 기준 음성 청감 비교다. 입력·reference를 바꿔 화자 변환을 확인하고 발화 꼬리가 잘리는지 검사한다. 반복 입력의 길이 검증과 실제 다양한 장시간 발화 검증은 구분한다. 파일 처리 속도는 마이크·스피커의 실시간 지연을 뜻하지 않는다. Unity·WebSocket 연동은 Phase 2 이후에 진행한다.
