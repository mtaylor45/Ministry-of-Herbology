# SvelteKit PWA, built then served by the Node adapter. Workstream B.
FROM node:22-slim AS build
WORKDIR /srv/web
COPY web/package.json web/package-lock.json* ./
RUN npm ci || npm install
COPY web/ ./
RUN npm run build

FROM node:22-slim AS runtime
ENV NODE_ENV=production
WORKDIR /srv/web
RUN adduser --system --group --no-create-home herbology
COPY --from=build /srv/web/build ./build
COPY --from=build /srv/web/package.json ./
COPY --from=build /srv/web/node_modules ./node_modules
USER herbology
EXPOSE 3000
CMD ["node", "build/index.js"]
