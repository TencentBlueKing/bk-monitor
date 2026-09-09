FROM python:3.6-bullseye as builder
ARG build_frontend=true
ARG replace_debian_source=false

# download fonts
RUN mkdir -p /app/fonts \
    && wget https://github.com/adobe-fonts/source-han-sans/raw/release/Variable/TTF/SourceHanSansSC-VF.ttf -O /app/fonts/SourceHanSansSC-VF.ttf \
    && wget https://github.com/adobe-fonts/source-han-serif/raw/release/Variable/TTF/SourceHanSerifSC-VF.ttf -O /app/fonts/SourceHanSerifSC-VF.ttf

# update debian source to ustc
# bullseye 于 2026-08-31 结束 LTS，bullseye-security 不再发布新的 Release 文件，
# 其 Valid-Until 已于 2026-09-07 到期，留在 sources.list 里只会让 apt-get update
# 报 "E: Release file ... is expired" 并以 100 退出，因此两个分支都不再使用该源。
# 其余三个套件（bullseye / -updates / -backports）的 Release 已无 Valid-Until 字段，不会过期。
# 注：`[ ${replace_debian_source} ]` 是非空字符串判断，传 false 也为真，实际总是走 then 分支；
# 当前构建机依赖腾讯源，修正该判断会改变既有行为，故保持原状。
RUN if [ ${replace_debian_source} ] ; then \
        echo "update debian source to ustc" &&\
        mv /etc/apt/sources.list /etc/apt/sources.list.bakevan && \
        echo "deb https://mirrors.tencent.com/debian/ bullseye main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb-src https://mirrors.tencent.com/debian/ bullseye main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb https://mirrors.tencent.com/debian/ bullseye-updates main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb-src https://mirrors.tencent.com/debian/ bullseye-updates main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb https://mirrors.tencent.com/debian/ bullseye-backports main contrib non-free" >>/etc/apt/sources.list && \
        echo "deb-src https://mirrors.tencent.com/debian/ bullseye-backports main contrib non-free" >>/etc/apt/sources.list; \
    else \
        echo "don't need change debian source" && \
        sed -i '/-security/d' /etc/apt/sources.list; \
    fi

# install node and pnpm
RUN apt-get update && apt-get install -y curl && curl -sL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs
RUN npm install -g pnpm@8.15.9

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
  cd /app/webpack/ && pnpm i --frozen-lockfile && npm run prod; \
fi

# copy code
COPY ./ /app/code

RUN if [ "${build_frontend}" = true ] ; then \
  rm -rf /app/code/static/monitor /app/code/static/weixin /app/code/static/fta /app/code/static/apm /app/code/static/trace /app/code/static/external \
  && cp -r /app/webpack/apm/ /app/webpack/monitor/ /app/webpack/fta/ /app/webpack/weixin/ /app/webpack/trace/ /app/webpack/external/ /app/code/static/; \
fi

RUN rm -rf /app/code/webpack /app/code/.git /app/code/support-files/pkgs

FROM python:3.6-bullseye

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

# patch tarfile, shutil
COPY --from=builder /app/code/patches/patch_lib/ /usr/local/lib/python3.6/

CMD python manage.py runserver 0.0.0.0:80
