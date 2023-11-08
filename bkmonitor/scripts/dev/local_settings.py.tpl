import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("BKAPP_SAAS_DB_USER"),
        "PASSWORD": os.getenv("BKAPP_SAAS_DB_PASSWORD"),
        "HOST": os.getenv("BKAPP_SAAS_DB_HOST"),
        "PORT": os.getenv("BKAPP_SAAS_DB_PORT"),
    },
    "monitor_api": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("BK_MONITOR_MYSQL_NAME"),
        "USER": os.getenv("BK_MONITOR_MYSQL_USER"),
        "PASSWORD": os.getenv("BK_MONITOR_MYSQL_PASSWORD"),
        "HOST": os.getenv("BK_MONITOR_MYSQL_HOST"),
        "PORT": os.getenv("BK_MONITOR_MYSQL_PORT"),
    }
}
