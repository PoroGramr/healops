FROM node:22-alpine AS build
WORKDIR /src
COPY package*.json ./
RUN npm install
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
RUN npm run build
FROM nginx:1.27-alpine
COPY --from=build /src/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
