FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /workspace

# Copy dependency specification
COPY pyproject.toml /workspace/

# Install the application dependencies directly into the system python
RUN uv pip install --system -r pyproject.toml || uv pip install --system fastapi uvicorn sqlalchemy psycopg2-binary passlib bcrypt itsdangerous jinja2 python-multipart

# Copy the rest of the application
COPY ./app /workspace/app

# Run the API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
