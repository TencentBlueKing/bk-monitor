from django.contrib import auth
from rest_framework.response import Response
from rest_framework.views import APIView


class LogOutView(APIView):
    def get(self, request):
        auth.logout(request)
        response = Response("User Logged out successfully")
        cookie_keys = ["bk_ticket", "bk_token", "bk_uid"]
        host = "".join(request.headers["Host"].split(":")[:1])
        domain = f'.{".".join(host.split(".")[1:])}'
        for _domain in [host, domain]:
            for key in cookie_keys:
                response.delete_cookie(key, domain=_domain)
        return response
