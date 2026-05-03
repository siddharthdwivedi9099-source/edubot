# syntax=docker/dockerfile:1.6
# ----------------------------------------------------------------------------
# EduBot frontend image — Vite build, served by nginx, /api reverse-proxied
# to the backend service.
# ----------------------------------------------------------------------------

# ---- 1. Build stage --------------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
# VITE_API_BASE_URL is baked at build time. Default to /api so nginx proxies it.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ---- 2. Runtime stage ------------------------------------------------------
FROM nginx:1.27-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
