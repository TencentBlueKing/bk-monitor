from django.apps import AppConfig


class LocalAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'local_app'
