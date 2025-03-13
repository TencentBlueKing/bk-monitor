from django.conf.urls import include
from django.urls import re_path

app_name = "log_adapter"

urlpatterns = [
    re_path(r"^", include("log_adapter.home.urls")),
]
