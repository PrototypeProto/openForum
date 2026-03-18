FROM node:current-trixie-slim

WORKDIR /frontend
COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173
