ARG NODE_IMAGE=node:20.11.1-slim
ARG PNPM_VERSION=8
ARG NODE_PLATFORM=linux/amd64

FROM --platform=${NODE_PLATFORM} ${NODE_IMAGE} as nodejs

WORKDIR /code

RUN npm i -g pnpm@${PNPM_VERSION}

COPY . .

RUN pnpm i
RUN pnpm run build
RUN tar -czvf frontend.tar.gz  monitor fta weixin apm trace external

CMD [ "echo", "前端构建完毕" ]
