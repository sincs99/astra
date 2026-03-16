# ══════════════════════════════════════════════════════════
# Astra Backend – Multi-Stage Dockerfile
# ══════════════════════════════════════════════════════════

# ── Build-Stage ─────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime-Stage ───────────────────────────────────────
FROM python:3.12-slim

# Sicherheit: Nicht als root laufen
RUN groupadd -r astra && useradd -r -g astra -d /app -s /sbin/nologin astra

WORKDIR /app

# Python-Pakete aus Builder kopieren
COPY --from=builder /install /usr/local

# Anwendungscode kopieren
COPY . .

# Entrypoint ausfuehrbar machen
RUN chmod +x entrypoint.sh

# Eigentuemer setzen
RUN chown -R astra:astra /app

# Nicht-Root-User verwenden
USER astra

# Health-Check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["serve"]
