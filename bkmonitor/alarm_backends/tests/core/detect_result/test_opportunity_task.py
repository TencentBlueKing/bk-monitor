from alarm_backends.core.detect_result import tasks


def test_opportunity_task_reports_trim_work_without_retry(mocker):
    stats = {
        "strategy_count": 1,
        "item_count": 2,
        "scanned_fields": 10,
        "zrem_commands": 9,
        "removed_members": 30,
    }
    mocker.patch.object(tasks, "trim_strategy_group", return_value=stats)
    mocker.patch.object(tasks, "time", mocker.Mock(time=mocker.Mock(side_effect=[105.0, 107.0, 108.0])))
    task_metrics = mocker.patch.object(tasks, "metrics")

    result = tasks.async_trim_check_result_opportunity.run("group", 100.0)

    assert result == stats
    task_metrics.CHECK_RESULT_OPPORTUNITY_TRIM_QUEUE_DELAY.observe.assert_called_once_with(5.0)
    assert task_metrics.CHECK_RESULT_OPPORTUNITY_TRIM_COUNT.labels.call_count == 3
    task_metrics.CHECK_RESULT_OPPORTUNITY_TRIM_TIME.observe.assert_called_once_with(3.0)
    task_metrics.report_all.assert_called_once_with()
