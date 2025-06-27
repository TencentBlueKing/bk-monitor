from rest_framework import serializers

from constants.report import GROUPS, StaffChoice


class StaffSerializer(serializers.Serializer):
    id = serializers.CharField(required=True, max_length=512, label="用户名或组ID")
    name = serializers.CharField(required=False, max_length=512, label="用户名或组名")
    group = serializers.ChoiceField(required=False, allow_null=True, choices=GROUPS, label="所属组别")
    type = serializers.ChoiceField(required=True, choices=[StaffChoice.user, StaffChoice.group])


class ReceiverSerializer(StaffSerializer):
    is_enabled = serializers.BooleanField(required=True, label="是否启动订阅")


class ReportContentSerializer(serializers.Serializer):
    content_title = serializers.CharField(required=True, max_length=512, label="子内容标题")
    content_details = serializers.CharField(required=True, max_length=512, label="子内容说明", allow_blank=True)
    row_pictures_num = serializers.ChoiceField(
        required=True, choices=[(1, "1 Picture"), (2, "2 Pictures")], label="一行几幅图"
    )
    width = serializers.IntegerField(required=False, max_value=4000, label="单图宽度", allow_null=True)
    height = serializers.IntegerField(required=False, max_value=2000, label="单图高度", allow_null=True)
    graphs = serializers.ListField(required=True, label="图表")

    # 单图宽度高度默认值
    size_mapping = {1: (800, 270), 2: (620, 300)}

    def validate(self, attrs):
        """
        根据 row_pictures_num 的值设置 width 和 height 的默认值。
        """
        # 判断是否是整屏图表
        if attrs.get("graphs") and "*" in attrs["graphs"][0]:
            attrs["width"] = attrs.get("width", 1600)
            attrs["height"] = attrs.get("height", None)
        else:
            # 如果图表是单图，则根据row_pictures_num设置width和height
            width, height = self.size_mapping[attrs["row_pictures_num"]]
            attrs["width"] = attrs.get("width", width)
            attrs["height"] = attrs.get("height", height)
        return attrs


class FrequencySerializer(serializers.Serializer):
    type = serializers.IntegerField(required=True, label="频率类型")
    day_list = serializers.ListField(required=True, label="几天")
    week_list = serializers.ListField(required=True, label="周几")
    run_time = serializers.CharField(required=True, label="运行时间", allow_blank=True)
    hour = serializers.FloatField(required=False, label="小时频率")

    class DataRangeSerializer(serializers.Serializer):
        time_level = serializers.CharField(required=True, label="数据范围时间等级")
        number = serializers.IntegerField(required=True, label="数据范围时间")

    data_range = DataRangeSerializer(required=False)

    def to_internal_value(self, data):
        if not data.get("hour"):
            data["hour"] = 0.5
        data = super().to_internal_value(data)
        return data


class SubscriberSerializer(serializers.Serializer):
    username = serializers.CharField(required=True, label="渠道账户")
    is_enabled = serializers.BooleanField(required=False, label="是否启动订阅", default=True)


class EmailSubscriberSerializer(SubscriberSerializer):
    username = serializers.EmailField(required=True, label="渠道账户")


class ReportChannelSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField(required=True, label="是否启动")
    channel_name = serializers.CharField(required=True, label="渠道名称")
    subscribers = serializers.ListField(required=False, label="订阅人员", default=[])

    subscriber_serializers = {"email": EmailSubscriberSerializer}

    def to_internal_value(self, data):
        channel = super().to_internal_value(data)
        subscriber_slz_class = SubscriberSerializer
        if channel["channel_name"] in self.subscriber_serializers:
            subscriber_slz_class = self.subscriber_serializers[channel["channel_name"]]
        subscriber_slz = subscriber_slz_class(data=channel["subscribers"], many=True)
        subscriber_slz.is_valid(raise_exception=True)
        channel["subscribers"] = subscriber_slz.validated_data
        return channel
