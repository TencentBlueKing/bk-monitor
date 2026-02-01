### 场景化关联

如何通过业务ID关联到结果表ID？

1. 插件采集（非全局）
   1. 腾讯云插件 - 包含k8s_qcloud_exporter_的table_id
   2. 进程采集插件 - TimeSeriesGroup的time_series_group_name为process_perf/process_port，且bk_biz_id对应。
   3. 拨测插件 - TimeSeriesGroup的time_series_group_name为uptimecheck_http_xxx/uptimecheck_tcp_xxx/uptimecheck_icmp_xxx/uptimecheck_udp_xxx，xxx为业务ID。
   4. 日志关键字/snmp_trap插件 - CustomEventGroup的type为keyword，且业务ID对应。
   5. 普通插件(script/pushgateway/jmx/exporter/snmp/datadog) - {plugin_type}_xxxx_\d+，xxxx为业务ID。
2. 自定义指标
   通过CustomTSTable的time_series_group_id关联TimeSeriesGroup，然后查询对应的table_id
3. 自定义事件
   通过CustomEventGroup的event_group_id关联EventGroup，然后查询对应的table_id
4. BCS集群
   通过BCSClusterInfo的K8sMetricDataID/CustomMetricDataID/K8sEventDataID/CustomEventDataID关联DataSource
   然后通过DataSourceResultTable关联ResultTable，然后再通过table_id关联到TimeSeriesGroup/EventGroup
5. 内置数据
   1. xxxx_yyyy_built_in_time_series - cmdb关联数据
6. APM应用 - 通过ApmDataSourceConfigBase派生的四张表，通过业务ID查询dataid，然后通过dataid关联的table_id
7. 日志采集 - DataSource的type_label为log，且source_system为bk_log_search/其他日志平台app_code（可以配置为config变量），获取到bk_data_ids后，通过DataSourceResultTable关联ResultTable，然后再用resulttable中的bk_biz_id过滤出业务下的table_ids

特殊逻辑业务0，代表全局数据
1. 内置数据
2. 内置拨测
3. 内置进程采集
4. 内置系统进程采集
5. 内置主机数据
6. 插件采集 - 全局插件
7. 自监控及运营数据
8. 特殊逻辑
   1. dbm/p4等特殊主机数据
   2. apm预计算表


### DataSource分类
1. type_label: time_series
2. type_label: event
   - 包含custom_event - 自定义事件
   - 包含bcs_BCS-K8S - 集群事件
   - -?\d+_fta_xxx - 第三方告警源
   - gse_process_event_report/system_base_events - 内置事件落地
   - bk_log_search_bk_log_event - ?
3. type_label: log
   日志采集
4. type_label: bk_event
   - 1100000
   - 1100001
   - 1100002

