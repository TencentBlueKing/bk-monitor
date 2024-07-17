FROM python:3.6.15

ARG APT_MIRROR="https://mirrors.tencent.com"
#ARG build_frontend=true

RUN sed -i "s@http://deb.debian.org/debian@${APT_MIRROR}/debian@g" /etc/apt/sources.list \
    && sed -i "s@http://security.debian.org/debian-security@${APT_MIRROR}/debian-security@g" /etc/apt/sources.list

#starship
RUN apt update && apt install -y curl wget vim git && curl -sS https://starship.rs/install.sh | sh -s -- -y && echo 'eval "$(starship init bash)"' > ~/.bashrc
RUN echo 'eval "$(starship init bash)"' >> ~/.bashrc && echo "PATH=$PATH:/home/bkmonitor/.local/bin" >> ~/.bashrc

# 安装工具包及npm
RUN apt update && apt install -y curl wget git vim supervisor \
    && curl -fsSL https://code-server.dev/install.sh | sh \
    && mkdir -p /usr/local/lib/nodejs \
    && wget https://nodejs.org/download/release/v18.18.2/node-v18.18.2-linux-x64.tar.xz \
    && tar -xvf node-v18.18.2-linux-x64.tar.xz -C /usr/local/lib/nodejs \
    && echo 'export PATH=/usr/local/lib/nodejs/node-v18.18.2-linux-x64/bin:$PATH' >> ~/.bashrc

# npm加入PATH环境变量
ENV PATH="/usr/local/lib/nodejs/node-v18.18.2-linux-x64/bin:${PATH}"
RUN npm install -g npm@latest pnpm

# install node and pnpm
RUN apt-get update && apt-get install -y curl && curl -sL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs
RUN npm install -g pnpm

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
