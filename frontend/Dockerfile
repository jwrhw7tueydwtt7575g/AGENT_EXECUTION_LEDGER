# =============================================================
# Frontend Dockerfile — Agent Execution Ledger
# Multi-stage: Node builder → nginx static serve
# =============================================================

# --- Stage 1: Builder ---
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files first (better layer caching)
COPY package.json package-lock.json* ./

RUN npm ci --prefer-offline

# Copy source and build
COPY . .

# Pass build-time env vars (override during docker build via --build-arg)
ARG VITE_API_BASE=http://localhost:8000
ARG VITE_WS_URL=ws://localhost:8000/ws/live
ARG VITE_APP_NAME="Agent Execution Ledger"
ARG VITE_APP_VERSION=1.0.0
ARG VITE_ENABLE_LIVE_FEED=true

ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_WS_URL=$VITE_WS_URL
ENV VITE_APP_NAME=$VITE_APP_NAME
ENV VITE_APP_VERSION=$VITE_APP_VERSION
ENV VITE_ENABLE_LIVE_FEED=$VITE_ENABLE_LIVE_FEED

RUN npm run build

# --- Stage 2: Serve with nginx ---
FROM nginx:1.27-alpine AS runtime

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Custom nginx config for SPA routing
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx.conf: serve SPA, proxy /api/* and /ws/* to backend
RUN cat > /etc/nginx/conf.d/default.conf <<'EOF'
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to backend
    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket proxy
    location /ws/ {
        proxy_pass http://backend:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
    }

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;
}
EOF

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
