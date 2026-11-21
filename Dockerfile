FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.source="https://github.com/walmfml88886666/go2-rule-based-inspection-navigation" \
      org.opencontainers.image.description="Go2 Patrol offline route audit and synthetic grid simulation"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1
WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --only-binary=:all: -r requirements.txt
COPY tools/ ./tools/
COPY examples/ ./examples/
COPY tests/ ./tests/

USER 65532:65532
CMD ["python", "-m", "examples.offline_audit"]
