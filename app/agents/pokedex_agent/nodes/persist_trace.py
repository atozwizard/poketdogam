# Run: python app/agents/pokedex_agent/nodes/persist_trace.py
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.pokedex_agent.state import AgentState
from app.agents.pokedex_agent.tools.tool_langfuse import record_trace


def run(state: AgentState) -> AgentState:
    top_score = None
    if state.match_candidates:
        top_score = state.match_candidates[0].get("confidence")
    evidence_sources = sorted(
        {
            str(source)
            for candidate in state.match_candidates
            for source in candidate.get("evidence_sources", [])
        }
    )
    record_trace(
        state.trace_id,
        {
            "intent": state.intent,
            "model": state.llm_model_used,
            "ocr_engine": state.ocr_engine,
            "visual_engine": state.visual_engine,
            "recognition_mode": "+".join(evidence_sources) or "none",
            "match_score": top_score,
            "dataset_version": state.dataset_version,
            "facet": state.retrieval_context.get("facet"),
            "strategy": state.retrieval_context.get("strategy"),
            "error_code": state.error.get("code"),
        },
    )
    return state


def main() -> None:
    state = AgentState()
    print(run(state))


if __name__ == "__main__":
    main()
