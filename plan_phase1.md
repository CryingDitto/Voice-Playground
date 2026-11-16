# Phase 1 — 외부 PCM 입력을 받는 Seed-VC 엔진 분리

## 목표와 범위

마이크·스피커를 열지 않고 WAV 파일을 작은 mono float32 PCM 조각으로 전달해 변환 WAV를 저장한다. 기존 `_process_block()`의 VAD, 문맥, SOLA와 reference conditioning을 재사용한다. Unity 생성, WebSocket, 실시간 재생과 다중 세션은 이후 단계다.

## 초기 CPU 작업 당시 기준선 (과거 기록)

- 저장소: `seed-vc-realtime`, commit `58d0ca372cc76f60a798d9f84611f053f9029f3a`
- Python: 기존 `.venv`의 3.11.9
- PyTorch: 2.4.0+cpu, 현재 Python에서 CUDA 사용 불가. 하드웨어는 RTX 4070 SUPER(12GB), 드라이버 610.88로 확인됐으므로 GPU 부재가 아니라 CPU 전용 PyTorch 환경의 제약이다. 현재 환경에서 GPU 실시간 성능을 검증할 수 없다.
- 당시 `configs/config.json`의 reference 경로는 다른 PC 경로여서 예제 WAV를 명시적으로 사용했다. 저장소에 포함하는 기본 설정은 이후 범용 값으로 교체했다.
- 기존 GUI는 입력 장치 조회와 버퍼 준비가 결합되어 있고, 추론 오류를 무음으로 숨길 수 있다.

## 작업 순서

1. [x] GUI 기본 실행 경로를 유지하면서 장치 열거를 생략하고 모델 샘플레이트·mono로 버퍼를 준비하는 경로 추가. GUI 직접 실행 회귀 검사는 별도 필요.
2. [x] `PythonServer/voice_service.py`: 모델 1회 초기화, 작은 PCM 누적, 한 엔진의 순차 추론, 오류 전파, 종료 시 잔여 샘플 패딩 처리.
3. [x] WAV 실행 도구: 입력을 모델 샘플레이트로 변환, 20ms 조각 전달, 출력 WAV와 설정·시간·환경 보고서 저장 기능 구현.
4. [x] 모델 없이 실행 가능한 경계·누락·순서·오류 테스트와 기존 엔진의 실제 DSP 경로 검사.
5. [x] 설치 의존성과 모델 캐시 확인 후 실제 VC 실행 시도. 초기 CPU 실패 기록 보존. 2026-10-30 CUDA 환경에서 실제 변환 WAV 생성 성공, GUI 음질 비교는 미완료.
6. [x] README와 이 계획서에 실제 검증 결과 및 미완료 항목 기록.

## 인터페이스와 정책

- `initialize()` 후 `sample_rate`, `block_size` 확인.
- `process_pcm(pcm)`은 동기 호출이며 모델 블록이 쌓이면 처리하고 가용 출력을 반환한다. 네트워크 비동기 작업은 Phase 2가 담당한다.
- 입력은 유한한 1차원 mono float32, 모델 샘플레이트. 리샘플링은 WAV 도구가 담당한다.
- 모델·reference는 세션 초기화 시 준비하고 매 조각마다 다시 로드하지 않는다.
- 동시 호출은 거절한다. 추론 실패 후 세션 재사용을 거절해 오염된 스트리밍 상태가 이어지지 않게 한다.
- `flush()`는 마지막 불완전 블록을 0으로 패딩하고 패딩 분량을 잘라낸다. 알고리즘 자체의 look-ahead/SOLA 지연은 그대로이며 GUI 오디오 장치용 priming 무음은 붙이지 않는다.
- 출력의 파일 길이와 실제 음성 정렬은 구분한다. GUI와의 청감 비교 전 음질 동등성을 주장하지 않는다.

## 완료 기준

- 장치 조회·스트림 생성 없이 외부 PCM을 처리한다.
- 청크 크기가 달라도 같은 입력 순서와 출력 샘플 수를 유지한다.
- VAD·SOLA·문맥이 블록 간 유지되고 추론 오류가 호출자에게 전달된다.
- 실제 Seed-VC로 WAV를 생성하고 GUI 결과와 비교한다. 모델·환경 문제로 실행하지 못한 경우 이 항목은 미완료로 남긴다.

## 초기 CPU 작업 검증 결과 (과거 기록)

아래에서 언급하는 `PythonServer/results/` 원본 보고서와 패키지 목록은 로컬 검증 산출물이며 Git에는 포함하지 않는다. 확인된 결과와 한계는 이 문서와 `PythonServer/issues_cuda_validation.md`에 남긴다.

