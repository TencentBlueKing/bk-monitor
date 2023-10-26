from apps.log_commons.models import ApiAuthToken
from apps.utils.admin import AppModelAdmin
from django.contrib import admin


@admin.register(ApiAuthToken)
class ApiAuthTokenAdmin(AppModelAdmin):
    list_display = [
        "id",
        "type",
        "token",
        "space_uid",
        "created_at",
        "created_by",
        "expire_time",
    ]
    search_fields = ["id", "space_uid", "type", "created_by"]
