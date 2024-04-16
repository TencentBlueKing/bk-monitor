FROM python:3.6.15

# Install Node.js and pnpm and other dependencies
RUN curl -sL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs curl wget vim \
    && npm install -g pnpm@8.0.0

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
