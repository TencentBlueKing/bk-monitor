import gzip
import json

from rest_framework.test import APIRequestFactory, force_authenticate

from monitor_web.commons.context import views


def test_enhanced_context_is_gzipped(mocker):
    context = {"BK_BIZ_ID": 2, "SPACE_LIST": [{"bk_biz_id": i, "space_name": f"space-{i}"} for i in range(500)]}
    mocker.patch.object(views, "get_default_biz_id", return_value=2)
    mocker.patch.object(
        views.resource.commons.enhanced_get_context,
        "request",
        return_value={"context": context, "context_type": "basic"},
    )
    request = APIRequestFactory().get(
        "/rest/v2/commons/context/enhanced/", {"context_type": "basic"}, HTTP_ACCEPT_ENCODING="gzip"
    )
    force_authenticate(request, user=mocker.MagicMock(is_authenticated=True))

    response = views.ContextViewSet.as_view({"get": "enhanced"})(request)
    response.render()

    assert response["Content-Encoding"] == "gzip"
    assert json.loads(gzip.decompress(response.content)) == context
    assert response.cookies["bk_biz_id"].value == "2"
