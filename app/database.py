import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# In production, set DATABASE_URL to a Postgres connection string
# (e.g. from Neon, Supabase, or Render Postgres). Falls back to local
# SQLite for development. SQLite is NOT safe on serverless platforms
# like Vercel — the filesystem is ephemeral/read-only, so writes won't
# persist between requests.
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./ab_testing.db")

# Some hosts (e.g. Heroku-style) provide "postgres://" — SQLAlchemy needs "postgresql://"
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
