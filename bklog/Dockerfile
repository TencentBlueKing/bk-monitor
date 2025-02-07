FROM python:3.6.12 as builder

RUN apt-get update && apt-get install -y curl vim
RUN curl -sL https://deb.nodesource.com/setup_12.x | bash - && apt-get install -y nodejs

COPY . /app/code

WORKDIR /app

RUN python -m venv venv \
&& venv/bin/pip install --upgrade --no-cache-dir pip==20.2.3 setuptools==57.5.0 \
&& venv/bin/pip install --no-cache-dir -r code/requirements.txt -i https://mirrors.tencent.com/pypi/simple/ --extra-index-url https://mirrors.tencent.com/repository/pypi/tencent_pypi/simple 

RUN venv/bin/pip uninstall -y pycrypto && venv/bin/pip uninstall -y pycryptodome && venv/bin/pip install pycryptodome

WORKDIR /app/code

# set python env
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

CMD python manage.py migrate

