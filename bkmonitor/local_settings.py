DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'bkmonitor_saas',
        'USER': 'root',
        'PASSWORD': '123456',
        'HOST': '127.0.0.1',
        'PORT': '3307',
        'TEST': {
            'CHARSET': 'utf8mb4',
        },
    },
    'monitor_api': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'bkmonitor_api',
        'USER': 'root',
        'PASSWORD': '123456',
        'HOST': '127.0.0.1',
        'PORT': '3307',
        'TEST': {
            'CHARSET': 'utf8mb4',
        },
    },
}

ELASTICSEARCH_DSL = {
    "default": {
        "hosts": "localhost",
        "port": 9200,
        "http_auth": ("elastic", "82hYP7VQ+apinB2M*OD-"),
        "use_ssl": True,
        "verify_certs": False,
    },
}

# for web
# BROKER_URL = "amqp://guest:guest@localhost:5672/"
BROKER_URL = CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379/0"

# 跳过 IAM 权限校验
BK_IAM_SKIP = SKIP_IAM_PERMISSION_CHECK = True

# PYINSTRUMENT_PROFILE_DIR = Path(__file__).parent

# UNIFY_QUERY_URL 需要在 global_setting 表中配置
# "https://unify-query.paas3-dev.bktencent.com"
pass

# 在 web 运行某些后台任务
REDIS_CELERY_CONF = REDIS_QUEUE_CONF = {
    "host": "127.0.0.1",
    "port": 6379,
    "db": 9,
    "password": "",
}
REDIS_SERVICE_CONF = {
    "host": "127.0.0.1",
    "port": 6379,
    "db": 10,
    "password": "",
    "socket_timeout": 10,
}
REDIS_CACHE_CONF = {
    "host": "127.0.0.1",
    "port": 6379,
    "db": 8,
    "password": "",
    "master_name": "",
    "sentinel_password": "",
}
REDIS_LOG_CONF = {
    "host": "127.0.0.1",
    "port": 6379,
    "db": 7,
    "password": "",
}
