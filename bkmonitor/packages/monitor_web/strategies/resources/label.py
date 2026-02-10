import logging

from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.models import StrategyLabel
from core.drf_resource import Resource, resource

logger = logging.getLogger(__name__)


class StrategyLabelResource(Resource):
    """
    创建/修改策略标签
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, default=0, label="业务ID")
        strategy_id = serializers.IntegerField(required=False, default=0, label="策略ID")
        id = serializers.CharField(required=False, label="标签ID", default=None)
        label_name = serializers.CharField(required=True, label="标签名")

        def validate_label_name(self, value):
            label_name = StrategyLabelResource.gen_label_name(value)
            return label_name

        def validate(self, attrs):
            label_name = attrs["label_name"]
            if StrategyLabel.objects.filter(
                label_name=label_name, strategy_id=attrs["strategy_id"], bk_biz_id=attrs["bk_biz_id"]
            ).exists():
                raise ValidationError(_("标签{}已存在").format(label_name))
            return attrs

    def edit_label(self, label_name, label_id=None, strategy_id=0, bk_biz_id=0):
        # create/update label
        # 将父节点全部删除，再新建当前全路径节点。
        # 输入：label_name-> /a/b/c/
        # 如果有 /a/b/c/.*/，则表示创建的是上层目录，啥都不做即可。
        # 删除/a/, /a/b/
        # 新增/a/b/c/
        parent_label = self.get_parent_labels(label_name)
        StrategyLabel.objects.filter(label_name__in=parent_label, bk_biz_id=bk_biz_id, strategy_id=strategy_id).delete()
        if StrategyLabel.objects.filter(
            label_name__startswith=label_name, bk_biz_id=bk_biz_id, strategy_id=strategy_id
        ).exists():
            # 如果有 /a/b/c/.*/，则表示创建的是上层目录，啥都不做即可。
            logger.info(f"label_name: {label_name} exists, nothing to do")
            if label_id:
                # 如果是编辑，那么原标签可以删掉了
                target_label = StrategyLabel.objects.get(
                    label_name=label_id, bk_biz_id=bk_biz_id, strategy_id=strategy_id
                )
                logger.info(f"{target_label.label_name} -> {label_name}, already exists another label, will delete ")
                target_label.delete()
            return None
        if label_id is None:
            label_obj = StrategyLabel.objects.create(
                label_name=label_name, bk_biz_id=bk_biz_id, strategy_id=strategy_id
            )
            label_id = label_obj.label_name
        else:
            StrategyLabel.objects.filter(label_name=label_id, bk_biz_id=bk_biz_id, strategy_id=strategy_id).update(
                label_name=label_name
            )
        return label_id

    @classmethod
    def get_global_label(cls, label_name):
        return StrategyLabel.objects.filter(label_name=label_name, bk_biz_id=0, strategy_id=0).first()

    def perform_request(self, validated_request_data):
        label_id = validated_request_data.get("id")
        if label_id:
            label_id = self.gen_label_name(label_id)
        label_name = validated_request_data["label_name"]
        strategy_id = validated_request_data["strategy_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        return self.edit_label(label_name, label_id, strategy_id=strategy_id, bk_biz_id=bk_biz_id)

    @classmethod
    def gen_label_name(cls, label):
        return f"/{label.strip('/')}/"

    def get_parent_labels(self, label_name):
        labels = []
        for label in filter(lambda x: x, label_name.split("/")):
            if labels:
                labels.append(self.gen_label_name("/".join([labels[-1].strip("/"), label])))
            else:
                labels.append(self.gen_label_name(label))
        if labels:
            if labels.pop(-1) != label_name:
                raise
        return labels


class DeleteStrategyLabelResource(Resource):
    """
    删除策略标签
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, default=0, label="业务ID")
        strategy_id = serializers.IntegerField(required=False, default=0, label="策略ID")
        label_name = serializers.CharField(required=False, label="标签名", default="")

        def validate_label_name(self, value):
            label_name = StrategyLabelResource.gen_label_name(value) if value else ""
            return label_name

        def validate(self, attrs):
            if attrs["bk_biz_id"] == attrs["strategy_id"] == 0:
                if not attrs["label_name"]:
                    raise ValidationError(_("参数缺少label_name"))
            return attrs

    def perform_request(self, validated_request_data):
        label_name = validated_request_data["label_name"]
        strategy_id = validated_request_data["strategy_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        if strategy_id == bk_biz_id == 0:
            StrategyLabel.objects.filter(label_name__startswith=label_name, bk_biz_id=0, strategy_id=0).delete()
            # 如果标签上级只剩下被删除标签，则创建上层级标签
            # a/b 删除后， 变成 a
            parents = resource.strategies.strategy_label.get_parent_labels(label_name)
            if parents:
                if not StrategyLabel.objects.filter(
                    label_name__startswith=parents[-1], bk_biz_id=0, strategy_id=0
                ).exists():
                    StrategyLabel.objects.create(label_name=parents[-1], bk_biz_id=0, strategy_id=0)
        elif strategy_id != 0:
            # 基于策略ID删除全部标签
            StrategyLabel.objects.filter(strategy_id=strategy_id).delete()


class StrategyLabelList(Resource):
    """
    获取策略标签列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, default=0, label="业务ID")
        strategy_id = serializers.IntegerField(required=False, default=0, label="策略ID")

    def perform_request(self, validated_request_data):
        strategy_id = validated_request_data["strategy_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        # strategy_id != 0 表示获取单策略的标签
        # strategy_id == 0 & bk_biz_id != 0 表示获取业务下策略标签+全局标签
        # bk_biz_id == 0 表示获取全局标签
        global_labels = StrategyLabel.objects.filter(bk_biz_id=0)
        if strategy_id != 0:
            labels = StrategyLabel.objects.filter(strategy_id=strategy_id)
        else:
            if bk_biz_id != 0:
                labels = StrategyLabel.objects.filter(bk_biz_id__in=[0, bk_biz_id])
            else:
                labels = global_labels
        return self.group_labels(labels, global_labels)

    def group_labels(self, labels, global_labels):
        labels_dict = {"global": {}, "custom": {}, "global_parent_nodes": [], "custom_parent_nodes": []}
        global_label_set = global_labels.values_list("label_name", flat=True)
        for label in labels.values("label_name", "id"):
            if label["label_name"] in global_label_set:
                labels_dict["global"][label["label_name"]] = label["label_name"].strip("/")
            else:
                labels_dict["custom"][label["label_name"]] = label["label_name"].strip("/")
        global_dict = labels_dict["global"]
        custom_dict = labels_dict["custom"]
        labels_dict["global"] = [{"label_name": v, "id": k} for k, v in global_dict.items()]
        global_parent_nodes = []
        custom_parent_nodes = []
        for label_id in global_dict.keys():
            global_parent_nodes.extend(resource.strategies.strategy_label.get_parent_labels(label_id))
        for label_id in custom_dict.keys():
            custom_parent_nodes.extend(resource.strategies.strategy_label.get_parent_labels(label_id))
        labels_dict["custom"] = [{"label_name": v, "id": k} for k, v in custom_dict.items()]
        for label_id in set(global_parent_nodes).difference(set(global_dict.keys())):
            labels_dict.setdefault("global_parent_nodes", []).append(
                {"label_name": label_id.strip("/"), "label_id": label_id}
            )
        for label_id in set(custom_parent_nodes).difference(set(custom_dict.keys())):
            labels_dict.setdefault("custom_parent_nodes", []).append(
                {"label_name": label_id.strip("/"), "label_id": label_id}
            )
        return labels_dict
