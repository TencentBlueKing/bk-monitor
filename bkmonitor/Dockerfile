FROM python:3.7-bullseye as python-base

# variables
ARG username=bkmonitor
ARG pypi_index_url=https://pypi.org/simple/
ARG replace_debian_source=false

# update debian source
RUN if [ ${replace_debian_source} ] ; then \
        echo "update debian source to tencent" && \
        rm -rf /etc/apt/sources.list && \
        echo "deb https://mirrors.tencent.com/debian/ bullseye main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb-src https://mirrors.tencent.com/debian/ bullseye main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb https://mirrors.tencent.com/debian/ bullseye-updates main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb-src https://mirrors.tencent.com/debian/ bullseye-updates main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb https://mirrors.tencent.com/debian/ bullseye-backports main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb-src https://mirrors.tencent.com/debian/ bullseye-backports main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb https://mirrors.tencent.com/debian-security/ bullseye-security main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb-src https://mirrors.tencent.com/debian-security/ bullseye-security main contrib non-free" >>/etc/apt/sources.list; \
    else \
        echo "don't need change debian source"; \
    fi

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
RUN apt-get update && apt-get install -y vim chromium wget strace graphviz tini


# build python packages
FROM python-base as python-builder

# install python packages
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=/app/requirements.txt \
    python -m venv /app/venv \
    && /app/venv/bin/pip install --upgrade pip \
    && /app/venv/bin/pip install -r /app/requirements.txt -i "${pypi_index_url}"



# build frontend
FROM node:20-bullseye-slim as node-builder

# pnpm
RUN npm install -g pnpm@9

WORKDIR /app

# build frontend
COPY ./webpack /app/webpack
RUN cd /app/webpack/ && pnpm i && npm run prod \
    && mkdir -p /app/dist && mv apm monitor fta weixin trace external /app/dist/



# final image
FROM python-base

# install vim and chromium
RUN groupadd -r ${username}  \
    && useradd -r -g ${username} ${username}  \
    && mkdir -p /data/ /app/ /home/${username} \
    && chown -R ${username}:${username} /data/ /app/ /home/${username}

# move code and python packages
COPY --chown=${username}:${username} . /app/code/
COPY --from=node-builder --chown=${username}:${username} /app/dist/ /app/code/static/
COPY --from=python-builder --chown=${username}:${username} /app/venv /app/venv

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
