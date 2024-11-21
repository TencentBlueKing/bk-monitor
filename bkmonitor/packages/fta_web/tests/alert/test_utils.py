# -*- coding: utf-8 -*-
from fta_web.alert import utils


def test_process_metric_string():
    """测试 process_metric_string"""
    # key是原始值，value是预期的值
    testcases = {
        '指标ID : bk_monitor.corefile-gse AND corefile': 'event.metric : bk_monitor.corefile-gse* AND corefile',
        'event.metric: "bk_monitor.corefile-gse" AND corefile': 'event.metric : bk_monitor.corefile-gse* AND corefile',
        'event.metric: "bk_monitor.corefile-gse" OR corefile': 'event.metric : bk_monitor.corefile-gse* OR corefile',
        '-event.metric: "bk_monitor.corefile-gse" OR corefile': '-event.metric : bk_monitor.corefile-gse* OR corefile',
        'not event.metric: "bk_monitor.corefile-gse" OR corefile': 'not event.metric : bk_monitor.corefile-gse* OR'
        ' corefile',
        '指标ID : "bk_monitor.corefile-gse" AND corefile': 'event.metric : bk_monitor.corefile-gse* AND corefile',
        '-指标ID : "bk_monitor.corefile-gse" AND corefile': '-event.metric : bk_monitor.corefile-gse* AND corefile',
        '指标ID : "bk_monitor.corefile-gse" AND corefile AND 处理阶段 : 已通知': 'event.metric : bk_monitor.corefile-gse* '
        'AND corefile AND 处理阶段 : 已通知',
        '处理阶段 : 已通知 AND 指标ID : "bk_monitor.corefile-gse" AND \
        corefile': '处理阶段 : 已通知 AND event.metric : bk_monitor.corefile-gse* AND corefile',
        '((指标ID : bk_monitor.corefile-gse AND corefile)) OR -指标ID : "bk_log_search.index_set.53"': '((event.metric :'
        ' bk_monitor.corefile-gse* AND corefile)) OR -event.metric : bk_log_search.index_set.53*',
        '指标ID : bk_monitor.event.metric AND -指标ID : "bk_log_search*"': 'event.metric : bk_monitor.event.metric* AND '
        '-event.metric : bk_log_search*',
        '处理阶段 : 已屏蔽 OR (指标ID : bk_monitor.event.metric AND -指标ID : "bk_log_search*" ) AND 处理阶段 : 已通知': '处理'
        '阶段 : 已屏蔽 OR (event.metric : bk_monitor.event.metric* AND -event.metric : bk_log_search* ) AND 处理阶段 : 已通知',
    }
    for query_string, expected_value in testcases.items():
        result = utils.process_metric_string(query_string)
        assert result == expected_value
