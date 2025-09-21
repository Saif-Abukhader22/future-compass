# --- build frontend ---
FROM node:20 AS webbuild
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_BASE_URL=/api
RUN npm run build   # outputs /web/dist

# --- runtime: backend + nginx ---
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev nginx && \
    rm -rf /var/lib/apt/lists/*

# python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn uvicorn

# app code
COPY backend/ ./backend
# static site served by Nginx
COPY --from=webbuild /web/dist /var/www/html

# Nginx config: serve SPA and proxy /api to FastAPI on :8000
COPY nginx.conf /etc/nginx/conf.d/default.conf

ENV PORT=8080
EXPOSE 8080

# start both: backend (gunicorn) and nginx (simple sh supervisor)
CMD bash -lc '\
  gunicorn -k uvicorn.workers.UvicornWorker -w ${WORKERS:-3} -b 0.0.0.0:8000 backend.app.main:app & \
  nginx -g "daemon off;" \
'
