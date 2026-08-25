from alarm_backends.service.nodata import processor as nodata_processor
from alarm_backends.service.nodata.processor import CheckProcessor


def test_nodata_push_data_does_not_trim_check_results(mocker):
    processor = object.__new__(CheckProcessor)
    processor.strategy_id = "10"
    processor.inputs = {}
    processor.outputs = {1: [{"data": {"value": 1}}]}
    processor.strategy = mocker.MagicMock(items=[mocker.MagicMock(id=1), mocker.MagicMock(id=2)])
    push_abnormal_data = mocker.patch.object(processor, "push_abnormal_data", return_value=1)
    trim_item = mocker.patch.object(
        nodata_processor,
        "trim_item_check_results_if_trigger_idle",
        create=True,
    )
    mocker.patch.object(nodata_processor, "metrics")

    processor.push_data()

    push_abnormal_data.assert_called_once_with(processor.outputs, "10", [])
    trim_item.assert_not_called()
