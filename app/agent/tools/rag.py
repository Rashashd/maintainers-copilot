from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag import service as rag_service


async def run(args: dict, session: AsyncSession) -> str:
    answer, contexts = await rag_service.answer(
        query=args["query"],
        session=session,
    )
    return answer
