from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class VariantCreate(BaseModel):
    name: str
    traffic_weight: float = 0.5


class ExperimentCreate(BaseModel):
    name: str
    description: str = ""
    variants: List[VariantCreate] = Field(
        default_factory=lambda: [
            VariantCreate(name="control", traffic_weight=0.5),
            VariantCreate(name="treatment", traffic_weight=0.5),
        ]
    )


class VariantOut(BaseModel):
    id: int
    name: str
    traffic_weight: float

    class Config:
        from_attributes = True


class ExperimentOut(BaseModel):
    id: int
    name: str
    description: str
    status: str
    created_at: datetime
    variants: List[VariantOut]

    class Config:
        from_attributes = True


class AssignRequest(BaseModel):
    user_id: str


class AssignResponse(BaseModel):
    experiment: str
    variant: str
    user_id: str


class EventRequest(BaseModel):
    user_id: str
    event_type: str = "conversion"
    value: float = 1.0


class VariantResult(BaseModel):
    variant: str
    users_assigned: int
    conversions: int
    conversion_rate: float
    avg_value: float


class ExperimentResults(BaseModel):
    experiment: str
    status: str
    variants: List[VariantResult]
    p_value: Optional[float] = None
    z_score: Optional[float] = None
    significant_at_95: Optional[bool] = None
    winner: Optional[str] = None
    note: Optional[str] = None
