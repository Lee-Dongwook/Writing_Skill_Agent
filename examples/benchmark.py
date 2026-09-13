"""제한된 실제 Ollama 비교 벤치마크. 기본은 도시 나무 사례 1개만 실행한다."""
import argparse
import asyncio
import json

from writing_feedback.config import Settings
from writing_feedback.main import run_fast_workflow, run_local_workflow
from writing_feedback.orchestration.state import WorkflowMode, WorkflowState
from writing_feedback.rubrics.loader import load_rubric
from writing_feedback.schemas.request import FeedbackRequest

PASSAGE = "도시의 나무는 여름철 기온을 낮추는 데 도움을 준다. 나뭇잎이 햇빛을 가려 그늘을 만들고, 잎에서 물이 증발할 때 주변의 열을 흡수하기 때문이다. 하지만 나무를 심는 것만으로 모든 도시의 더위 문제가 해결되는 것은 아니다. 바람이 통하는 길을 확보하고 건물의 배치를 고려하는 노력도 함께 필요하다."
CASES = {
    "city": ("도시의 나무는 그늘을 만들어 기온을 낮춘다. 그래서 나무를 많이 심으면 도시의 더위 문제를 모두 해결할 수 있다.", {"distortion"}),
    "accurate": ("도시의 나무는 그늘과 물의 증발로 기온을 낮추지만, 더위 문제를 해결하려면 바람길과 건물 배치도 고려해야 한다.", set()),
    "reversed_cause": ("도시의 기온이 낮아지면 나뭇잎이 햇빛을 가리고 물이 증발한다.", {"distortion"}),
    "missing_limit": ("도시의 나무는 그늘과 물의 증발로 여름철 기온을 낮춘다.", {"omission"}),
    "unsupported": ("도시의 나무는 그늘을 만들고 모든 시민의 건강을 완벽하게 지킨다.", {"unsupported_claim"}),
}


async def one(name: str, student_text: str, expected: set[str], mode: str, settings: Settings) -> dict:
    request = FeedbackRequest(school_level="elementary", grade=5, instruction="지문의 중심 내용을 두 문장으로 요약하세요.", passage=PASSAGE, student_text=student_text)
    state = WorkflowState(request=request, rubric=load_rubric(request), mode=WorkflowMode.FAST if mode == "fast" else WorkflowMode.DETAILED, max_retries=0, max_steps=1 if mode == "fast" else 3)
    print(f"[진행] {name} / {mode}", flush=True)
    result = await (run_fast_workflow(state, settings) if mode == "fast" else run_local_workflow(state, settings))
    issues = result.fast_feedback.issues if result.fast_feedback else (result.evaluation.issues if result.evaluation else [])
    found = {issue.category.value for issue in issues}
    return {"case": name, "mode": mode, "status": result.status.value, "total_seconds": result.performance.get("total_seconds"), "calls": result.performance.get("calls", []), "expected_categories": sorted(expected), "detected_categories": sorted(found), "expected_categories_detected": expected.issubset(found)}


async def main_async(args):
    settings = Settings()
    names = list(CASES) if args.all_cases else ["city"]
    modes = ["fast", "detailed"] if args.compare else [args.mode]
    results = []
    for name in names:
        student, expected = CASES[name]
        for mode in modes:
            results.append(await one(name, student, expected, mode, settings))
    print(json.dumps({"settings": {"model": settings.ollama_model, "num_ctx": settings.llm_num_ctx, "detailed_num_predict": settings.llm_num_predict, "fast_num_predict": settings.fast_num_predict, "temperature": settings.llm_temperature, "think": settings.llm_think}, "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fast", "detailed"], default="fast")
    parser.add_argument("--compare", action="store_true", help="각 사례에서 fast와 detailed를 차례로 실행")
    parser.add_argument("--all-cases", action="store_true", help="고정 5개 사례 실행(호출 수가 증가함)")
    asyncio.run(main_async(parser.parse_args()))
