# -*- coding: utf-8 -*-
"""
Local development middleware: auto-login as admin user.
Bypasses BlueKing PaaS login so the app can run standalone.
"""
from django.contrib.auth import get_user_model

User = get_user_model()


class LocalAutoLoginMiddleware:
    """
    If the request has no authenticated user, automatically log in as 'admin'.
    Creates the admin user on first request if it does not exist.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user or not request.user.is_authenticated:
            user, _ = User.objects.get_or_create(
                username="admin",
                defaults={
                    "is_staff": True,
                    "is_superuser": True,
                },
            )
            request.user = user
        return self.get_response(request)
