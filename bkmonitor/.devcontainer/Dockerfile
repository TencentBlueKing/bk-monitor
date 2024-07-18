FROM python:3.6.15

ARG APT_MIRROR="https://mirrors.tencent.com"

# replace mirrors
RUN sed -i "s@http://deb.debian.org/debian@${APT_MIRROR}/debian@g" /etc/apt/sources.list \
    && sed -i "s@http://security.debian.org/debian-security@${APT_MIRROR}/debian-security@g" /etc/apt/sources.list


# Set the default shell to bash rather than sh
ENV SHELL /bin/bash

# 安装工具包及npm
RUN apt-get update && apt-get install -y curl wget git vim supervisor

#starship
RUN curl -sS https://starship.rs/install.sh | sh -s -- -y && echo 'eval "$(starship init bash)"' > ~/.bashrc
RUN echo 'eval "$(starship init bash)"' >> ~/.bashrc && echo "PATH=$PATH:/home/bkmonitor/.local/bin" >> ~/.bashrc

# 安装code-server插件
# RUN code-server --install-extension ms-python.python && \
#     code-server --install-extension Equinusocio.vsc-material-theme && \
#     code-server --install-extension equinusocio.vsc-material-theme-icons && \
#     code-server --install-extension xyz.local-history && \
#     code-server --install-extension eamodio.gitlens

# 安装python依赖
RUN pip install --upgrade --no-cache-dir pip==20.2.3 setuptools==57.5.0

# Mount your project into the container
VOLUME /app/code

# Set the default working directory as the project root
WORKDIR /app/code

# Expose the port the app runs on
EXPOSE 8000

# Set the default command to run when starting the container
CMD ["sleep", "infinity"]
