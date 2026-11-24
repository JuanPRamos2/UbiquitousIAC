# main-process-service — Integrante 2
#
# El contexto de construccion es apps/microservicios (no la carpeta del
# servicio), igual que en los servicios en Python, porque hay que copiar
# tambien la biblioteca compartida comun-node.
FROM node:20-alpine

RUN addgroup -S servicio && adduser -S servicio -G servicio

WORKDIR /srv
COPY comun-node/package.json ./comun-node/package.json
COPY main-process-service/package.json ./main-process-service/package.json

WORKDIR /srv/comun-node
RUN npm install --omit=dev --no-audit --no-fund

WORKDIR /srv/main-process-service
RUN npm install --omit=dev --no-audit --no-fund

COPY comun-node /srv/comun-node
COPY main-process-service/src /srv/main-process-service/src
COPY main-process-service/openapi.yaml /srv/main-process-service/openapi.yaml

ENV NODE_ENV=production \
    NOMBRE_SERVICIO=main-process-service \
    PUERTO=8000
EXPOSE 8000

USER servicio

# La sonda del contenedor usa /health/live y NO /health/ready: un servicio
# cuya base de datos esta caida sigue estando vivo y no debe reiniciarse en
# bucle; lo que no debe es recibir trafico, y de eso se encarga /ready.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:8000/health/live').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "src/server.js"]
