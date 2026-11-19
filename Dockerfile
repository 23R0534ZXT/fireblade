# Fireblade Host — the Windows edition's core, served over HTTP, without Qt.
# The cases live in a mounted folder and keep the desktop's on-disk format.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    FIREBLADE_CASES=/data/cases

WORKDIR /app

# The core requirements only: no PySide6, no Windows-only parser.
COPY requirements-core.txt ./
RUN pip install --no-cache-dir -r requirements-core.txt

COPY pyproject.toml README.md ./
# Only what the service imports. plugin_host (129 MB) and ui (Qt) stay out.
COPY src/fireblade/__init__.py ./src/fireblade/
COPY src/fireblade/core ./src/fireblade/core
COPY src/fireblade/runtime ./src/fireblade/runtime
COPY src/fireblade/web ./src/fireblade/web

RUN useradd --create-home --uid 10001 fireblade \
    && mkdir -p /data/cases \
    && chown -R fireblade:fireblade /data
USER fireblade

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=4).status==200 else 1)"

# Opening a case and counting its rows is the smoke test of this image:
#   docker run --rm -v /srv/fireblade/cases:/data/cases fireblade:host \
#       python -m fireblade.web count
CMD ["python", "-m", "fireblade.web", "serve", "--root", "/data/cases", "--host", "0.0.0.0", "--port", "8080"]
