FROM node:current-trixie-slim

WORKDIR /frontend
COPY package*.json ./
RUN npm install

COPY . .
# RUN npm install vite react react-dom react-router-dom

EXPOSE 5173

# CMD ["bash"]