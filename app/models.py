from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey, DateTime, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from .database import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, default="")
    status = Column(String, default="active")  # active | paused | completed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    variants = relationship("Variant", back_populates="experiment", cascade="all, delete-orphan")


class Variant(Base):
    __tablename__ = "variants"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    name = Column(String, nullable=False)  # e.g. "control", "treatment"
    traffic_weight = Column(Float, default=0.5)  # relative allocation weight

    experiment = relationship("Experiment", back_populates="variants")

    __table_args__ = (UniqueConstraint("experiment_id", "name", name="uix_experiment_variant"),)


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("variants.id"), nullable=False)
    user_id = Column(String, index=True, nullable=False)
    assigned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("experiment_id", "user_id", name="uix_experiment_user"),)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("variants.id"), nullable=False)
    user_id = Column(String, index=True, nullable=False)
    event_type = Column(String, default="conversion")  # conversion | click | custom
    value = Column(Float, default=1.0)  # e.g. revenue amount, or 1 for a simple conversion
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
