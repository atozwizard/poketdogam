# Run: python app/api/routes/chat.py
from pathlib import Path
import json
import sys
from collections.abc import Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agents.pokedex_agent.graph import PokedexAgentGraph
from app.agents.pokedex_agent.nodes.compose_answer import build_template_answer
from app.agents.pokedex_agent.nodes.ingest_input import run as ingest_input
from app.agents.pokedex_agent.nodes.persist_trace import run as persist_trace
from app.agents.pokedex_agent.nodes.retrieve_local_dex import run as retrieve_context
from app.agents.pokedex_agent.state import AgentState
from app.agents.pokedex_agent.tools.tool_local_llm import stream_local_answer
from app.schemas.api import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])
agent = PokedexAgentGraph()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    state = agent.run_chat(message=request.message, form_id=request.form_id)
    return ChatResponse(
        answer=state.response_text,
        confidence=0.75,
        trace_id=state.trace_id,
        llm_runtime=state.llm_runtime,
        llm_model=state.llm_model_used,
        citations=[],
    )


@router.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    state = _prepare_chat_state(request)

    def events() -> Iterator[str]:
        detail = state.retrieval_context.get("detail") if state.retrieval_context else None
        if not isinstance(detail, dict):
            answer = "로컬 도감에서 대상을 찾지 못했어요. 이름을 조금 더 정확히 입력해 주세요."
            state.response_text = answer
            state.llm_runtime = "template"
            state.llm_model_used = "template"
            yield _sse({"event": "meta", "runtime": "template", "model": "template", "trace_id": state.trace_id})
            yield _sse({"event": "delta", "text": answer, "trace_id": state.trace_id})
            yield _sse(
                {
                    "event": "done",
                    "answer": answer,
                    "runtime": "template",
                    "model": "template",
                    "trace_id": state.trace_id,
                }
            )
            persist_trace(state)
            return

        template_answer = build_template_answer(state, detail)
        for event in stream_local_answer(state.input_text, detail, template_answer):
            state.llm_runtime = event.get("runtime", state.llm_runtime)
            state.llm_model_used = event.get("model", state.llm_model_used)
            if event.get("event") == "done":
                state.response_text = event.get("answer", "")
                if event.get("error"):
                    state.error = {"code": "local_llm_fallback", "message": event["error"]}
            yield _sse({**event, "trace_id": state.trace_id})
        persist_trace(state)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def _prepare_chat_state(request: ChatRequest) -> AgentState:
    state = AgentState()
    state.entities = {"form_id": request.form_id or ""}
    ingest_input(state, request.message)
    retrieve_context(state, request.form_id or request.message)
    return state


def _sse(event: dict[str, object]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def main() -> None:
    response = chat(ChatRequest(message="피카츄 알려줘"))
    print(response.model_dump())


if __name__ == "__main__":
    main()
