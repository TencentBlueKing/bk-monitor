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

const data = {
  // 主机监控
  performance: {
    // 是否无数据
    is_no_data: true,
    // 是否没有关联资源
    is_no_source: true,
    // 其他数据 如 快捷链接 新增链接 右侧图片链接 文案
    data: {
      title: '开启主机监控',
      subTitle:
        '默认录入到蓝鲸配置平台的主机，将会采集操作系统和进程相关的指标数据和事件数据，所以开启主机监控需要关联业务资源。',
      introduce: [
        '采集的指标丰富多达100个指标和8种系统事件',
        '可以按集群和模块拓扑进行数据的汇总',
        '提供默认的主机和事件策略',
      ],
      buttons: [
        {
          name: '接入主机',
          url: '',
        },
        {
          name: 'DEMO',
          url: '',
        },
      ],
      links: [
        {
          name: '快速接入',
          url: '产品白皮书/scene-host/host_monitor.md',
        },
        {
          name: '进程配置',
          url: '产品白皮书/scene-process/process_monitor_overview.md',
        },
        {
          name: '操作系统指标',
          url: '产品白皮书/scene-host/host_metrics.md',
        },
        {
          name: '进程指标',
          url: '产品白皮书/scene-process/process_metrics.md',
        },
        {
          name: '操作系统事件',
          url: '产品白皮书/scene-host/host_events.md',
        },
      ],
    },
  },
  // 服务拨测
  'uptime-check': {
    is_no_data: true,
    is_no_source: true,
    data: {
      title: '开启综合拨测',
      subTitle:
        '拨测是主动探测应用可用性的监控方式，通过拨测节点对目标进行周期性探测，通过可用性和响应时间来度量目标的状态。帮助业务主动发现问题和提升用户体验。',
      introduce: [
        '支持HTTP(s)、TCP、UDP、ICMP协议',
        '提供单点可用率、响应时长、期望响应码等指标',
        '提供节点TOP和地图等图表',
      ],
      buttons: [
        {
          name: '新建拨测',
          url: '#/uptime-check/task-add',
        },
        {
          name: 'DEMO',
          url: '',
        },
      ],
      links: [
        {
          name: '开启综合拨测',
          url: '产品白皮书/scene-synthetic/synthetic_monitor.md',
        },
        {
          name: '拨测指标说明',
          url: '产品白皮书/scene-synthetic/synthetic_metrics.md',
        },
        {
          name: '拨测策略说明',
          url: '产品白皮书/scene-synthetic/synthetic_default_rules.md',
        },
      ],
    },
  },
  // 应用监控
  'apm-home': {
    is_no_data: true,
    is_no_source: true,
    data: {
      title: '开启APM',
      subTitle:
        'APM即应用性能监控，通过Trace数据分析应用中各服务的运行情况，尤其是在微服务和云原生情况下非常依赖Trace数据的发现来解决接口级别的调用问题。',
      introduce: [
        '通过应用拓扑图，可以了解服务之间调用的关系和出现问题的节点',
        '通过调用次数、耗时、错误率等指标可以了解服务本身的运行状况',
        '可以添加告警即时的发现问题',
      ],
      buttons: [
        {
          name: '新建应用',
          url: '#/apm/application/add',
        },
        {
          name: 'DEMO',
          url: '',
        },
      ],
      links: [
        {
          name: 'button-开启APM',
          url: '产品白皮书/scene-apm/apm_monitor_overview.md',
        },
        {
          name: 'APM指标说明',
          url: '产品白皮书/scene-apm/apm_metrics.md',
        },
        {
          name: 'APM策略说明',
          url: '产品白皮书/scene-apm/apm_default_rules.md',
        },
      ],
    },
  },
  // 容器监控
  k8s: {
    is_no_data: true,
    is_no_source: true,
    data: {
      title: '开启Kubernetes监控',
      subTitle:
        '基于Kubernetes的云原生场景，提供了围绕云平台本身及上的应用数据监控解决方案。兼容了Prometheus的使用并且解决了原本的一些短板问题。开启容器监控需要将Kubernetes接入到蓝鲸容器管理平台中。',
      introduce: [
        '提供开箱即用的K8s服务组件的各种监控视角',
        '兼容serviceMonitor、podMonitor的使用',
        '提供了Events、Log、Metrics的采集方案',
        '提供远程服务注册的方式',
        '提供本地拉取和均衡拉取的能力',
      ],
      buttons: [
        {
          name: '接入Kubernetes',
          url: '',
        },
        {
          name: 'DEMO',
          url: '',
        },
      ],
      links: [
        {
          name: '开启容器监控',
          url: '产品白皮书/scene-k8s/k8s_monitor_overview.md',
        },
        {
          name: '容器指标说明',
          url: '产品白皮书/scene-k8s/k8s_metrics.md',
        },
        {
          name: 'K8s策略说明',
          url: '产品白皮书/scene-k8s/k8s_default_rules.md',
        },
      ],
    },
  },
  // 自定义场景
  'custom-scenes': {
    is_no_data: true,
    is_no_source: true,
    data: {
      title: '自定义场景',
      subTitle:
        '自定义场景是除了平台自带的场景之外可以根据监控需求来自定义监控场景，平台提供了快速定义场景的能力，从数据源接入到数据可视化、关联功能联动都可以很快速的完成。',
      introduce: [
        '基于数据源提供默认的数据可视化',
        '支持快速进行数据查看和检验',
        '支持指标分组和标签配置',
        '支持变量过滤和数据分组',
      ],
      buttons: [
        {
          name: '开始自定义',
          url: '',
        },
        {
          name: 'DEMO',
          url: '',
        },
      ],
    },
  },
  // 数据采集
  'collect-config': {
    is_no_data: true,
    is_no_source: true,
    data: {
      title: '开始数据采集',
      subTitle:
        '数据采集是通过下发监控插件或配置来实现数据采集，并且提供插件和配置的全生命周期管理，所以依赖服务器安装bkmonitorbeat采集器。',
      introduce: ['结合插件提供本地和远程采集两种方式', '提供基于配置平台节点的动态扩缩容', '提供物理和容器环境的采集'],
      buttons: [
        {
          name: '新建数据采集',
          url: '#/collect-config/add',
        },
        {
          name: 'DEMO',
          url: '',
        },
      ],
      links: [
        {
          name: '什么是指标和维度',
          url: '产品白皮书/integrations-metrics/what_metrics.md',
        },
        {
          name: '开始指标数据采集',
          url: '产品白皮书/integrations-metrics/collect_tasks.md',
        },
        {
          name: '插件制作快速入门',
          url: '产品白皮书/integrations-metric-plugins/plugins.md',
        },
      ],
    },
  },
};
export default data;
