# Voice tools Phase 1 커밋 기록

작성: 2026-11-17. `feat/voice-tools-phase1` 로컬 브랜치에서 수행한 작업을 기록한다. 이 문서는 검토용 `commit_plan.md`를 완료 상태로 갱신한 것이다. 커밋은 `origin/main`의 `fb45ceb`에서 분기했다.

## 완료된 커밋

| 순서 | 커밋 | 메시지 | 포함한 파일과 처리 결과 |
|---|---|---|---|
| 1 | `a56581c` | `chore: ignore generated voice conversion files` | 루트 `.gitignore`와 `ConvertToWav/`, `PythonServer/`, `seed-vc-realtime/`의 `.gitignore` 4개. 환경·모델·결과물과 검토되지 않은 예제 음성·영상을 무시한다. Unity 전용 규칙과 `PythonServer/results/*.py` 예외는 제외했다. |
| 2 | `ba136fa` | `feat: add M4A to WAV converter` | `ConvertToWav/`의 README, `convert_to_wav.py`, `gui.py`, `requirements.txt`, `test_converter.py`, `실행.bat` 6개. 파일 변환, GUI, 잘못된 입력 테스트 3개 통과. |
| 3 | `516646f` | `chore: vendor Seed-VC realtime engine` | `seed-vc-realtime/`의 소스·모델 설정·README·`LICENSE` 67개. README에 [외부 저장소](https://github.com/jiaheguo521/seed-vc-realtime)의 기준 커밋과 로컬 변경 내용을 기록했다. GUI의 `configs/config.json`에서 개인 경로와 오디오 장치명을 제거했다. |
| 4 | `e8135f9` | `feat: process external PCM with Seed-VC` | `PythonServer/`의 서비스, WAV 실행기, 설정, 테스트 파일 6개. 모델 없이 실행하는 서비스·엔진·실행기 테스트 12개 통과. |
| 5 | `fbe35b9` | `docs: document phase one validation` | `plan_phase1.md`, `phase1_summary.md`, `PythonServer/README.md`, `PythonServer/issues_cuda_validation.md` 4개. 사용자 제공 WAV 경로로 실행 예시를 바꾸고 Git에 없는 결과물 링크를 로컬 기록으로 정리했다. |

각 커밋은 한 목적을 담고 영어 Conventional Commits 제목을 사용했다. 로컬 `commit-msg` hook과 `node scripts/check_commit_messages.js --range origin/main..HEAD`에서 다섯 메시지가 모두 통과했다. 샘플 미디어, 모델 캐시, 결과 파일은 어느 커밋에도 들어가지 않았다.

## 제외한 파일

| 경로 | 결정 |
|---|---|
| `seed-vc-realtime/examples/reference/*.wav` 12개, `seed-vc-realtime/examples/source/*.wav` 10개 | 배포 권한을 파일별로 확인하지 않아 제외했다. 여기에는 사용자 녹음 `korean_recording.wav`도 포함된다. 약 24.8 MiB이며 Git ignore 대상이다. |
| `seed-vc-realtime/assets/real-time-demo.webm` | 실행에 필요하지 않은 약 3.2 MiB 영상. 배포 권한 확인 전 제외했다. |
| `PythonServer/results/diagnose_model.py`, `PythonServer/results/recover_download.py` | 일회성 진단·모델 다운로드 복구 스크립트이므로 제외했다. |
| `PythonServer/results/*`의 변환 WAV, 보고서, 로그, 패키지 목록 | 로컬 검증 산출물이다. 문서에 필요한 결과와 한계를 요약했고 원본은 Git에 넣지 않았다. |
| `ConvertToWav/.venv/`, `ConvertToWav/output/`, `seed-vc-realtime/.venv/`, `seed-vc-realtime/checkpoints/`, `__pycache__/` 등 | 재생성하는 환경·모델·출력 파일이므로 제외했다. |

## 확인 결과와 남은 범위

- 변환기 자동 테스트 3개와 외부 PCM·엔진 자동 테스트 12개가 통과했다. GUI 기본 엔진 초기화 경로는 엔진 테스트에 포함된다.
- `seed-vc-realtime/configs/config.json`은 GUI 시작에 필요하므로 커밋하되 `reference_audio_path`와 장치명을 빈 값으로 두었다. 실행 시 장치 선택은 GUI의 기본 장치 선택 경로를 따른다.
- 외부 Seed-VC 코드의 GPL-3.0 `LICENSE`를 보존하고 원본 및 로컬 변경 사항을 README에 표시했다. 샘플 음성과 영상의 배포 권한은 확인하지 않았다.
- 실제 음질 비교, 다양한 입력·기준 화자 검증, 장치 지연 측정은 Phase 1 문서에 남은 작업으로 기록돼 있다. 이번 커밋은 이 항목들을 완료로 주장하지 않는다.
- 이 기록을 작성할 때 브랜치는 로컬에만 있었다. 이 문서는 푸시나 PR 생성 사실을 기록하지 않는다.
