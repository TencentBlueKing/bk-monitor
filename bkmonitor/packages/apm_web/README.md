# Blueking APM SaaS Development Guide

## How to run APM SaaS locally?

1. setup your python environment
```shell
# on top folder
pip install -r requirements.txt
pip install -r requirements_test.txt
```
2. load required env variables
```shell
export APP_CODE=bk_monitorv3
export APP_TOKEN={your-app-token}
export BK_PAAS_HOST={your-paas-host}
export BKAPP_DEPLOY_PLATFORM=enterprise

```

3. run django server
```shell
python manage.py runserver 0.0.0.0:8000
```

4. run unittest
```shell
pytest packages/apm_web/tests/ --reuse-db
```