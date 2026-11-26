FROM node:22-alpine AS build
WORKDIR /ui
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_LOCAL_CSV=false
ENV VITE_LOCAL_CSV=$VITE_LOCAL_CSV
RUN npm run build

FROM caddy:2.10-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /ui/dist /srv
EXPOSE 8080
