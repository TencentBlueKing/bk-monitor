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
import { jumpToDocsLink } from 'monitor-common/utils';

import store from '../store/modules/app';

export const linkMap = {
  processMonitoring: '监控平台/产品白皮书/scene-process/process_monitor_overview.md', //  主机监控-主机详情 左下角 进程监控配置指引
  /** @deprecated 20230811 该链接已不存在，先暂时保留 */
  strategyTemplate: '监控平台/产品白皮书/alarm-configurations/notify_case.md', //  新建策略 高级设置-通知模版-模板使用说明
  globalConfiguration: '监控平台/产品白皮书/alarm-configurations/notify_setting.md', //  全局配置
  Script: '监控平台/产品白皮书/integrations-metric-plugins/script_collect.md', //  插件管理 script 链接
  JMX: '监控平台/产品白皮书/integrations-metric-plugins/plugin_jmx.md', //  插件管理 JMX 链接
  Exporter: '监控平台/产品白皮书/integrations-metric-plugins/import_exporter.md', //  插件管理 exporter 链接
  DataDog: '监控平台/产品白皮书/integrations-metric-plugins/import_datadog_online.md', //  插件管理 datadog 链接
  Pushgateway: '监控平台/产品白皮书/integrations-metric-plugins/howto_bk-pull.md', //  插件管理 bk-pull 链接
  api: '监控平台/产品白皮书/integrations-metrics/custom_metrics_http.md', //  自定义上报 API
  python: '',
  quickStartDial: '监控平台/产品白皮书/scene-synthetic/synthetic_monitor.md', //  5分钟快速上手"服务拨测" 功能 前往查看
  bestPractices: '监控平台/产品白皮书/quickstart/best_practices.md', //  了解"快速接入"方法
  processMonitor: '监控平台/产品白皮书/scene-process/process_monitor_overview.md', //  了解进程的配置方法
  scriptCollect: '监控平台/产品白皮书/integrations-metric-plugins/script_collect.md', //  如何使用脚本进行服务监控？
  multiInstanceMonitor: '监控平台/产品白皮书/integrations-metrics/multi_instance_monitor.md', //  如何实现多实例采集？
  componentMonitor: '监控平台/产品白皮书/integrations-metrics/component_monitor.md', //  如何对开源组件进行监控？
  /** @deprecated 20230811 该链接已不存在，先暂时保留 */
  monitorUpdate: '监控平台/应用运维文档/安装指南/monitor_update.md', //  迁移页面内容
  homeLink: '监控平台/产品白皮书/intro/README.md', //  首页链接
  callbackLink: '监控平台/产品白皮书/alarm-handling/solutions_http_callback.md', // 告警组-回调地址链接
  fromDataSource: '监控平台/产品白皮书/alarm-configurations/bigdata_monitor.md', // 指标选择器-数据源平台的来源
  formLogPlatform: '监控平台/产品白皮书/alarm-configurations/log_monitor.md', // 指标选择器-日志平台的来源
  fromCustomRreporting: '监控平台/产品白皮书/integrations-metrics/custom_metrics_http.md', // 指标选择器-自定义上报的来源
  fromMonitor: '监控平台/产品白皮书/integrations-metrics/collect_tasks.md', // 指标选择器-监控采集的来源
  collectorConfigMd: '监控平台/产品白皮书/integrations-metrics/collect_tasks.md', // 采集产品不白皮书
  addClusterMd: '监控平台/产品白皮书/scene-k8s/k8s_monitor_overview.md', // 新增集群产品不白皮书
  apmAccess: '监控平台/产品白皮书/scene-apm/apm_monitor_overview.md', // APM 快速接入
  apmMetrics: '监控平台/产品白皮书/scene-apm/apm_metrics.md', // APM 指标说明
  alarmConfig: '监控平台/产品白皮书/scene-apm/apm_default_rules.md', // APM 告警配置
  bkLogQueryString: '日志平台/产品白皮书/data-visualization/query_string.md', // 日志平台 查询语句语法
  accessRequest: '监控平台/产品白皮书/quickstart/perm.md' // 权限申请文档
};
export const handleGotoLink = id => {
  const extraLinkMap = store.state.extraDocLinkMap;
  jumpToDocsLink(id, linkMap, extraLinkMap);
};

// 是否中文
export const isZh = () => ['zh', 'zhCN', 'zh-cn'].includes(window.i18n.locale);

