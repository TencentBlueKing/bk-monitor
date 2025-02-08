FROM python:3.11.10 as builder

ARG username=bklog

RUN apt-get update && apt-get install -y curl vim

RUN groupadd -r ${username}  \
    && useradd -r -g ${username} ${username}  \
    && mkdir -p /data/ /app/ /home/${username} \
    && chown -R ${username}:${username} /data/ /app/ /home/${username}

COPY --chown=${username}:${username} . /app/code

WORKDIR /app

RUN python -m venv venv \
&& venv/bin/pip install --no-cache-dir -r code/requirements.txt -i https://mirrors.tencent.com/pypi/simple/ --extra-index-url https://mirrors.tencent.com/repository/pypi/tencent_pypi/simple

# set user
USER ${username}

WORKDIR /app/code

# set python env
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

CMD python manage.py migrate
