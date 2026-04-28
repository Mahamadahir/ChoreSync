FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# Bake production API URL at build time
ARG VITE_API_BASE_URL=https://choresync.mahamadahir.com
ARG VITE_GOOGLE_CLIENT_ID
ARG VITE_MSAL_CLIENT_ID
ARG VITE_MSAL_AUTHORITY

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID \
    VITE_MSAL_CLIENT_ID=$VITE_MSAL_CLIENT_ID \
    VITE_MSAL_AUTHORITY=$VITE_MSAL_AUTHORITY

RUN npm run build

# --- runtime ---
FROM nginxinc/nginx-unprivileged:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080
