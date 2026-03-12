# Run: python app/api/routes/chat.py
from fastapi import APIRouter

from app.agents.pokedex_agent.graph import PokedexAgentGraph
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
        citations=[],
    )


def main() -> None:
    response = chat(ChatRequest(message="피카츄 알려줘"))
    print(response.model_dump())


if __name__ == "__main__":
    main()
