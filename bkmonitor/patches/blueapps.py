"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""Compatibility fixes for blueapps ticket authentication."""

from django.conf import settings


def patch_ticket_authenticate():
    """Install after Django initialization, only for the configured ticket middleware."""
    if settings.ROLE != "web":
        return

    from blueapps.account.conf import ConfFixture

    if ConfFixture.LOGIN_REQUIRED_MIDDLEWARE != "bk_ticket.middlewares.LoginRequiredMiddleware":
        return

    from blueapps.account.components.bk_ticket.middlewares import LoginRequiredMiddleware

    LoginRequiredMiddleware.authenticate = authenticate


def authenticate(self, request):
    # Use the session key after auth.login(), which can rotate or flush it.
    from django.contrib import auth

    from blueapps.account.components.bk_ticket.middlewares import AuthenticationForm, cache

    form = AuthenticationForm(request.COOKIES)
    if not form.is_valid():
        return None

    bk_ticket = form.cleaned_data["bk_ticket"]
    session_key = request.session.session_key
    if session_key:
        cache_session = cache.get(session_key)
        is_match = cache_session and bk_ticket == cache_session.get("bk_ticket")
        if is_match and request.user.is_authenticated:
            return request.user
    user = auth.authenticate(request=request, bk_ticket=bk_ticket)
    if user is not None and user.username != request.user.username:
        auth.login(request, user)
    if user is not None and request.user.is_authenticated:
        # A user switch flushes the session; SessionMiddleware creates its new key
        # when saving the response. Cache it on the following request instead.
        if request.session.session_key:
            cache.set(request.session.session_key, {"bk_ticket": bk_ticket}, settings.LOGIN_CACHE_EXPIRED)
    return user
