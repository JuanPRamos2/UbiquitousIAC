# organizational-service — publicado en 8117. Dentro del contenedor escucha en 8000,
# igual que el resto, para que el compose y el monitoreo lo encuentren. (Integrante 2: Ricardo)
FROM node:20-alpine

RUN addgroup -S servicio && adduser -S servicio -G servicio

WORKDIR /srv
COPY comun-node/package.json ./comun-node/package.json
COPY organizational-service/package.json ./organizational-service/package.json

WORKDIR /srv/comun-node
RUN npm install --omit=dev --no-audit --no-fund

WORKDIR /srv/organizational-service
RUN npm install --omit=dev --no-audit --no-fund

COPY comun-node /srv/comun-node
COPY organizational-service/src /srv/organizational-service/src

ENV NODE_ENV=production \
    NOMBRE_SERVICIO=organizational-service \
    PUERTO=8000
EXPOSE 8000

USER servicio

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:8000/health/live').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "src/server.js"]
