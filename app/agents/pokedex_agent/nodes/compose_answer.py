# Run: python app/agents/pokedex_agent/nodes/compose_answer.py
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.pokedex_agent.state import AgentState
from app.agents.pokedex_agent.tools.tool_local_llm import generate_local_answer


def run(state: AgentState) -> AgentState:
    state.llm_provider_used = "local"

    detail = state.retrieval_context.get("detail") if state.retrieval_context else None
    if not isinstance(detail, dict):
        state.llm_runtime = "template"
        state.llm_model_used = "template"
        state.response_text = "찌릿… 로컬 도감 메모리에서 대상을 못 찾았어. 이름을 조금 더 정확히 찍어줘-로!"
        return state

    template_answer = build_template_answer(state, detail)
    llm_result = generate_local_answer(state.input_text, detail, template_answer)
    state.llm_runtime = llm_result["runtime"]
    state.llm_model_used = llm_result["model"]
    state.response_text = llm_result["answer"]
    if llm_result["error"]:
        state.error = {"code": "local_llm_fallback", "message": llm_result["error"]}
    return state


def build_template_answer(state: AgentState, detail: dict[str, object]) -> str:
    name = str(detail.get("name_ko") or detail.get("name_en") or "이 포켓몬")
    types = ", ".join(str(item) for item in detail.get("types", [])) or "미확인"
    generation = detail.get("generation")
    stats = detail.get("stats") if isinstance(detail.get("stats"), dict) else {}
    bst = stats.get("bst")

    generation_text = f"{generation}세대" if generation else "세대 미상"
    bst_text = f" 종족값 합계는 {bst}." if bst else ""
    return f"찌릿! {name}는 {generation_text} 포켓몬이고 타입은 {types}야.{bst_text} 도감 메모리에 잠금-로!"


def main() -> None:
    state = AgentState(input_text="피카츄 알려줘")
    print(run(state))


if __name__ == "__main__":
    main()
