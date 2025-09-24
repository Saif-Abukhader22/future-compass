# ---------- build frontend ----------
FROM node:20 AS webbuild
WORKDIR /web
# If your frontend folder is not Chatbot, change both lines below
COPY Chatbot/package*.json ./
RUN npm ci
COPY Chatbot/ ./
# Make client hit same-origin API
ENV VITE_API_BASE_URL=/api
RUN npm run build   # -> /web/dist

# ---------- runtime: python + nginx ----------
FROM python:3.11-slim
WORKDIR /app

# system deps for psycopg2 + nginx
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev nginx && \
    rm -rf /var/lib/apt/lists/*

# python deps (requirements lives in pyserver/)
COPY pyserver/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt gunicorn uvicorn

# backend code
COPY pyserver/ ./pyserver

# built frontend → nginx web root
COPY --from=webbuild /web/dist /var/www/html

# nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

ENV PORT=8080
EXPOSE 8080

# start backend then nginx (simple supervision)
CMD bash -lc '\
  gunicorn -k uvicorn.workers.UvicornWorker -w ${WORKERS:-3} -b 0.0.0.0:8000 pyserver.app.main:app & \
  nginx -g "daemon off;" \
'
