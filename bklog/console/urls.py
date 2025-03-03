from django.urls import re_path  # noqa

from console import views  # noqa

urlpatterns = (re_path(r"^accounts/logout", views.user_exit),)
