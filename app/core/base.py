from sqlalchemy.orm import declarative_base

# This is the single source of truth for the SQLAlchemy declarative base.
# Models will import this, and the database initialization will use it.
Base = declarative_base()
