/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { LANGUAGE_COOKIE_KEY } from './constant';
import { docCookies, rstrip } from './utils';

import type { IDocLinkData } from '@/typings';

export enum DocLinkType {
  Link = 'link',
  MonitorSplice = 'Monitor',
  Splice = 'splice',
}

/**
 * @description: 文档链接集合
 */
export const DOCS_LINK_MAP = {
  Monitor: {
    processMonitoring: 'UserGuide/ProductFeatures/scene-process/process_monitor_overview.md', //  主机监控-主机详情 左下角 进程监控配置指引
    /** @deprecated 20230811 该链接已不存在，先暂时保留 */
    strategyTemplate: '监控平台/产品白皮书/alarm-configurations/notify_case.md', //  新建策略 高级设置-通知模版-模板使用说明
    globalConfiguration: 'UserGuide/ProductFeatures/alarm-configurations/notify_setting.md', //  全局配置
    Script: 'UserGuide/ProductFeatures/integrations-metric-plugins/script_collect.md', //  插件管理 script 链接
    JMX: 'UserGuide/ProductFeatures/integrations-metric-plugins/plugin_jmx.md', //  插件管理 JMX 链接
    Exporter: 'UserGuide/ProductFeatures/integrations-metric-plugins/import_exporter.md', //  插件管理 exporter 链接
    DataDog: 'UserGuide/ProductFeatures/integrations-metric-plugins/import_datadog_online.md', //  插件管理 datadog 链接
    Pushgateway: 'UserGuide/ProductFeatures/integrations-metric-plugins/howto_bk-pull.md', //  插件管理 bk-pull 链接
    api: 'UserGuide/ProductFeatures/integrations-metrics/custom_metrics_http.md', //  自定义上报 API
    python: '',
    quickStartDial: 'UserGuide/ProductFeatures/scene-synthetic/synthetic_monitor.md', //  5分钟快速上手"服务拨测" 功能 前往查看
    bestPractices: 'UserGuide/QuickStart/best_practices.md', //  了解"快速接入"方法
    processMonitor: 'UserGuide/ProductFeatures/scene-process/process_monitor_overview.md', //  了解进程的配置方法
    processPortMonitor: 'UserGuide/ProductFeatures/scene-process/process_cmdb_monitor.md', //  了解进程和端口监控配置
    scriptCollect: 'UserGuide/ProductFeatures/integrations-metric-plugins/script_collect.md', //  如何使用脚本进行服务监控？
    multiInstanceMonitor: 'UserGuide/ProductFeatures/integrations-metrics/multi_instance_monitor.md', //  如何实现多实例采集？
    componentMonitor: 'UserGuide/ProductFeatures/integrations-metrics/component_monitor.md', //  如何对开源组件进行监控？
    /** @deprecated 20230811 该链接已不存在，先暂时保留 */
    monitorUpdate: '监控平台/应用运维文档/安装指南/monitor_update.md', //  迁移页面内容
    homeLink: 'UserGuide/Overview/README.md', //  首页链接
    callbackLink: 'UserGuide/ProductFeatures/alarm-handling/solutions_http_callback.md', // 告警组-回调地址链接
    fromDataSource: 'UserGuide/ProductFeatures/alarm-configurations/bigdata_monitor.md', // 指标选择器-数据源平台的来源
    formLogPlatform: 'UserGuide/ProductFeatures/alarm-configurations/log_monitor.md', // 指标选择器-日志平台的来源
    fromCustomRreporting: 'UserGuide/ProductFeatures/integrations-metrics/custom_metrics_http.md', // 指标选择器-自定义上报的来源
    fromMonitor: 'UserGuide/ProductFeatures/integrations-metrics/collect_tasks.md', // 指标选择器-监控采集的来源
    collectorConfigMd: 'UserGuide/ProductFeatures/integrations-metrics/collect_tasks.md', // 采集产品不白皮书
    addClusterMd: 'UserGuide/ProductFeatures/scene-k8s/k8s_monitor_overview.md', // 新增集群产品不白皮书
    apmAccess: 'UserGuide/ProductFeatures/scene-apm/apm_monitor_overview.md', // APM 快速接入
    apmMetrics: 'UserGuide/ProductFeatures/scene-apm/apm_metrics.md', // APM 指标说明
    alarmConfig: 'UserGuide/ProductFeatures/scene-apm/apm_default_rules.md', // APM 告警配置
    accessRequest: 'UserGuide/QuickStart/perm.md', // 权限申请文档
    time_series: 'UserGuide/ProductFeatures/alarm-configurations/rules.md', // 告警策略配置文档
    event: 'UserGuide/ProductFeatures/alarm-configurations/events_monitor.md', // 事件告警策略文档
    log: 'UserGuide/ProductFeatures/alarm-configurations/log_monitor.md', // 如何监控日志平台的数据
    alert: 'UserGuide/ProductFeatures/alarm-configurations/composite_monitor.md', // 关联告警策略文档
    grafanaFeatures: 'UserGuide/Appendix/grafana10.md', // grafana 功能说明文档
    queryString: 'UserGuide/ProductFeatures/data-visualization/query_string.md', // 事件检索语句模式文档
  },
  BKOther: {
    bkLogQueryString: '日志平台/产品白皮书/data-visualization/query_string.md', // 日志平台 查询语句语法
    bkDeploymentGuides: 'ZH/DeploymentGuides/7.1/index.md', // 部署指南
  },
};