- 자동 검사 10개 통과: 서비스 계약 7개, 실제 엔진의 DSP 경로 및 GUI 기본 초기화 회귀 검사 3개(신경망만 대체).
- 기존 엔진 변경: 장치 열거 선택, 외부 오디오 버퍼 준비, strict 추론 오류 전파, 첫 reference 중복 로드 방지.
- 작은 입력 청크의 순서·샘플 수·최종 패딩, 초기화 재호출, 실패 세션 거절, 동시 호출 거절 확인.
- 실제 VAD·문맥·SOLA 경로에서 장치 조회와 스트림 생성이 일어나지 않는 것을 확인.
- 모델 캐시 없는 오프라인 실행 실패 기록: `PythonServer/results/phase1_offline.report.json`.
- 첫 온라인 실행의 네트워크 이름 조회 실패 기록: `PythonServer/results/phase1_online.report.json`.
- 네트워크 허용 후 Seed-VC 기본 checkpoint·CAMPPlus·HiFT 로딩 진행. 기본 checkpoint 설정의 sample rate는 22,050Hz.
- 첫 허용 실행은 XLS-R 모델 1,269,737,156바이트 중 892,376,410바이트 수신 후 연결이 끊겨 실패. `PythonServer/results/phase1_model.report.json`.
- XLS-R 구간별 다운로드 복구 완료. 전체 SHA256을 캐시 파일명 해시와 대조해 일치 확인. VAD 모델도 확보.
- CPU에서 semantic encoder FP16을 강제하는 경로를 Float32로 수정. GPU에서는 `fp16` 옵션을 따름.
- 실제 1초 입력 실행: 모델 출력 5,733개 샘플 전체가 비정상 값으로 검출되어 WAV 저장을 거절함. `PythonServer/results/phase1_diagnostic.report.json`.
- 단계별 진단에서 reference semantic encoder 또는 DiT 출력의 비정상 값이 관찰됨. 원인은 아직 확정하지 못함.
- CPU 스레드 1개·MKLDNN 비활성화·임시 attention fallback을 조합한 실험에서는 첫 모델 블록은 유한했지만, 3초 입력 실행 중 VAD가 `ValueError: math domain error`를 발생시킴. `PythonServer/results/phase1_cpu_safe.report.json`.
- 효과가 입증되지 않은 attention fallback은 최종 코드에서 제거. 진단용 CPU 설정만 실행 도구의 `--cpu-baseline` 옵션으로 제공하며 안정성을 보장하지 않음.
- strict 경로는 VAD 무음 처리 전에도 비정상 모델 출력을 검사해 실패를 숨기지 않음.
- 전체 Python 패키지 기준선: `PythonServer/results/environment-packages.txt`.
- 청감 비교·GUI 직접 실행 회귀 검사·실시간 GPU 성능은 아직 미검증.

## 현재 상태와 다음 작업

**2026-10-30: 외부 PCM 어댑터 구현, 자동 검사 12개, CUDA 실제 변환 WAV 생성 확인. GUI 직접 실행·청감 비교 완료 기준은 미충족.**

현재 환경은 Python 3.12.10, PyTorch/torchaudio 2.4.0+cu121, FunASR 1.4.17이다. RTX 4070 SUPER에서 CUDA 사용을 확인했다. 패키지는 사용자가 준비한 상태를 유지했다. Git 정보 없는 폴더에서 실행 중단, 로컬 VAD 캐시가 있어도 원격 조회가 필요한 문제를 수정했다.

CUDA 변환은 1/3/10/30/60초에서 성공했고 저장 WAV의 유한성·입출력 샘플 수 일치·비무음을 확인했다. 10/30/60초는 기존 예제를 반복한 시험 입력이다. 60초 출력은 1,323,000개 샘플이며, 초기화를 제외한 블록 처리 시간 합계는 입력 길이의 약 0.491배였다. 실제 장치 지연이나 청감 품질을 검증한 수치는 아니다.

과거 CPU 비정상 샘플/VAD 오류는 현재 검증에서 재현되지 않았다. Python·FunASR 버전도 달라졌으므로 원인 해결을 CUDA에만 귀속하지 않는다. 상세 문제 목록·검증 결과는 `PythonServer/issues_cuda_validation.md`에 있다. 과거 보고서와 최신 패키지 목록은 로컬에 보존했다.

1. 생성 WAV와 GUI 기준 음성을 청감 비교하고 실제 GUI 실행을 확인한다.
2. 다양한 입력·reference로 화자 변환과 발화 꼬리, 실제 장시간 발화를 검사한다.
3. 오디오 장치의 실시간 지연·안정성을 검증하고 이후 Unity·WebSocket 연동을 진행한다.
