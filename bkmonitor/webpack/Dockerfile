ARG NODE_IMAGE=node:20.11.1-slim
ARG PNPM_VERSION=8
ARG NODE_PLATFORM=linux/amd64
ARG TARGET_NAME=frontend.tar.gz

FROM --platform=${NODE_PLATFORM} ${NODE_IMAGE} as nodejs

ENV NODE_OPTIONS=--max_old_space_size=8000

WORKDIR /code

COPY . .

ENV NODE_ENV production

RUN npm i -g pnpm@${PNPM_VERSION} \
&& pnpm i \
&& pnpm run build \
&& tar -czvf ./${TARGET_NAME} monitor fta weixin apm trace external

CMD [ "echo", "前端构建完毕" ]