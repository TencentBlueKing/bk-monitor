FROM node:20.11.1-slim as nodejs
WORKDIR /code
COPY . .
RUN npm i -g pnpm \
&& pnpm i \
&& pnpm run build
CMD [ "echo", "前端构建完毕" ]