FROM node:22-bookworm-slim

WORKDIR /srv/services/comun
COPY services/comun/package.json services/comun/package-lock.json ./
RUN npm ci --omit=dev

WORKDIR /srv/services/queries-service
COPY services/queries-service/package.json services/queries-service/package-lock.json ./
RUN npm ci --omit=dev

COPY services/comun/src /srv/services/comun/src
COPY services/comun/xsd /srv/services/comun/xsd
COPY services/queries-service/src /srv/services/queries-service/src

RUN chown -R node:node /srv
USER node
ENV NODE_ENV=production
EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=8 \
  CMD node -e "fetch('http://127.0.0.1:3000/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "src/server.js"]
