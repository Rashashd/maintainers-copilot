from sqlalchemy.ext.asyncio import AsyncSession

from app.services import rag as rag_service


async def run(args: dict, session: AsyncSession) -> str:
    answer, contexts = await rag_service.answer(
        query=args["query"],
        session=session,
    )
    return answer
