FROM node:20-alpine
WORKDIR /srv
COPY services/catalog-service/package.json services/catalog-service/
WORKDIR /srv/services/catalog-service
RUN npm install --omit=dev uuid && cp -a node_modules /srv/node_modules
WORKDIR /srv
COPY src /srv/src
COPY services/catalog-service /srv/services/catalog-service
WORKDIR /srv/services/catalog-service
ENV NODE_ENV=production PORT=3002
EXPOSE 3002
CMD ["node", "src/server.js"]
