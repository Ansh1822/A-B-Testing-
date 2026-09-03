# A/B Testing Platform (FastAPI)

A lightweight, self-contained A/B testing service built with **FastAPI** and **SQLAlchemy**. It lets you spin up experiments, deterministically bucket users into variants, log conversion events, and get statistical-significance results (two-proportion z-test) via a REST API.

## Features

- **Create experiments** with any number of variants and custom traffic-weight splits (e.g. 50/50, 90/10).
- **Deterministic bucketing** — users are hashed (SHA-256 of `experiment:user_id`) into a variant, so the same user always sees the same variant on repeat visits (sticky assignment), with no need to store a random seed.
- **Event tracking** — log conversions (or any custom event type) tied to a user's assigned variant.
- **Statistical significance** — a two-proportion z-test (normal approximation) computes the z-score, p-value, and declares a winner at the 95% confidence level once enough data has been collected.
- **Auto-generated docs** — interactive Swagger UI at `/docs` (built into FastAPI).

## Tech stack

FastAPI · SQLAlchemy · SQLite (swappable for Postgres) · Pydantic · Uvicorn

## Project structure

```
ab-testing-platform/
├── app/
│   ├── main.py       # API routes
│   ├── models.py     # SQLAlchemy models (Experiment, Variant, Assignment, Event)
│   ├── schemas.py     # Pydantic request/response schemas
│   ├── stats.py       # Two-proportion z-test for significance testing
│   └── database.py    # DB engine/session setup
├── requirements.txt
└── README.md
```

## Running it

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000/docs` for the interactive API.

## Example flow

```bash
# 1. Create an experiment with two variants
curl -X POST http://127.0.0.1:8000/experiments \
  -H "Content-Type: application/json" \
  -d '{"name": "checkout_button_color", "description": "Red vs green CTA"}'

# 2. Assign a user to a variant (sticky — same user always gets the same variant)
curl -X POST http://127.0.0.1:8000/experiments/checkout_button_color/assign \
  -H "Content-Type: application/json" -d '{"user_id": "user_123"}'

# 3. Log a conversion for that user
curl -X POST http://127.0.0.1:8000/experiments/checkout_button_color/events \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_123", "event_type": "conversion"}'

# 4. Get results + statistical significance
curl http://127.0.0.1:8000/experiments/checkout_button_color/results
```

Sample results response:

```json
{
  "experiment": "checkout_button_color",
  "variants": [
    {"variant": "control", "users_assigned": 109, "conversions": 19, "conversion_rate": 0.1743},
    {"variant": "treatment", "users_assigned": 91, "conversions": 40, "conversion_rate": 0.4396}
  ],
  "z_score": 4.0961,
  "p_value": 0.0,
  "significant_at_95": true,
  "winner": "treatment"
}
```

## Deploying

### ⚠️ Use Postgres in production, not SQLite

SQLite writes to a local file. On serverless platforms (Vercel, AWS Lambda) the
filesystem is ephemeral or read-only, so data written in one request may not be
there on the next — experiments/assignments can silently disappear. For any
real deployment, set the `DATABASE_URL` environment variable to a hosted
Postgres connection string. Free options: [Neon](https://neon.tech) or
[Supabase](https://supabase.com). Locally, leave `DATABASE_URL` unset and it
falls back to SQLite automatically.

```
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

### Deploy to Vercel

This repo includes `vercel.json` and `api/index.py`, which point Vercel at the
FastAPI app.

1. Push the repo to GitHub.
2. On [vercel.com](https://vercel.com), import the repo as a new project.
3. In the project's Environment Variables settings, add `DATABASE_URL`
   pointing to a Postgres instance (see above — don't skip this).
4. Deploy. Your API will be live at `https://<project>.vercel.app`, docs at
   `/docs`.

### Deploy to Render or Railway (recommended if you want a simpler, stateful host)

Both platforms read the included `Procfile` automatically.

1. Push the repo to GitHub.
2. Create a new Web Service on [Render](https://render.com) or
   [Railway](https://railway.app) and point it at the repo.
3. Set the `DATABASE_URL` environment variable (both platforms offer a
   one-click managed Postgres add-on).
4. Deploy — build command `pip install -r requirements.txt`, start command
   is picked up from the `Procfile`.

## Possible extensions

- Swap SQLite for Postgres for production use
- Add a Bayesian significance model alongside the frequentist z-test
- Add an admin dashboard (e.g. Streamlit or a React frontend) to visualize results
- Add authentication for the experiment-management endpoints
