FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy bindings
COPY uv.lock pyproject.toml /app/

# Install dependencies using uv
RUN uv sync --frozen --no-install-project

# Copy the rest of the application
COPY . /app/

# Make sure the environment is on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose port
EXPOSE 8001

# Command to run the application
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
