from django.contrib import admin, messages

from apps.iam.models import IAMAuthorizationGrant
from apps.iam.repositories import IAMAuthorizationGrantRepository


@admin.register(IAMAuthorizationGrant)
class IAMAuthorizationGrantAdmin(admin.ModelAdmin):
    list_display = (
        "logical_key",
        "target_version",
        "resource_type",
        "resource_id",
        "state",
        "attempts",
        "next_retry_at",
        "updated_at",
    )
    list_filter = ("target_version", "state", "resource_type")
    search_fields = ("logical_key", "subject_id", "resource_id")
    readonly_fields = tuple(field.name for field in IAMAuthorizationGrant._meta.fields)
    actions = ("requeue_failed_grants",)

    @admin.action(description="重新进入补偿队列（仅最终失败记录）")
    def requeue_failed_grants(self, request, queryset):
        count = IAMAuthorizationGrantRepository.requeue_failed(list(queryset.values_list("pk", flat=True)))
        self.message_user(request, f"已重新入队 {count} 条授权意图", level=messages.SUCCESS)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
