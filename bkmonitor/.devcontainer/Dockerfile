FROM python:3.6.15



RUN mv /etc/apt/sources.list /etc/apt/sources.list.bakevan && \
    echo "deb https://mirrors.tencent.com/debian/ bullseye main contrib non-free" >>/etc/apt/sources.list && \
    echo "deb-src https://mirrors.tencent.com/debian/ bullseye main contrib non-free" >>/etc/apt/sources.list && \
    echo "deb https://mirrors.tencent.com/debian/ bullseye-updates main contrib non-free" >>/etc/apt/sources.list && \
    echo "deb-src https://mirrors.tencent.com/debian/ bullseye-updates main contrib non-free" >>/etc/apt/sources.list && \
    echo "deb https://mirrors.tencent.com/debian/ bullseye-backports main contrib non-free" >>/etc/apt/sources.list && \
    echo "deb-src https://mirrors.tencent.com/debian/ bullseye-backports main contrib non-free" >>/etc/apt/sources.list && \
    echo "deb https://mirrors.tencent.com/debian-security/ bullseye-security main contrib non-free" >>/etc/apt/sources.list && \
    echo "deb-src https://mirrors.tencent.com/debian-security/ bullseye-security main contrib non-free" >>/etc/apt/sources.list

RUN apt update && apt install -y curl wget vim git && curl -sS https://starship.rs/install.sh | sh -s -- -y && echo 'eval "$(starship init bash)"' > ~/.bashrc

# Install Node.js and pnpm and other dependencies
RUN curl -sL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs curl wget vim \
    && npm install -g pnpm@8

# Install Python dependencies
COPY ./requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt -i https://mirrors.tencent.com/pypi/simple \
    && pip install --no-cache-dir betterproto==2.0.0b5 -i https://mirrors.tencent.com/pypi/simple/

# Mount the app directory
VOLUME [ "/app" ]

# Set the working directory
WORKDIR /app

# Expose ports
EXPOSE 8080

CMD [ "sleep", "infinity" ]
