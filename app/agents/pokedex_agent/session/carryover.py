# Run: python app/agents/pokedex_agent/session/carryover.py
from __future__ import annotations

from app.agents.pokedex_agent.rag.analyze_query import QueryAnalysis, analyze_query
from app.agents.pokedex_agent.session.store import FlowState


def apply_carryover(message: str, flow_state: FlowState) -> tuple[str, QueryAnalysis]:
    analysis = analyze_query(message)
    rewritten = analysis.normalized
    if analysis.is_followup and flow_state.active_name_ko:
        if flow_state.active_name_ko not in rewritten:
            rewritten = f"{flow_state.active_name_ko} {rewritten}".strip()
        if analysis.facet == "profile" and flow_state.last_facet:
            analysis.facet = flow_state.last_facet
            rewritten = f"{rewritten} {flow_state.last_facet}".strip()
    analysis.search_queries = [rewritten, *analysis.search_queries][:3]
    analysis.normalized = rewritten
    return rewritten, analysis


def main() -> None:
    state = FlowState(active_form_id="x", active_name_ko="피카츄", last_facet="weakness")
    print(apply_carryover("그럼?", state))


if __name__ == "__main__":
    main()
