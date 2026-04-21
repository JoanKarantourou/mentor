from collections.abc import AsyncGenerator, Callable

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.ENVIRONMENT == "dev")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


def make_session_factory(eng: AsyncEngine) -> Callable[[], AsyncSession]:
    def factory() -> AsyncSession:
        return AsyncSession(eng, expire_on_commit=False)

    return factory
