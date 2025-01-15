from django.conf.urls import url  # noqa

from console import views  # noqa

urlpatterns = (url(r"^accounts/logout", views.user_exit),)
