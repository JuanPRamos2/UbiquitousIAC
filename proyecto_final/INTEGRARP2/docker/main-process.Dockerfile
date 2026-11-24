FROM node:20-alpine
WORKDIR /srv
COPY services/main-process-service/package.json services/main-process-service/
WORKDIR /srv/services/main-process-service
RUN npm install --omit=dev && cp -a node_modules /srv/node_modules
WORKDIR /srv
COPY src /srv/src
COPY services/main-process-service /srv/services/main-process-service
WORKDIR /srv/services/main-process-service
ENV NODE_ENV=production PORT=3003
EXPOSE 3003
CMD ["node", "src/server.js"]
