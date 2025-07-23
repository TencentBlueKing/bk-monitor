FROM python:3.11-bookworm AS python-base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# variables
ARG username=bkmonitor
ARG pypi_index_url=https://pypi.org/simple/

# update debian source
RUN cat <<EOF > /etc/apt/sources.list.d/debian.sources
Types: deb
# http://snapshot.debian.org/archive/debian/20250610T000000Z
URIs: http://mirrors.tencent.com/debian
Suites: bookworm bookworm-updates
Components: main
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg

Types: deb
# http://snapshot.debian.org/archive/debian-security/20250610T000000Z
URIs: http://mirrors.tencent.com/debian-security
Suites: bookworm-security
Components: main
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
EOF

# install chinese fonts
RUN --mount=type=cache,target=/app/fonts \
    if [ ! -f /app/fonts/SourceHanSansSC-VF.ttf ]; then \
        wget https://github.com/adobe-fonts/source-han-sans/raw/release/Variable/TTF/SourceHanSansSC-VF.ttf -O /app/fonts/SourceHanSansSC-VF.ttf; \
    fi \
    && if [ ! -f /app/fonts/SourceHanSerifSC-VF.ttf ]; then \
        wget https://github.com/adobe-fonts/source-han-serif/raw/release/Variable/TTF/SourceHanSerifSC-VF.ttf -O /app/fonts/SourceHanSerifSC-VF.ttf; \
    fi \
    && install -m644 /app/fonts/* /usr/share/fonts/truetype/

# install tools
RUN apt-get update && apt-get install -y --allow-unauthenticated vim chromium wget strace graphviz tini


# build python packages
FROM python-base AS python-builder

WORKDIR /app

# install python packages
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv venv venv --seed --link-mode=copy && . venv/bin/activate && uv sync --locked --no-install-project --no-dev --active

# build frontend
FROM node:20-bullseye-slim AS node-builder

# pnpm
RUN npm install -g pnpm@10

WORKDIR /app

# build frontend
COPY ./webpack /app/webpack
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
COPY --chown=${username}:${username} . /app/code/

ARG version
RUN echo ${version} > /app/code/VERSION && rm -r /app/code/webpack && cp /app/code/docs/api/monitor_v3.yaml /app/code/kernel_api/monitor_v3.yaml

# set user
USER ${username}

# set workdir
WORKDIR /app/code

# set python env
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

ENTRYPOINT ["/usr/bin/tini", "--"]

CMD python manage.py runserver 0.0.0.0:80
