# syntax=docker/dockerfile:1
FROM node:22-slim AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# Inlined into the browser bundle at build time, so it must be the public URL.
ARG NEXT_PUBLIC_API_BASE=http://localhost:8000
ARG NEXT_PUBLIC_DOCS_URL=https://zarreh.ai/clinical_care_navigator/
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE \
    NEXT_PUBLIC_DOCS_URL=$NEXT_PUBLIC_DOCS_URL \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-slim AS runtime

WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

USER node

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

EXPOSE 3000
CMD ["node", "server.js"]
