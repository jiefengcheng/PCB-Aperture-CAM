# A Linux development/intake environment, NOT a qualified trimming runtime.
# See README.md before attempting the Mac-specific execution entry points.
ARG PYTHON_IMAGE=python:3.14.5-slim-bookworm
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /opt/pcb-cam
# ps is used by retained-job ownership checks when porting execution.
RUN apt-get update && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.lock.txt requirements-completion.txt ./
# Build-time temporary data stays in the container build layer.
RUN TMPDIR=/tmp python -m pip install --only-binary=:all: \
    -r requirements.lock.txt -r requirements-completion.txt
# Selective copies avoid client datasets, jobs, local environments and caches.
COPY src/ src/
COPY contracts/ contracts/
COPY assets/ assets/
COPY tools/ tools/
COPY baselines/large_copper_0.2.0/ baselines/large_copper_0.2.0/
COPY reproduction/large_copper_0.2.0/ reproduction/large_copper_0.2.0/
ENV TMPDIR=/work/tmp XDG_CACHE_HOME=/work/cache
CMD ["python", "-B", "tools/check_large_copper_baseline.py", "--parse"]
