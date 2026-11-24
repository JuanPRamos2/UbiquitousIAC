FROM node:20-alpine AS base

WORKDIR /app

COPY package.json ./
# En entorno local o container se instalan las dependencias requeridas
RUN npm install --omit=dev

COPY src/ ./src/

EXPOSE 3002

ENV NODE_ENV=production \
    PORT=3002

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3002/health || exit 1

CMD ["node", "src/server.js"]
