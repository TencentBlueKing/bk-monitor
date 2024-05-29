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
    return handler.build_401_response(request)
