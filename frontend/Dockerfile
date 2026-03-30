FROM node:18-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

ARG REACT_APP_API_URL=
ENV REACT_APP_API_URL=$REACT_APP_API_URL

RUN npm run build

RUN npm install -g serve

EXPOSE 3000

CMD ["serve", "-s", "build", "-l", "3000"]
