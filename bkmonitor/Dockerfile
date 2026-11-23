ARG PYTHON_BASE_IMAGE=tencentos/tencentos4-minimal:4.4-v20250922

FROM ${PYTHON_BASE_IMAGE} AS python-base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# variables
ARG username=bkmonitor
ARG pypi_index_url=https://pypi.org/simple/

# install tools
# TSSA-2026:1230 backports the Brotli decoder fix without changing its upstream version.
RUN dnf install -y vim wget strace graphviz tini mysql-libs \
    libbrotli-1.1.0-4.tl4.2 freetype libjpeg-turbo zlib libtiff lcms2 libwebp openjpeg2 libraqm libxcb \
    https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm && dnf clean all

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

RUN dnf install -y gcc python3-devel mysql-devel pkgconf-pkg-config \
    freetype-devel libjpeg-turbo-devel zlib-devel libtiff-devel lcms2-devel \
    libwebp-devel openjpeg2-devel libraqm-devel libxcb-devel

# install python packages
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=bkmonitor/pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=bkmonitor/uv.lock,target=uv.lock \
    --mount=type=bind,source=bk-monitor-base,target=/bk-monitor-base \
    uv venv venv --seed --link-mode=copy && . venv/bin/activate \
    && uv sync --locked --no-install-project --no-dev --active \
        --no-binary-package pillow --config-settings-package pillow:freetype=enable

# Optional private AI agent runtime. The default build (false) only runs uv sync --locked
# and needs no extra build arguments, secrets, or pipeline changes.
ARG pypi_index_url=https://pypi.org/simple/
ARG AI_AGENT_HERMES_ENABLED=false
ARG AI_AGENT_HERMES_PACKAGES="bkai-hermes-core==0.8.2.dev1 bkai-otel-hermes==1.3.0"
ARG AI_AGENT_PIP_EXTRA_INDEX_URL=""
RUN --mount=type=bind,source=bkmonitor/pyproject.toml,target=/run/monitor-pyproject.toml \
    --mount=type=bind,source=bkmonitor/scripts,target=/run/monitor-scripts \
    --mount=type=secret,id=python_package_config \
    --mount=type=secret,id=python_package_netrc,target=/root/.netrc \
    case "${AI_AGENT_HERMES_ENABLED}" in \
        true) /app/venv/bin/python /run/monitor-scripts/install_ai_agent_runtime.py \
            && /app/venv/bin/python -m pip check \
            && /app/venv/bin/python /run/monitor-scripts/check_ai_agent_runtime.py --required ;; \
        false) ;; \
        *) echo 'AI_AGENT_HERMES_ENABLED must be true or false' >&2; exit 1 ;; \
    esac

# build frontend
FROM node:24.22.2-bookworm-slim AS node-builder

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
COPY --chown=${username}:${username} ai_agent/ /app/code/ai_agent/
COPY --chown=${username}:${username} iam_engine/ /app/iam_engine/
COPY --chown=${username}:${username} bk-monitor-base/ /bk-monitor-base/

# Verify the copied environment against the final image's libraries and fonts.
RUN /app/venv/bin/python /app/code/scripts/verify_pillow_build.py

# Bundle tokenizer files so LLM token estimation never downloads them while serving requests.
ENV TIKTOKEN_CACHE_DIR=/app/tiktoken_cache
RUN /app/venv/bin/python -c "import tiktoken; [tiktoken.get_encoding(name) for name in ('cl100k_base', 'o200k_base')]" \
    && chmod -R a+rX ${TIKTOKEN_CACHE_DIR}

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
