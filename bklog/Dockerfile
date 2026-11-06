ARG PYTHON_BASE_IMAGE=tencentos/tencentos4-minimal:4.4-v20250922

FROM ${PYTHON_BASE_IMAGE} AS python-base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Both stages use the same system Python and native runtime libraries.
RUN dnf install -y curl vim python3 libstdc++ file-libs && dnf clean all

FROM python-base AS builder

RUN dnf install -y gcc gcc-c++ python3-devel make && dnf clean all

COPY . /app/code

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv venv --python /usr/bin/python3 --seed --link-mode=copy && . venv/bin/activate \
    && uv pip install --link-mode=copy -r code/requirements.txt -i https://mirrors.tencent.com/pypi/simple/ --extra-index-url https://pypi.org/simple/

FROM python-base AS runtime

COPY --from=builder /app/venv /app/venv
COPY --from=builder /app/code /app/code

WORKDIR /app/code

# set python env
ENV C_FORCE_ROOT=1
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

CMD python manage.py migrate
