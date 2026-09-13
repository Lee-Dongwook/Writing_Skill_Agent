import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from writing_feedback.schemas.request import FeedbackRequest
from writing_feedback.orchestration.state import WorkflowState


def main() -> None:
    parser = argparse.ArgumentParser(
        description="국어 비문학 요약문 첨삭 에이전트",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="첨삭 요청 JSON 파일 경로",
    )
    args = parser.parse_args()

    try:
        payload = json.loads(
            args.input.read_text(encoding="utf-8"),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        parser.error(f"입력 파일을 읽을 수 없습니다: {exc}")

    try:
        request = FeedbackRequest.model_validate(payload)
    except ValidationError as exc:
        messages = []

        for error in exc.errors(include_input=False):
            location = ".".join(
                str(part) for part in error["loc"]
            ) or "request"

            messages.append(
                f"- {location}: {error['msg']}"
            )

        parser.error(
            "입력값 검증에 실패했습니다.\n"
            + "\n".join(messages)
        )

    # 다음 단계: 검증된 요청을 Supervisor에 전달
    print("입력값 검증 완료")
    print(request.model_dump_json(indent=2))

    state = WorkflowState(request=request)

    print("첨삭 실행 상태 생성 완료")
    print(state.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
