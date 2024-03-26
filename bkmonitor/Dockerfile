FROM python:3.6.15 as builder
ARG build_frontend=true
ARG replace_debian_source=false

# download fonts
RUN mkdir -p /app/fonts \
    && wget https://github.com/adobe-fonts/source-han-sans/raw/release/Variable/TTF/SourceHanSansSC-VF.ttf -O /app/fonts/SourceHanSansSC-VF.ttf \
    && wget https://github.com/adobe-fonts/source-han-serif/raw/release/Variable/TTF/SourceHanSerifSC-VF.ttf -O /app/fonts/SourceHanSerifSC-VF.ttf

# update debian source to ustc
RUN if [ ${replace_debian_source} ] ; then \
        echo "update debian source to ustc" &&\
        mv /etc/apt/sources.list /etc/apt/sources.list.bakevan && \
        echo "deb https://mirrors.tencent.com/debian/ bullseye main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb-src https://mirrors.tencent.com/debian/ bullseye main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb https://mirrors.tencent.com/debian/ bullseye-updates main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb-src https://mirrors.tencent.com/debian/ bullseye-updates main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb https://mirrors.tencent.com/debian/ bullseye-backports main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb-src https://mirrors.tencent.com/debian/ bullseye-backports main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb https://mirrors.tencent.com/debian-security/ bullseye-security main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb-src https://mirrors.tencent.com/debian-security/ bullseye-security main contrib non-free" >>/etc/apt/sources.list; \
    else \
        echo "don't need change debian source"; \
    fi

# install node and pnpm
RUN apt-get update && apt-get install -y curl && curl -sL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs
RUN npm install -g pnpm

WORKDIR /app

# install python packages
COPY ./requirements.txt /app
# betterproto has dependency conflicts in dataclasses with opentelemetry-sdk when installing from requirements.txt
RUN python -m venv venv \
&& /app/venv/bin/pip install --upgrade pip \
&& /app/venv/bin/pip install --no-cache-dir -r /app/requirements.txt -i https://mirrors.tencent.com/pypi/simple/ \
&& rm -rf /app/requirements.txt \
&& /app/venv/bin/pip install --no-cache-dir betterproto==2.0.0b5 -i https://mirrors.tencent.com/pypi/simple/

# build frontend
COPY ./webpack /app/webpack
RUN if [ "${build_frontend}" = true ] ; then \
  cd /app/webpack/ && pnpm i && npm run prod; \
fi

# copy code
COPY ./ /app/code

RUN if [ "${build_frontend}" = true ] ; then \
  rm -rf /app/code/static/monitor /app/code/static/weixin /app/code/static/fta /app/code/static/apm /app/code/static/trace /app/code/static/external \
  && cp -r /app/webpack/apm/ /app/webpack/monitor/ /app/webpack/fta/ /app/webpack/weixin/ /app/webpack/trace/ /app/webpack/external/ /app/code/static/; \
fi

RUN rm -rf /app/code/webpack /app/code/.git /app/code/support-files/pkgs

FROM python:3.6.15

ARG username=bkmonitor
ARG version

# copy source.list file
COPY --from=builder /etc/apt/sources.list /etc/apt/sources.list
# install fonts
COPY --from=builder /app/fonts/ /app/fonts/
RUN install -m644 /app/fonts/SourceHanSansSC-VF.ttf /usr/share/fonts/truetype/ \
    && install -m644 /app/fonts/SourceHanSerifSC-VF.ttf /usr/share/fonts/truetype/ \
    && rm -rf /app/fonts

# install vim and chromium
RUN apt-get update  \
    && apt-get install -y vim chromium wget strace graphviz \
    && groupadd -r ${username}  \
    && useradd -r -g ${username} ${username}  \
    && mkdir -p /data/ /app/ /home/${username} \
    && chown -R ${username}:${username} /data/ /app/ /home/${username}

# move code and python packages
COPY --from=builder --chown=${username}:${username} /app/venv /app/venv
COPY --from=builder --chown=${username}:${username} /app/code/ /app/code/
COPY --from=builder --chown=${username}:${username} /app/code/docs/api/monitor_v3.yaml /app/code/kernel_api/monitor_v3.yaml
RUN echo ${version} > /app/code/VERSION

USER ${username}

# set workdir
WORKDIR /app/code

# set python env
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

CMD python manage.py runserver 0.0.0.0:80