// 空间类型对应map
export const SPACE_TYPE_MAP = {
  bkcc: {
    name: window.i18n.tc('业务'),
    dark: {
      color: '#478EFC',
      backgroundColor: '#2B354D'
    },
    light: {
      color: '#63656E',
      backgroundColor: '#CDE8FB'
    }
  },
  default: {
    name: window.i18n.tc('监控空间'),
    dark: {
      color: '#B3B3B3',
      backgroundColor: '#333333'
    },
    light: {
      color: '#63656E',
      backgroundColor: '#DEDEDE'
    }
  },
  bkci: {
    name: window.i18n.tc('研发项目'),
    dark: {
      color: '#F85959',
      backgroundColor: '#4C3232'
    },
    light: {
      color: '#63656E',
      backgroundColor: '#F8D8D4'
    }
  },
  bcs: {
    name: window.i18n.tc('容器项目'),
    dark: {
      color: '#FC943B',
      backgroundColor: '#453921'
    },
    light: {
      color: '#63656E',
      backgroundColor: '#FFF2C9'
    }
  },
  paas: {
    name: window.i18n.tc('蓝鲸应用'),
    dark: {
      color: '#2BB950',
      backgroundColor: '#223B2B'
    },
    light: {
      color: '#63656E',
      backgroundColor: '#D8EDD9'
    }
  },
  bksaas: {
    name: window.i18n.tc('蓝鲸应用'),
    dark: {
      color: '#2BB950',
      backgroundColor: '#223B2B'
    },
    light: {
      color: '#63656E',
      backgroundColor: '#D8EDD9'
    }
  }
};

export const SPACE_FIRST_CODE_COLOR_MAP = {
  bkcc: {
    dark: {
      backgroundColor: '#3A84FF'
    },
    light: {
      backgroundColor: '#3A84FF'
    }
  },
  default: {
    dark: {
      backgroundColor: '#63656E'
    },
    light: {
      backgroundColor: '#63656E'
    }
  },
  bkci: {
    dark: {
      backgroundColor: '#FF5656'
    },
    light: {
      backgroundColor: '#FF5656'
    }
  },
  bcs: {
    dark: {
      backgroundColor: '#FF9C01'
    },
    light: {
      backgroundColor: '#FF9C01'
    }
  },
  paas: {
    dark: {
      backgroundColor: '#2DCB56'
    },
    light: {
      backgroundColor: '#2DCB56'
    }
  },
  bksaas: {
    dark: {
      backgroundColor: '#2DCB56'
    },
    light: {
      backgroundColor: '#2DCB56'
    }
  }
};

export const DEFAULT_TIME_RANGE_LIST = [
  {
    name: window.i18n.t('近{n}分钟', { n: 5 }),
    value: 5 * 60 * 1000
  },
  {
    name: window.i18n.t('近{n}分钟', { n: 15 }),
    value: 15 * 60 * 1000
  },
  {
    name: window.i18n.t('近{n}分钟', { n: 30 }),
    value: 30 * 60 * 1000
  },
  {
    name: window.i18n.t('近{n}小时', { n: 1 }),
    value: 1 * 60 * 60 * 1000
  },
  {
    name: window.i18n.t('近{n}小时', { n: 3 }),
    value: 3 * 60 * 60 * 1000
  },
  {
    name: window.i18n.t('近{n}小时', { n: 6 }),
    value: 6 * 60 * 60 * 1000
  },
  {
    name: window.i18n.t('近{n}小时', { n: 12 }),
    value: 12 * 60 * 60 * 1000
  },
  {
    name: window.i18n.t('近{n}小时', { n: 24 }),
    value: 24 * 60 * 60 * 1000
  },
  {
    name: window.i18n.t('近 {n} 天', { n: 2 }),
    value: 2 * 24 * 60 * 60 * 1000
  },
  {
    name: window.i18n.t('近 {n} 天', { n: 7 }),
    value: 7 * 24 * 60 * 60 * 1000
  },
  {
    name: window.i18n.t('近 {n} 天', { n: 30 }),
    value: 30 * 24 * 60 * 60 * 1000
  },
  {
    name: window.i18n.t('今天'),
    value: 'today'
  },
  {
    name: window.i18n.t('昨天'),
    value: 'yesterday'
  },
  {
    name: window.i18n.t('前天'),
    value: 'beforeYesterday'
  },
  {
    name: window.i18n.t('本周'),
    value: 'thisWeek'
  }
];
export const DEFAULT_TIMESHIFT_LIST = [
  {
    id: '1h',
    name: window.i18n.t('1 小时前')
  },
  {
    id: '1d',
    name: window.i18n.t('昨天')
  },
  {
    id: '1w',
    name: window.i18n.t('上周')
  },
  {
    id: '1M',
    name: window.i18n.t('一月前')
  }
];
export const DEFAULT_REFLESH_LIST = [
  // 刷新间隔列表
  {
    name: 'off',
    id: -1
  },
  {
    name: '1m',
    id: 60 * 1000
  },
  {
    name: '5m',
    id: 5 * 60 * 1000
  },
  {
    name: '15m',
    id: 15 * 60 * 1000
  },
  {
    name: '30m',
    id: 30 * 60 * 1000
  },
  {
    name: '1h',
    id: 60 * 60 * 1000
  },
  {
    name: '2h',
    id: 60 * 2 * 60 * 1000
  },
  {
    name: '1d',
    id: 60 * 24 * 60 * 1000
  }
];
