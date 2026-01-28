ARG PYTHON_BASE_IMAGE=tencentos/tencentos4-minimal:4.4-v20250922

FROM ${PYTHON_BASE_IMAGE} AS python-base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# variables
ARG username=bkmonitor
ARG pypi_index_url=https://pypi.org/simple/

# install tools
RUN dnf install -y vim wget strace graphviz tini mysql-libs https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm && dnf clean all

# install chinese fonts
RUN --mount=type=cache,target=/app/fonts \
    if [ ! -f /app/fonts/SourceHanSansSC-VF.ttf ]; then \
        wget https://github.com/adobe-fonts/source-han-sans/raw/release/Variable/TTF/SourceHanSansSC-VF.ttf -O /app/fonts/SourceHanSansSC-VF.ttf; \
    fi \
    && if [ ! -f /app/fonts/SourceHanSerifSC-VF.ttf ]; then \
        wget https://github.com/adobe-fonts/source-han-serif/raw/release/Variable/TTF/SourceHanSerifSC-VF.ttf -O /app/fonts/SourceHanSerifSC-VF.ttf; \
    fi \
    && mkdir -p /usr/share/fonts/truetype/ \
    && install -m644 /app/fonts/* /usr/share/fonts/truetype/

# build python packages
FROM python-base AS python-builder

WORKDIR /app

RUN dnf install -y gcc python3-devel mysql-devel

# install python packages
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=bkmonitor/pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=bkmonitor/uv.lock,target=uv.lock \
    --mount=type=bind,source=bk-monitor-base,target=/bk-monitor-base \
    uv venv venv --seed --link-mode=copy && . venv/bin/activate && uv sync --locked --no-install-project --no-dev --active

# build frontend
FROM node:20-bullseye-slim AS node-builder

# pnpm
RUN npm install -g pnpm@10

WORKDIR /app

# build frontend
COPY bkmonitor/webpack /app/webpack
RUN cd /app/webpack/ && npm run prod \
    && mkdir -p /app/dist && mv apm monitor fta weixin trace external /app/dist/

# final image
FROM python-base

# install vim and chromium
RUN groupadd -r ${username}  \
    && useradd -r -g ${username} ${username}  \
    && mkdir -p /data/ /app/ /home/${username} \
    && chown -R ${username}:${username} /data/ /app/ /home/${username}

# move code and python packages
COPY --from=python-builder --chown=${username}:${username} /app/venv /app/venv
COPY --from=node-builder --chown=${username}:${username} /app/dist/ /app/code/static/
COPY --chown=${username}:${username} bkmonitor/ /app/code/
COPY --chown=${username}:${username} bk-monitor-base/ /bk-monitor-base/

ARG version
RUN echo ${version} > /app/code/VERSION && rm -r /app/code/webpack && cp /app/code/docs/api/monitor_v3.yaml /app/code/kernel_api/monitor_v3.yaml

# set user
USER ${username}

# set workdir
WORKDIR /app/code

# set locale for UTF-8 support
ENV LANG=en_US.utf8
ENV LC_ALL=en_US.utf8

# set python env
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

ENTRYPOINT ["/usr/bin/tini", "--"]

CMD python manage.py runserver 0.0.0.0:80
