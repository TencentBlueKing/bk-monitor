ARG PYTHON_BASE_IMAGE=tencentos/tencentos4-minimal:4.4-v20250922

FROM ${PYTHON_BASE_IMAGE} AS python-base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Both stages use the same system Python and native runtime libraries.
RUN dnf install -y curl vim python3 libstdc++ file-libs && dnf clean all

FROM python-base AS builder

RUN dnf install -y gcc gcc-c++ python3-devel make && dnf clean all

COPY . /app/code
# The BKLog-only build context must materialize shared symlinks (cp -RL / tar -h).
# Fail at build time rather than deploy a broken runtime import.
RUN test -f /app/code/iam_engine/core/config.py

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

# Check the final stage, where builder-only libraries are no longer available.
RUN python -c 'import sys; assert sys.version_info >= (3, 11); from bk_kms import decrypt; import ujson, jieba_fast, grpc, magic; from iam_engine.core.config import DEFAULT_DUAL_STACK; assert sys.prefix == "/app/venv"; assert ujson.loads(ujson.dumps({"ok": True}))["ok"]; assert list(jieba_fast.cut("runtime smoke test")); assert magic.from_buffer(b"runtime smoke test"); print("BKLog runtime imports: OK")' \
    && command -v ldd \
    && find /app/venv -type f -name '*.so*' -exec ldd '{}' \; > /tmp/bklog-runtime-ldd.log 2>&1 \
    && if grep -F 'not found' /tmp/bklog-runtime-ldd.log; then exit 1; fi \
    && test ! -d /usr/include/c++ \
    && ! command -v gcc \
    && ! command -v g++ \
    && rm /tmp/bklog-runtime-ldd.log

CMD python manage.py migrate
