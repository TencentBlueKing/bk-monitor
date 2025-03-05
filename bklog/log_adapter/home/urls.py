from django.urls import re_path

from log_adapter.home import views

urlpatterns = [
    re_path(r"^external/$", views.external),
    re_path(r"^external_callback/$", views.external_callback),
    re_path(r"^dispatch_external_proxy/$", views.dispatch_external_proxy),
    re_path(r"^dispatch_list_user_spaces/$", views.dispatch_list_user_spaces),
]
