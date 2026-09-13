# 국어 비문학 첨삭 에이전트

교사가 검토할 요약문 첨삭 초안을 만드는 로컬 Ollama 도구입니다. 결과는 자동 승인·채점 결과가 아니며 반드시 교사가 검토해야 합니다.

## 실행 모드

- `--local`: 기본 권장. 빠른 단일 LLM 호출로 원문 핵심 요약, 최대 3개의 중요 문제, 근거 인용, 짧은 학생 피드백을 만듭니다.
- `--detailed`: 기존 지문 분석 → 평가 → 첨삭의 3단계 경로입니다. 더 자세하지만 원문과 중간 JSON을 다시 전달하므로 느립니다.
- `--passage-only`: 기존 지문 분석·근거 검증만 실행합니다.
- `--mock`: 모델 없이 기존 전체 흐름을 확인합니다.

## 설치와 빠른 실행

Python 3.10 이상에서 의존성을 설치하고 Ollama에 `qwen3:4b`가 준비되어 있어야 합니다.

```bash
python -m pip install -e .
ollama serve
ollama pull qwen3:4b
cp .env.example .env
writing-feedback --input examples/summary_request.json --local
```

## 웹 화면과 로컬 API 실행

가안 React 화면은 실제 Python Agent API를 호출합니다. 브라우저는 Ollama에 직접 연결하지 않습니다. 터미널을 두 개 열어 다음 순서로 실행하세요.

```bash
# 터미널 1: Python 3.10+ 가상환경에서
python -m pip install -e .
ollama serve
writing-feedback-api

# 터미널 2
pnpm install
pnpm dev
```

`http://localhost:5173`에서 학교급·학년, 과제 지시문, 원문, 학생 글을 입력합니다. 기본 `빠른 첨삭`은 기존 단일 호출 Agent를 사용하고, `상세 분석`은 지문 분석 → 평가 → 첨삭의 기존 3단계 Agent를 사용합니다. 두 모드 모두 원문/학생 글 인용 검증과 학교급별 YAML 평가 기준을 그대로 사용합니다.

### HTTP 계약과 상태

- `POST /api/runs`: `school_level`, `grade`, `task_type`(`summary`), `instruction`, `passage`, `student_text`, 선택 `teacher_guidance`, `mode`(`fast` 또는 `detailed`)를 받아 `202`와 `run_id`를 반환합니다.
- `GET /api/runs/{run_id}`: `pending`(대기), `running`(실행 중, 실제 Agent 단계 포함), `awaiting_teacher_review`(결과 완료), `failed`를 반환합니다.
- 생성 POST는 자동 재시도하지 않습니다. 실패 화면의 **같은 입력으로 다시 실행** 버튼만 새 작업을 명시적으로 만듭니다.

API는 로컬 개발용 단일 프로세스 메모리 저장소입니다. LLM 동시 실행은 1개, 대기열은 기본 8개이며, 서버 재시작 시 대기·결과 작업은 유실됩니다. 완료 결과는 기본 1시간 뒤 정리됩니다(`WRITING_API_RESULT_TTL_SECONDS`). 저장·승인 워크플로우는 구현하지 않았습니다.

### 연결 환경 변수

프론트엔드는 기본적으로 `http://127.0.0.1:8000`을 사용합니다. 다른 위치의 API라면 프론트 실행 환경에 다음을 설정합니다.

```bash
VITE_WRITING_API_BASE_URL=http://127.0.0.1:8000 pnpm dev
```

Python API의 설정은 `.env.example`을 복사해 `.env`에서 관리합니다. `WRITING_API_CORS_ORIGINS`에는 실제 프론트 개발 origin만 쉼표로 구분해 넣으세요. 원격 프론트/컨테이너의 `localhost`는 Mac의 Ollama가 아닙니다. 이 구성은 **API와 Ollama를 같은 Mac에서 실행**하는 로컬 개발 전제입니다. 원격 API를 쓸 경우 API 호스트가 접근 가능한 Ollama 주소를 별도로 제공해야 하며, 학생 글을 공개 인터넷에 노출하지 마세요.

### 확인 방법

모델 없이 API 연결·결과 변환을 확인하는 테스트와 기존 Agent 테스트는 다음으로 실행합니다.

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
pnpm build
```

실제 Ollama 통합은 짧은 입력으로 화면에서 한 번만 실행하거나 아래 CLI로 확인합니다.

```bash
writing-feedback --input examples/summary_request.json --local
```

실패 시 화면은 API 연결 실패, 요청 검증 오류, 대기열 포화, 모델 호출/시간 초과, 출력 형식·근거 검증 실패, 서버 재시작에 따른 작업 유실을 구분해 표시합니다. 입력·모델 전체 응답은 기본 실행 로그나 성능 메타데이터에 기록하지 않습니다.

`.env`의 기본 빠른 설정은 `think=false`, `temperature=0.1`, `num_ctx=4096`, `fast_num_predict=512`입니다. 상세 경로의 출력 상한은 2048입니다. 환경과 모델에서 실제 적용값은 각 실행 결과의 `performance.calls`에 기록됩니다. 입력·출력 본문은 성능 로그에 저장하지 않습니다.

빠른 경로는 토크나이저 없이 한국어 문자 수를 바탕으로 **보수적으로 추정**한 입력 예산(기본 3000)을 검사합니다. 한도를 넘는 요청은 조용히 자르지 않고 `input_budget_exceeded`로 실패합니다. 더 긴 글은 상세 경로를 쓰거나, 교사가 입력을 분할한 뒤 각각 검토하세요.

## 성능 계측과 벤치마크

결과의 `performance`에는 전체 시간, 단계/시도별 호출 수와 시간, 모델·컨텍스트·생성 설정, Ollama의 `load_duration`, `prompt_eval_duration`, `eval_duration`(나노초를 초로 변환), 토큰 수, 생성 tokens/sec, 완료 사유와 오류 종류가 있습니다. 출력 상한 도달(`done_reason=length`)은 성공으로 처리하지 않습니다.

실제 Mac에서 먼저 도시 나무 사례의 두 경로를 제한된 횟수로 비교합니다.

```bash
PYTHONPATH=src python examples/benchmark.py --compare
```

첫 호출에는 모델 로딩 비용이 포함될 수 있습니다. 위 명령의 fast 뒤 detailed는 같은 모델을 유지하므로 후속 호출 비용도 함께 관찰할 수 있습니다. 고정 5개(기존 도시 나무, 정확, 인과 뒤집기, 한계 누락, 원문 밖 주장)를 모두 측정하려면 호출 수가 늘어나는 것을 알고 다음을 실행합니다.

```bash
PYTHONPATH=src python examples/benchmark.py --compare --all-cases
```

벤치마크는 모델이 매긴 점수가 아니라 예상 오류 유형의 탐지 여부를 별도로 출력합니다. 연결할 Ollama가 없으면 외부 API로 대체하지 않으며, 아래 테스트만 실행할 수 있습니다.

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## 제한 사항

원문·학생 글 인용의 **존재와 문단 위치**는 검증하지만, 인용을 바탕으로 한 의미 해석의 정확성까지 기계적으로 증명하지는 못합니다. 로컬 모델의 실제 속도는 Mac의 모델 상태, 로딩 여부, 컨텍스트에 좌우되므로 이 저장소에서는 측정값을 미리 주장하지 않습니다.
