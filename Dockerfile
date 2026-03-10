FROM node:18

WORKDIR /app

COPY app /app

RUN npm init -y
RUN npm install express

EXPOSE 3000

CMD ["node", "index.js"]