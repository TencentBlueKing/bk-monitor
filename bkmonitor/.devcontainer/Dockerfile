FROM python:3.7-bullseye

ARG APT_MIRROR="https://mirrors.tencent.com"
ARG PIP_MIRROR="https://mirrors.tencent.com/pypi/simple"

# replace mirrors
RUN sed -i "s@http://deb.debian.org/debian@${APT_MIRROR}/debian@g" /etc/apt/sources.list \
    && sed -i "s@http://security.debian.org/debian-security@${APT_MIRROR}/debian-security@g" /etc/apt/sources.list

# Set the default shell to bash rather than sh
ENV SHELL /bin/bash

# 安装工具包及npm
RUN apt-get update && apt-get install -y curl wget git vim supervisor && git config --global core.trustctime false

# replace pip source
RUN mkdir -p ~/.pip && echo "[global]\nindex-url = $PIP_MIRROR/\n" > ~/.pip/pip.conf && pip install --upgrade pip
ENV PIP_ROOT_USER_ACTION=ignore

# set python env
ENV VIRTUAL_ENV=/app/code/bkmonitor/venv
ENV PATH="/app/code/bkmonitor/venv/bin:${PATH}"

# Mount your project into the container
VOLUME /app/code

# Set the default working directory as the project root
WORKDIR /app/code

# set git safe directory
RUN git config --global --add safe.directory /app/code

# Expose the port the app runs on
EXPOSE 8000

# Set the default command to run when starting the container
CMD ["sleep", "infinity"]
