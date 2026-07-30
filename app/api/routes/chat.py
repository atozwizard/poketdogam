# Run: python app/api/routes/chat.py
from pathlib import Path
import json
import re
import sys
from collections.abc import Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from app.agents.pokedex_agent.graph import PokedexAgentGraph
from app.agents.pokedex_agent.nodes.compose_answer import build_template_answer, run as compose_answer
from app.agents.pokedex_agent.nodes.ingest_input import run as ingest_input
from app.agents.pokedex_agent.nodes.persist_trace import run as persist_trace
from app.agents.pokedex_agent.nodes.retrieve_local_dex import run as retrieve_context
from app.agents.pokedex_agent.session.carryover import apply_carryover
from app.agents.pokedex_agent.session.store import FlowState, SessionStore
from app.agents.pokedex_agent.state import AgentState
from app.agents.pokedex_agent.tools.tool_local_llm import stream_local_answer
from app.schemas.api import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])
agent = PokedexAgentGraph()
sessions = SessionStore()
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str) -> Response:
    if not SESSION_ID_PATTERN.fullmatch(session_id):
        raise HTTPException(status_code=422, detail="Invalid session id")
    if not sessions.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return Response(status_code=204)


@router.get("/privacy/status")
def privacy_status() -> dict[str, object]:
    return {
        "session_retention_seconds": 1800,
        "trace_retention_days": 7,
        "raw_images_stored": False,
        "ocr_text_stored": False,
        "chat_stored_locally": True,
        "delete_endpoint": "/v1/sessions/{session_id}",
    }


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    state, session, flow_state, analysis = _prepare_chat_state(request)
    compose_answer(state)
    persist_trace(state)
    _persist_session(session.session_id, request.message, state, flow_state, analysis.facet)
    citations = _citations(state)
    return ChatResponse(
        answer=state.response_text,
        confidence=0.8 if state.retrieval_context.get("detail") else 0.35,
        trace_id=state.trace_id,
        session_id=session.session_id,
        llm_runtime=state.llm_runtime,
        llm_model=state.llm_model_used,
        facet=str(state.retrieval_context.get("facet") or analysis.facet),
        suggested_actions=_suggested_actions(state),
        citations=citations,
    )


@router.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    state, session, flow_state, analysis = _prepare_chat_state(request)

    def events() -> Iterator[str]:
        detail = state.retrieval_context.get("detail") if state.retrieval_context else None
        if not isinstance(detail, dict):
            answer = "찌릿… 로컬 도감 메모리에서 대상을 못 찾았어. 이름을 조금 더 정확히 찍어줘-로!"
            state.response_text = answer
            state.llm_runtime = "template"
            state.llm_model_used = "template"
            yield _sse(
                {
                    "event": "meta",
                    "runtime": "template",
                    "model": "template",
                    "trace_id": state.trace_id,
                    "session_id": session.session_id,
                    "facet": analysis.facet,
                }
            )
            yield _sse({"event": "delta", "text": answer, "trace_id": state.trace_id})
            yield _sse(
                {
                    "event": "done",
                    "answer": answer,
                    "runtime": "template",
                    "model": "template",
                    "trace_id": state.trace_id,
                    "session_id": session.session_id,
                    "suggested_actions": _suggested_actions(state),
                }
            )
            _persist_session(session.session_id, request.message, state, flow_state, analysis.facet)
            persist_trace(state)
            return

        template_answer = build_template_answer(state, detail)
        yield _sse(
            {
                "event": "meta",
                "runtime": "pending",
                "model": "pending",
                "trace_id": state.trace_id,
                "session_id": session.session_id,
                "facet": analysis.facet,
                "strategy": state.retrieval_context.get("strategy"),
            }
        )
        facet = str(state.retrieval_context.get("facet") or analysis.facet)
        if facet in {"weakness", "resistance", "type", "evolution", "stats"}:
            state.llm_runtime = "template"
            state.llm_model_used = "grounded_template"
            state.response_text = template_answer
            yield _sse({"event": "delta", "text": template_answer, "trace_id": state.trace_id})
            yield _sse(
                {
                    "event": "done",
                    "answer": template_answer,
                    "runtime": "template",
                    "model": "grounded_template",
                    "trace_id": state.trace_id,
                    "session_id": session.session_id,
                    "suggested_actions": _suggested_actions(state),
                    "citations": _citations(state),
                }
            )
            _persist_session(session.session_id, request.message, state, flow_state, analysis.facet)
            persist_trace(state)
            return
        for event in stream_local_answer(state.input_text, detail, template_answer):
            state.llm_runtime = event.get("runtime", state.llm_runtime)
            state.llm_model_used = event.get("model", state.llm_model_used)
            if event.get("event") == "done":
                state.response_text = event.get("answer", "")
                if event.get("error"):
                    state.error = {"code": "local_llm_fallback", "message": event["error"]}
                payload = {
                    **event,
                    "trace_id": state.trace_id,
                    "session_id": session.session_id,
                    "suggested_actions": _suggested_actions(state),
                    "citations": _citations(state),
                }
                yield _sse(payload)
            else:
                yield _sse({**event, "trace_id": state.trace_id, "session_id": session.session_id})
        _persist_session(session.session_id, request.message, state, flow_state, analysis.facet)
        persist_trace(state)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def _prepare_chat_state(request: ChatRequest):
    session = sessions.ensure(request.session_id)
    flow_state = session.flow_state
    if request.form_id:
        flow_state.active_form_id = request.form_id
    rewritten, analysis = apply_carryover(request.message, flow_state)
    state = AgentState(session_id=session.session_id, input_text=rewritten)
    state.entities = {
        "form_id": request.form_id or flow_state.active_form_id or "",
        "name_ko": flow_state.active_name_ko,
    }
    ingest_input(state, rewritten)
    retrieve_context(state, rewritten)
    return state, session, flow_state, analysis


