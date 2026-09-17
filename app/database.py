from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import QueuePool

from app.config import settings

# Database URL from settings (.env)
database_url = settings.database_url

# Configure engine and connect_args based on database dialect
if database_url.startswith("sqlite"):
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )
else:
    # PostgreSQL settings
    connect_args = {
        "sslmode": "prefer",
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
        "application_name": "agenda_atende",
    }
    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_pre_ping=True,
        pool_recycle=120,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        connect_args=connect_args,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()