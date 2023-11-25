from django.conf.urls import include, url

app_name = "log_adapter"

urlpatterns = [
    url(r"^", include("log_adapter.home.urls")),
]