def _persist_session(
    session_id: str,
    user_message: str,
    state: AgentState,
    flow_state: FlowState,
    facet: str,
) -> None:
    detail = state.retrieval_context.get("detail") if state.retrieval_context else None
    if isinstance(detail, dict):
        flow_state.active_form_id = str(detail.get("form_id") or flow_state.active_form_id)
        flow_state.active_name_ko = str(detail.get("name_ko") or flow_state.active_name_ko)
    flow_state.last_facet = str(state.retrieval_context.get("facet") or facet)
    passages = state.retrieval_context.get("passages") if isinstance(state.retrieval_context, dict) else []
    if isinstance(passages, list):
        flow_state.evidence_ids = [str(item.get("passage_id")) for item in passages[:5] if isinstance(item, dict)]
    sessions.append_exchange(
        session_id,
        user_content=user_message,
        assistant_content=state.response_text,
        assistant_metadata={
            "trace_id": state.trace_id,
            "facet": flow_state.last_facet,
            "strategy": state.retrieval_context.get("strategy"),
            "form_id": flow_state.active_form_id,
        },
        flow_state=flow_state,
    )


def _suggested_actions(state: AgentState) -> list[str]:
    detail = state.retrieval_context.get("detail") if state.retrieval_context else None
    if not isinstance(detail, dict):
        return ["이름으로 다시 스캔", "피카츄 알려줘"]
    name = str(detail.get("name_ko") or "이 포켓몬")
    return [f"{name} 약점", f"{name} 진화", f"{name} 종족값"]


def _citations(state: AgentState) -> list[dict[str, str]]:
    passages = state.retrieval_context.get("passages") if isinstance(state.retrieval_context, dict) else []
    facet = str(state.retrieval_context.get("facet") or "profile")
    detail = state.retrieval_context.get("detail") if isinstance(state.retrieval_context, dict) else None
    if facet in {"weakness", "resistance", "type", "evolution", "stats"} and isinstance(detail, dict):
        labels = {
            "weakness": "타입 상성표 기반 약점",
            "resistance": "타입 상성표 기반 반감·무효",
            "type": "선택 폼의 타입 정보",
            "evolution": "선택 폼의 진화 관계",
            "stats": "선택 폼의 종족값",
        }
        return [
            {
                "passage_id": f"fact:{facet}:{detail.get('form_id') or ''}",
                "title": labels[facet],
                "facet": facet,
            }
        ]
    if not isinstance(passages, list):
        return []
    citations = []
    for item in passages[:3]:
        if not isinstance(item, dict):
            continue
        citations.append(
            {
                "passage_id": str(item.get("passage_id") or ""),
                "title": str(item.get("title") or ""),
                "facet": str(item.get("facet") or ""),
            }
        )
    return citations


def _sse(event: dict[str, object]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def main() -> None:
    response = chat(ChatRequest(message="피카츄 알려줘"))
    print(response.model_dump())


if __name__ == "__main__":
    main()
