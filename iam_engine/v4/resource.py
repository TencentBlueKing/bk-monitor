"""V4 wire-format adapter for the existing SDK ResourceProvider contract."""

from copy import copy

from iam.resource.provider import ListResult, ResourceProvider


class V4ResourceProvider(ResourceProvider):
    def __init__(self, provider, resource_type, codec, *, root_resource_type="space"):
        self.provider = provider
        self.resource_type = resource_type
        self.codec = codec
        self.root_resource_type = root_resource_type

    def _filter(self, filters):
        result = copy(filters)
        parent = getattr(filters, "parent", None)
        if parent:
            if parent["type"] != self.root_resource_type or self.resource_type == self.root_resource_type:
                raise ValueError("unsupported parent resource type")
            result["parent"] = {
                **parent,
                "id": self.codec.decode_resource_id(self.root_resource_type, parent["id"]),
            }
        ids = getattr(filters, "ids", None)
        if ids is not None:
            result["ids"] = [self.codec.decode_resource_id(self.resource_type, item) for item in ids]
        return result

    def _path(self, path):
        if isinstance(path, list):
            # SDK V3 path is a list of ancestor chains. V4 has a single parent path.
            if not path:
                return "/"
            if len(path) != 1:
                raise ValueError("V4 callback requires a single parent path")
            segments = [(item["type"], str(item["id"])) for item in path[0]]
        else:
            segments = [item.partition(",")[::2] for item in str(path).strip("/").split("/") if item]
        return "/" + "/".join(
            f"{self.codec.encode_resource_type(kind)},{self.codec.encode_resource_id(kind, identity)}"
            for kind, identity in segments
        ) + ("/" if segments else "")

    def _result(self, result, requires=None):
        converted = []
        for row in result.results:
            item = dict(row)
            item["id"] = self.codec.encode_resource_id(self.resource_type, str(item["id"]))
            if "_bk_iam_path_" in item:
                item["_bk_iam_path_"] = self._path(item["_bk_iam_path_"])
            approver = item.pop("_bk_iam_approver_", None)
            if approver is not None:
                item["_bk_iam_approvers_"] = [approver] if approver else []
            if requires:
                wanted = {"id", "display_name", *requires}
                item = {key: value for key, value in item.items() if key in wanted}
            converted.append(item)
        # Do not mutate the original SDK result or its cached dictionaries.
        return type(result)(results=converted, count=result.count)

    def list_instance(self, filter, page, **options):
        result = self.provider.list_instance(self._filter(filter), page, include_resource_metadata=True, **options)
        return self._result(result)

    def fetch_instance_info(self, filter, **options):
        if not filter.ids:
            return ListResult(results=[], count=0)
        result = self.provider.fetch_instance_info(self._filter(filter), include_resource_metadata=True, **options)
        return self._result(result, getattr(filter, "attrs", None))

    def list_attr(self, **options):
        raise NotImplementedError

    def list_attr_value(self, filter, page, **options):
        raise NotImplementedError

    def list_instance_by_policy(self, filter, page, **options):
        raise NotImplementedError

    def search_instance(self, filter, page, **options):
        raise NotImplementedError