const isEn = docCookies.getItem(LANGUAGE_COOKIE_KEY) === 'en';

/**
 * @description 拼接监控外其他项目文档（如日志等）链接
 * @param path 需要跳转的文档路径
 * @returns docs链接
 */
export function concatBKOtherDocsUrl(path: string) {
  return `${rstrip(window.bk_docs_site_url, '/')}/markdown/${path}`;
}

/**
 * @description 拼接监控项目文档链接
 * @param path 需要跳转的文档路径
 * @returns docs链接
 */
export function concatMonitorDocsUrl(path: string) {
  const lang = isEn ? 'EN' : 'ZH';
  const docsVersion = window.bk_doc_version || 4.7;
  return `${rstrip(window.bk_docs_site_url, '/')}/markdown/${lang}/Monitor/${docsVersion}/${path}`;
}

/**
 * @description 新文档跳转方案
 * @param {DocLinkType} type 传入 path 路径类型
 * @param {string} path 文档链接路径
 */
export function linkJump(type: DocLinkType, path: string) {
  let url = '';
  switch (type) {
    case DocLinkType.Link:
      url = path;
      break;
    case DocLinkType.Splice:
      url = concatBKOtherDocsUrl(path);
      break;
    case DocLinkType.MonitorSplice:
      url = concatMonitorDocsUrl(path);
      break;
  }
  window.open(url, '_blank');
}

/**
 * @desc 文档跳转统一方案处理入口
 * @param { string } id
 * @param { Record<string, string> } localMap
 * @param { Record<string, IDocLinkData> } remoteMap
 */
export function skipToDocsLink<T extends Record<string, IDocLinkData>>(
  id: keyof (typeof DOCS_LINK_MAP)['BKOther'] | keyof (typeof DOCS_LINK_MAP)['Monitor'] | keyof T,
  remoteMap?: T
) {
  let path = '';
  let type = DocLinkType.Link;
  // 先匹配接口返回文档链接
  if (remoteMap?.[id]) {
    const v = remoteMap?.[id];
    type = v.type;
    path = v.value;
  } else {
    const key = id as keyof (typeof DOCS_LINK_MAP)['BKOther'] | keyof (typeof DOCS_LINK_MAP)['Monitor'];
    path = DOCS_LINK_MAP.Monitor[key] || DOCS_LINK_MAP.BKOther[key] || key;
    type = DOCS_LINK_MAP.Monitor[key] ? DocLinkType.MonitorSplice : DocLinkType.Splice;
  }
  if (path) {
    linkJump(type, path);
  }
}
