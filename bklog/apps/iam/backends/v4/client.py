"""BKLog codec adapter for the shared IAM V4 HTTP client."""

import requests as requests  # public compatibility patch point

from iam_engine.v4.client import V4Client as SharedV4Client
from .codec import BklogNameCodec


class V4Client(SharedV4Client):
    def __init__(self, options, *, username="", bk_tenant_id="", codec=None):
        super().__init__(options, username=username, bk_tenant_id=bk_tenant_id, codec=codec or BklogNameCodec())
