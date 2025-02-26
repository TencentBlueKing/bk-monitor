ARG PYTHON_VERSION=3.11


FROM python:${PYTHON_VERSION}-bullseye AS base

ENV LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

## PYTHON
# Seems to speed things up
ENV PYTHONUNBUFFERED=1
# Turns off writing .pyc files. Superfluous on an ephemeral container.
ENV PYTHONDONTWRITEBYTECODE=1

# 设置非交互模式
ENV DEBIAN_FRONTEND=noninteractive

# Ensures that the python and pip executables used
# in the image will be those from our virtualenv.
ENV PATH="/venv/bin:$PATH"

RUN set -ex && \
    chmod 1777 /tmp && \
    rm /etc/apt/sources.list && \
    echo "deb https://mirrors.tencent.com/debian/ bullseye main contrib non-free" >>/etc/apt/sources.list && \
    echo "deb-src https://mirrors.tencent.com/debian/ bullseye main contrib non-free" >>/etc/apt/sources.list && \
    echo "deb https://mirrors.tencent.com/debian/ bullseye-updates main contrib non-free" >>/etc/apt/sources.list && \
    echo "deb-src https://mirrors.tencent.com/debian/ bullseye-updates main contrib non-free" >>/etc/apt/sources.list && \
    echo "deb https://mirrors.tencent.com/debian/ bullseye-backports main contrib non-free" >>/etc/apt/sources.list && \
    echo "deb-src https://mirrors.tencent.com/debian/ bullseye-backports main contrib non-free" >>/etc/apt/sources.list && \
    echo "deb https://mirrors.tencent.com/debian-security/ bullseye-security main contrib non-free" >>/etc/apt/sources.list && \
    echo "deb-src https://mirrors.tencent.com/debian-security/ bullseye-security main contrib non-free" >>/etc/apt/sources.list;

RUN set -ex && mkdir ~/.pip && printf '[global]\nindex-url = https://mirrors.tencent.com/pypi/simple/' > ~/.pip/pip.conf


# Install OS package dependencies.
# Do all of this in one RUN to limit final image size.
RUN set -ex &&  \
    apt-get update && \
    apt-get -f install && \
    apt-get install -y --no-install-recommends \
        gcc gettext mariadb-client && \
    rm -rf /var/lib/apt/lists/*


FROM base AS builder

WORKDIR /

COPY requirements.txt /
COPY requirements_test.txt /

# 创建 Python 虚拟环境
RUN set -ex && python -m venv /venv && pip install --upgrade pip && pip install --no-cache-dir -r requirements_test.txt


FROM base AS base-app

USER root

# 安装运行时依赖
RUN set -ex &&  \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        debconf-utils lsb-release gnupg wget curl vim git redis-server mariadb-server && \
    rm -rf /var/lib/apt/lists/*

RUN set -ex && \
    mkdir -p /var/lib/mysql /run/mysqld /tmp/mysql && \
    chown -R mysql:mysql /var/lib/mysql /run/mysqld /tmp/mysql && \
    chmod 1777 /tmp/mysql && \
    mysql_install_db --user=mysql --datadir=/var/lib/mysql --skip-test-db

WORKDIR /app

ADD ./ ./

COPY scripts/unittest/local_settings.py ./

# 拷贝构件
COPY --from=builder /venv /venv


FROM base-app AS app

ENV DJANGO_SETTINGS_MODULE=settings
ENV DJANGO_CONF_MODULE=conf.worker.development.enterprise
ENV APP_TOKEN=xxxxxxxxxx
ENV BK_MONITOR_APP_SECRET=xxxxxxxxxx
ENV USE_DYNAMIC_SETTINGS=0
ENV BKAPP_DEPLOY_PLATFORM=enterprise

ENTRYPOINT ["scripts/unittest/entrypoint.sh"]
