import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Load the database URL from environment variables for security
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/content_analyzer")

# The engine is the entry point to the database
engine = create_engine(DATABASE_URL)

# The SessionLocal class is a factory for creating new database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our ORM models
Base = declarative_base()