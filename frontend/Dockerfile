# ══════════════════════════════════════════════════════════
# Astra Frontend – Multi-Stage Dockerfile
# ══════════════════════════════════════════════════════════

# ── Build-Stage ─────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Build-Time Umgebungsvariablen
ARG VITE_API_BASE_URL=/api
ARG VITE_WS_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_WS_BASE_URL=$VITE_WS_BASE_URL

RUN npm run build

# ── Runtime-Stage (Nginx) ──────────────────────────────
FROM nginx:1.27-alpine

# Nginx-Konfiguration fuer SPA
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Build-Artefakte kopieren
COPY --from=builder /build/dist /usr/share/nginx/html

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

EXPOSE 80
