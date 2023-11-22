from django.conf.urls import url
from log_adapter.home import views

urlpatterns = [
    url(r"^external/$", views.external),
    url(r"^external_callback/$", views.external_callback),
    url(r"^dispatch_external_proxy/$", views.dispatch_external_proxy),
    url(r"^dispatch_list_user_spaces/$", views.dispatch_list_user_spaces),
]
