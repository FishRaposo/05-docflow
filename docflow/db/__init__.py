from docflow.db.session import get_session, init_db, async_session, engine, Base

__all__ = ["get_session", "init_db", "async_session", "engine", "Base"]
clarativeBase

from docflow.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""

    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session for dependency injection."""
    async with async_session() as session:
        yield session


async def init_db() -> None:
    """Initialize database schema.

    Creates all tables defined in the models. In production, use Alembic migrations instead.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
