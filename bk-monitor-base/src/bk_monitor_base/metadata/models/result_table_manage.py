from django.db import models


class EnableManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_disable=False)
