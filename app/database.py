import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import QueuePool

# Database URL from environment
database_url = os.environ.get("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/agenda_atende")

# Check if using Neon (SSL required) or local PostgreSQL
is_neon = "neon.tech" in os.environ.get("DATABASE_URL", "")

# SSL and connection arguments for PostgreSQL
connect_args = {}

if "neon.tech" in os.environ.get("DATABASE_URL", ""):
    # Neon requires SSL and specific settings - aggressive keepalive for Neon
    connect_args = {
        "sslmode": "require",
        "channel_binding": "require",
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 10,
        "keepalives_interval": 5,
        "keepalives_count": 3,
        "application_name": "agenda_atende",
        "tcp_user_timeout": 10000,
    }
else:
    # Local PostgreSQL settings
    connect_args = {
        "sslmode": "prefer",
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
        "application_name": "agenda_atende",
    }

# Engine configuration with robust connection pooling and SSL handling
engine = create_engine(
    database_url,
    poolclass=QueuePool,
    pool_pre_ping=True,           # CRITICAL: validates connections before use
    pool_recycle=120,             # Recycle connections every 2 minutes
    pool_size=10,                 # Base pool size
    max_overflow=20,              # Allow up to 20 additional connections
    pool_timeout=30,              # Timeout for getting connection from pool
    connect_args=connect_args,    # SSL and keepalive settings
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