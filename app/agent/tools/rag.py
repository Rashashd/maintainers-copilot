from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.tracing import observe
from app.services import rag as rag_service


@observe(name="agent.tool.search_knowledge_base")
async def run(args: dict, session: AsyncSession) -> str:
    answer, contexts = await rag_service.answer(
        query=args["query"],
        session=session,
    )
    return answer
