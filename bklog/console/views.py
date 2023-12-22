from django.contrib import auth
from django.http import HttpResponseRedirect
from rest_framework.views import APIView


class LogOutView(APIView):
    def get(self, request):
        auth.logout(request)
        response = HttpResponseRedirect("/")
        cookie_keys = ["bk_ticket", "bk_token", "bk_uid"]
        host = "".join(request.headers["Host"].split(":")[:1])
        domain = f'.{".".join(host.split(".")[1:])}'
        for _domain in [host, domain]:
            for key in cookie_keys:
                response.delete_cookie(key, domain=_domain)
        return response
