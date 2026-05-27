# Authentication Anomaly Detection Backend

## Step to follow

From inside backend folder

1. pip install uv
2. uv venv
3. .venv\scripts\activate
4. uv sync
5. make .env file(place your postgres url and redis url)
6. Run command "alembic upgrade head"
7. Run command "uvicorn main:app --reload"
