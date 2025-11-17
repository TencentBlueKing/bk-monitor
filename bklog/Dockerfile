ARG PYTHON_BASE_IMAGE=tencentos/tencentos4-minimal:4.4-v20250922

FROM ${PYTHON_BASE_IMAGE} as builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN dnf install -y curl vim

COPY . /app/code

WORKDIR /app

RUN uv venv venv --seed --link-mode=copy && . venv/bin/activate \
    && uv pip install --no-cache-dir -r code/requirements.txt -i https://mirrors.tencent.com/pypi/simple/ --extra-index-url https://pypi.org/simple/

WORKDIR /app/code

# set python env
ENV C_FORCE_ROOT=1
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

CMD python manage.py migrate
