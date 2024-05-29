from blueapps.account import ConfFixture
from blueapps.account.handlers.response import ResponseHandler
from django.conf import settings
from django.contrib import auth


def user_exit(request):
    def add_logout_slug():
        return {"is_from_logout": "1"}

    auth.logout(request)

    # 验证不通过，需要跳转至统一登录平台
    request.path = request.path.replace("/console/accounts/logout", "")
    handler = ResponseHandler(ConfFixture, settings)
    handler._build_extra_args = add_logout_slug
    response = handler.build_401_response(request)

    # 清除 cookies
    cookie_keys = ["bk_ticket", "bk_token", "bk_uid"]
    host = "".join(request.headers["Host"].split(":")[:1])
    domain = f'.{".".join(host.split(".")[1:])}'
    for _domain in [host, domain]:
        for key in cookie_keys:
            response.delete_cookie(key, domain=_domain)
    return response
