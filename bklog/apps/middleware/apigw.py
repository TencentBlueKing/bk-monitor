"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import jwt
from apigw_manager.apigw.authentication import (
    ApiGatewayJWTGenericMiddleware,
    JWTTokenInvalid,
)
from apigw_manager.apigw.providers import (
    CachePublicKeyProvider,
    DecodedJWT,
    DefaultJWTProvider,
)
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.http import HttpRequest
from six import raise_from

from apps.utils.log import logger


class UserModelBackend(ModelBackend):
    """Get users by username"""

    def __init__(self):
        super().__init__()

        self.user_model = get_user_model()

        # 未将用户保存到 db，防止未预期添加用户数据
        # 未查询 db 中用户，因用户可能在 db 中不存在
        self.user_maker = lambda username: self.user_model(**{self.user_model.USERNAME_FIELD: username})

    def authenticate(self, request, gateway_name, bk_username, verified, **credentials):
        try:
            return self.user_model.objects.get(**{self.user_model.USERNAME_FIELD: bk_username})
        except self.user_model.DoesNotExist:
            return self.user_maker(bk_username)


class CustomCachePublicKeyProvider(CachePublicKeyProvider):
    def provide(self, gateway_name: str, jwt_issuer: str | None = None, request: HttpRequest = None) -> str | None:
        """Return the public key specified by Settings"""
        external_public_key = getattr(settings, "EXTERNAL_APIGW_PUBLIC_KEY", None)
        if not request:
            return super().provide(gateway_name, jwt_issuer)
        is_external = request.headers.get("Is-External", "false")
        if is_external == "true":
            logger.info(
                "This request is from external api gateway, use external public key: `EXTERNAL_APIGW_PUBLIC_KEY`."
            )
            if not external_public_key:
                logger.warning(
                    "No `EXTERNAL_APIGW_PUBLIC_KEY` can be found in settings, you should either configure it "
                    "with a valid value or remove `ApiGatewayJWTExternalMiddleware` middleware entirely"
                )
            return external_public_key
        new_internal_apigw_name = getattr(settings, "NEW_INTERNAL_APIGW_NAME", None)
        if gateway_name and new_internal_apigw_name and gateway_name == new_internal_apigw_name:
            new_internal_public_key = getattr(settings, "NEW_INTERNAL_APIGW_PUBLIC_KEY", None)
            if new_internal_public_key:
                logger.info(
                    """
                    This request is from new internal api gateway, 
                    use new internal public key: `NEW_INTERNAL_APIGW_PUBLIC_KEY`.
                    """
                )
                return new_internal_public_key
        return super().provide(gateway_name, jwt_issuer)


class ApiGatewayJWTProvider(DefaultJWTProvider):
    def provide(self, request: HttpRequest) -> DecodedJWT | None:
        jwt_token = request.META.get(self.jwt_key_name, "")
        if not jwt_token:
            return None

        try:
            jwt_header = self._decode_jwt_header(jwt_token)
            gateway_name = jwt_header.get("kid") or self.default_gateway_name
            public_key = CustomCachePublicKeyProvider(default_gateway_name=self.default_gateway_name).provide(
                gateway_name=gateway_name, jwt_issuer=jwt_header.get("iss"), request=request
            )
            if not public_key:
                logger.warning("no public key found, gateway=%s, issuer=%s", gateway_name, jwt_header.get("iss"))
                return None

            algorithm = jwt_header.get("alg") or self.algorithm
            decoded = self._decode_jwt(jwt_token, public_key, algorithm)

            return DecodedJWT(gateway_name=gateway_name, payload=decoded)

        except jwt.PyJWTError as e:
            if not self.allow_invalid_jwt_token:
                raise_from(JWTTokenInvalid, e)

        return None


class ApiGatewayJWTMiddleware(ApiGatewayJWTGenericMiddleware):
    PUBLIC_KEY_PROVIDER_CLS = CustomCachePublicKeyProvider
