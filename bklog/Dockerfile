ARG PYTHON_BASE_IMAGE=tencentos/tencentos4-minimal:4.4-v20250922

FROM ${PYTHON_BASE_IMAGE} as builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY . /app/code
# The BKLog-only build context must materialize shared symlinks (cp -RL / tar -h).
# Fail at build time rather than deploy a broken runtime import.
RUN test -f /app/code/iam_engine/core/config.py

WORKDIR /app

# Install and remove the compiler in one layer so build-only files are not retained.
RUN dnf install -y curl vim gcc gcc-c++ python3-devel make \
    && UV_NO_CACHE=1 uv venv venv --seed --link-mode=copy && . venv/bin/activate \
    && UV_NO_CACHE=1 uv pip install --no-cache-dir -r code/requirements.txt -i https://mirrors.tencent.com/pypi/simple/ --extra-index-url https://pypi.org/simple/ \
    && dnf remove -y gcc gcc-c++ libstdc++-devel python3-devel make \
    && dnf clean all \
    && rm -rf /root/.cache /usr/include/c++ /var/cache/dnf

WORKDIR /app/code

# set python env
ENV C_FORCE_ROOT=1
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

CMD python manage.py migrate
