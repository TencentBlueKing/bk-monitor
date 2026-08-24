from alarm_backends.service.nodata import processor as nodata_processor
from alarm_backends.service.nodata.processor import CheckProcessor


def test_nodata_push_data_trims_items_only_after_anomaly_list_publish(mocker):
    processor = object.__new__(CheckProcessor)
    processor.strategy_id = "10"
    processor.inputs = {}
    processor.outputs = {1: [{"data": {"value": 1}}]}
    processor.check_result_producer_token = "producer-token"
    processor.check_result_producer_lock = mocker.sentinel.producer_lock
    processor.strategy = mocker.MagicMock(items=[mocker.MagicMock(id=1), mocker.MagicMock(id=2)])
    push_abnormal_data = mocker.patch.object(processor, "push_abnormal_data", return_value=1)
    trim_item = mocker.patch.object(nodata_processor, "trim_item_check_results_if_trigger_idle")
    mocker.patch.object(nodata_processor, "metrics")
    operation_order = mocker.MagicMock()
    operation_order.attach_mock(push_abnormal_data, "push")
    operation_order.attach_mock(trim_item, "trim")

    processor.push_data()

    assert operation_order.method_calls == [
        mocker.call.push(processor.outputs, "10", []),
        mocker.call.trim(processor.strategy.items[0], "producer-token", mocker.sentinel.producer_lock),
        mocker.call.trim(processor.strategy.items[1], "producer-token", mocker.sentinel.producer_lock),
    ]
