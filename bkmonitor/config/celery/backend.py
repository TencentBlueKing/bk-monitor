"""Backend broker configuration shared by workers and IAM task producers."""

from urllib.parse import quote

from django.conf import settings

from alarm_backends.core.cluster import get_cluster


def get_backend_celery_broker_config():
    config = {
        "broker_url": f"amqp://{quote(settings.RABBITMQ_USER)}:{quote(settings.RABBITMQ_PASS)}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/{settings.RABBITMQ_VHOST}",
        "broker_transport_options": {},
    }
    cluster = get_cluster()
    if not cluster.is_default():
        config["broker_transport_options"]["queue_name_prefix"] = f"{cluster.name}-"
    return config
