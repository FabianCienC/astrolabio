# syntax=docker/dockerfile:1
# astrolabio-web. Built from the repo root (the types come from ../contract):
#   docker build -f web/Dockerfile .
# Base images are pinned by digest (Dependabot bumps them) and `npm ci` checks
# every package against the integrity hashes in package-lock.json.

FROM node:24-alpine@sha256:06d7adf3e0ef61a13f1d28682726366f97a15aa1888c934d3ecec86c33918b53 AS build
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY contract /app/contract
COPY web ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03
COPY web/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY web/nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/web/dist /usr/share/nginx/html
EXPOSE 8080
