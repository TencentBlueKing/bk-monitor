FROM python:3.11.10 as builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y curl vim

COPY . /app/code

WORKDIR /app

RUN uv venv venv --seed --link-mode=copy && source venv/bin/activate \
    && uv pip install --no-cache-dir -r code/requirements.txt -i https://mirrors.tencent.com/pypi/simple/ --extra-index-url https://mirrors.tencent.com/repository/pypi/tencent_pypi/simple

WORKDIR /app/code

# set python env
ENV C_FORCE_ROOT=1
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

CMD python manage.py migrate
