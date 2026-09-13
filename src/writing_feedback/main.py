import argparse
import json
from pathlib import Path

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
        request = json.loads(
            args.input.read_text(encoding="utf-8"),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        parser.error(f"입력 파일을 읽을 수 없습니다: {exc}")

    if not isinstance(request, dict):
        parser.error("입력 JSON의 최상위 값은 객체여야 합니다.")

    # 다음 단계: 요청 스키마 검증 → Supervisor 실행
    print("입력 파일 로딩 완료")
    print(json.dumps(request, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
