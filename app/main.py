import hashlib
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func

from . import models, schemas
from .database import engine, get_db
from .stats import two_proportion_z_test

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="A/B Testing Platform",
    description="A lightweight A/B testing service: create experiments, "
    "deterministically bucket users into variants, log conversion events, "
    "and compute statistical significance between variants.",
    version="1.0.0",
)

# Allow calls from any frontend (loosen/tighten as needed for your use case)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "A/B Testing Platform",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


# ---------- Experiments ----------

@app.post("/experiments", response_model=schemas.ExperimentOut)
def create_experiment(payload: schemas.ExperimentCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Experiment).filter_by(name=payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Experiment name already exists")

    experiment = models.Experiment(name=payload.name, description=payload.description)
    db.add(experiment)
    db.flush()  # get experiment.id before adding variants

    for v in payload.variants:
        db.add(models.Variant(experiment_id=experiment.id, name=v.name, traffic_weight=v.traffic_weight))

    db.commit()
    db.refresh(experiment)
    return experiment


@app.get("/experiments", response_model=List[schemas.ExperimentOut])
def list_experiments(db: Session = Depends(get_db)):
    return db.query(models.Experiment).all()


@app.get("/experiments/{name}", response_model=schemas.ExperimentOut)
def get_experiment(name: str, db: Session = Depends(get_db)):
    experiment = db.query(models.Experiment).filter_by(name=name).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment


# ---------- Assignment (bucketing) ----------

def _deterministic_bucket(user_id: str, experiment_name: str, variants: List[models.Variant]) -> models.Variant:
    """
    Hash (user_id + experiment_name) to a float in [0, 1) so the same user
    always lands in the same variant for a given experiment, then map that
    float onto the variants' traffic weights.
    """
    digest = hashlib.sha256(f"{experiment_name}:{user_id}".encode()).hexdigest()
    bucket = int(digest, 16) / (16 ** len(digest))  # -> [0, 1)

    total_weight = sum(v.traffic_weight for v in variants) or 1.0
    cumulative = 0.0
    for v in variants:
        cumulative += v.traffic_weight / total_weight
        if bucket < cumulative:
            return v
    return variants[-1]


@app.post("/experiments/{name}/assign", response_model=schemas.AssignResponse)
def assign_variant(name: str, payload: schemas.AssignRequest, db: Session = Depends(get_db)):
    experiment = db.query(models.Experiment).filter_by(name=name).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if experiment.status != "active":
        raise HTTPException(status_code=400, detail=f"Experiment is {experiment.status}")

    # Return existing assignment if this user was already bucketed (sticky assignment)
    existing = (
        db.query(models.Assignment)
        .filter_by(experiment_id=experiment.id, user_id=payload.user_id)
        .first()
    )
    if existing:
        variant = db.query(models.Variant).get(existing.variant_id)
        return schemas.AssignResponse(experiment=name, variant=variant.name, user_id=payload.user_id)

    variant = _deterministic_bucket(payload.user_id, experiment.name, experiment.variants)
    db.add(models.Assignment(experiment_id=experiment.id, variant_id=variant.id, user_id=payload.user_id))
    db.commit()

    return schemas.AssignResponse(experiment=name, variant=variant.name, user_id=payload.user_id)


# ---------- Events ----------

@app.post("/experiments/{name}/events")
def log_event(name: str, payload: schemas.EventRequest, db: Session = Depends(get_db)):
    experiment = db.query(models.Experiment).filter_by(name=name).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    assignment = (
        db.query(models.Assignment)
        .filter_by(experiment_id=experiment.id, user_id=payload.user_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=400, detail="User has not been assigned a variant yet")

    db.add(models.Event(
        experiment_id=experiment.id,
        variant_id=assignment.variant_id,
        user_id=payload.user_id,
        event_type=payload.event_type,
        value=payload.value,
    ))
    db.commit()
    return {"status": "logged"}


# ---------- Results / significance ----------

@app.get("/experiments/{name}/results", response_model=schemas.ExperimentResults)
def get_results(name: str, db: Session = Depends(get_db)):
    experiment = db.query(models.Experiment).filter_by(name=name).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    variant_results = []
    per_variant_stats = {}

    for variant in experiment.variants:
        users_assigned = (
            db.query(func.count(models.Assignment.id))
            .filter_by(experiment_id=experiment.id, variant_id=variant.id)
            .scalar()
        )
        conversions = (
            db.query(func.count(func.distinct(models.Event.user_id)))
            .filter_by(experiment_id=experiment.id, variant_id=variant.id, event_type="conversion")
            .scalar()
        )
        avg_value = (
            db.query(func.avg(models.Event.value))
            .filter_by(experiment_id=experiment.id, variant_id=variant.id)
            .scalar()
        ) or 0.0

        conversion_rate = (conversions / users_assigned) if users_assigned else 0.0
        per_variant_stats[variant.name] = (conversions, users_assigned)

        variant_results.append(schemas.VariantResult(
            variant=variant.name,
            users_assigned=users_assigned,
            conversions=conversions,
            conversion_rate=round(conversion_rate, 4),
            avg_value=round(avg_value, 2),
        ))

    result = schemas.ExperimentResults(
        experiment=name, status=experiment.status, variants=variant_results
    )

    # Significance test only when there are exactly 2 variants with data
    if len(experiment.variants) == 2:
        names = [v.name for v in experiment.variants]
        conv_a, n_a = per_variant_stats[names[0]]
        conv_b, n_b = per_variant_stats[names[1]]
        z, p = two_proportion_z_test(conv_a, n_a, conv_b, n_b)

        if z is not None:
            result.z_score = round(z, 4)
            result.p_value = round(p, 4)
            result.significant_at_95 = p < 0.05
            if result.significant_at_95:
                rate_a = conv_a / n_a if n_a else 0
                rate_b = conv_b / n_b if n_b else 0
                result.winner = names[1] if rate_b > rate_a else names[0]
        else:
            result.note = "Not enough data to compute significance yet."
    else:
        result.note = "Significance testing currently supports exactly 2 variants."

    return result
