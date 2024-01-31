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
import { intervalModeNames } from './strategy-config-set-new/notice-config/notice-config';

const dataTypeLabelNames = {
  time_series: window.i18n.t('监控指标'),
  event: window.i18n.t('事件'),
  log: window.i18n.t('日志关键字'),
  alert: window.i18n.t('关联告警')
};

const signalNames = {
  abnormal: window.i18n.t('告警触发时'),
  recovered: window.i18n.t('告警恢复时'),
  closed: window.i18n.t('告警关闭时'),
  execute: window.i18n.t('执行前'),
  execute_success: window.i18n.t('执行成功'),
  execute_failed: window.i18n.t('执行失败'),
  no_data: window.i18n.t('无数据时')
};

const levelMap = {
  1: window.i18n.t('致命'),
  2: window.i18n.t('预警'),
  3: window.i18n.t('提醒')
};

const detectionTypeMap = {
  IntelligentDetect: window.i18n.t('智能异常检测'),
  Threshold: window.i18n.t('静态阈值'),
  AdvancedYearRound: window.i18n.t('同比（高级）'),
  AdvancedRingRatio: window.i18n.t('环比（高级）'),
  SimpleYearRound: window.i18n.t('同比（简易）'),
  SimpleRingRatio: window.i18n.t('环比（简易）'),
  PartialNodes: window.i18n.t('部分节点数'),
  YearRoundAmplitude: window.i18n.t('同比振幅'),
  RingRatioAmplitude: window.i18n.t('环比振幅'),
  YearRoundRange: window.i18n.t('同比区间'),
  OsRestart: window.i18n.t('主机重启'),
  ProcPort: window.i18n.t('进程端口'),
  PingUnreachable: window.i18n.t('Ping不可达算法'),
  TimeSeriesForecasting: window.i18n.t('时序预测'),
  AbnormalCluster: window.i18n.t('离群检测')
};

export const invalidTypeMap = {
  invalid_metric: window.i18n.t('监控指标不存在'),
  invalid_unit: window.i18n.t('指标和检测算法的单位类型不一致'),
  invalid_biz: window.i18n.t('策略所属空间不存在'),
  invalid_target: window.i18n.t('监控目标全部失效'),
  invalid_related_strategy: window.i18n.t('关联的策略已失效'),
  deleted_related_strategy: window.i18n.t('关联的策略已删除')
};

const dataModeNames = {
  converge: window.i18n.t('汇聚'),
  realtime: window.i18n.t('实时')
};

export default class TableStore {
  constructor(originData, bizList) {
    this.setDefaultStore();
    this.total = originData.length || 0;
    this.data = [];
    let i = 0;
    while (i < this.total) {
      const item = originData[i];
      const targetString = '';
      const objectType = item.target_object_type;
      const nodeType = item.target_node_type;
      const biz = bizList.find(v => v.id === item.bk_biz_id) || { text: '' };
      const noticeGroupList = item.notice.user_groups;
      const noticeGroupNameList = item.notice.user_group_list.map(item => item?.name);
      const intervalNotifyMode = intervalModeNames[item.notice.config.interval_notify_mode] || '';
      const queryConfig = item.items[0].query_configs[0];
      const dataTypeLabelName = dataTypeLabelNames[queryConfig.data_type_label];
      const dataMode =
        dataModeNames[
          queryConfig.agg_method === 'REAL_TIME' ||
          (queryConfig.data_type_label === 'event' && queryConfig.data_source_label === 'bk_monitor')
            ? 'realtime'
            : 'converge'
        ];
      const notifyInterval = item.notice.config.notify_interval / 60;
      const trigger = item.detects[0]?.trigger_config
        ? `${item.detects[0].trigger_config.count}/${item.detects[0].trigger_config.check_window}`
        : '--';
      const triggerConfig = item.detects[0]?.trigger_config || false;
      const signals = item.notice.signal.filter(signal => signal !== 'no_data').map(signal => signalNames[signal]);
      const { algorithms } = item.items[0];
      let levels;
      if (algorithms.length) {
        levels = algorithms
          .map(alg => alg.level)
          .filter((level, index, arr) => arr.indexOf(level, 0) === index)
          .map(level => levelMap[level]);
      } else {
        levels = [levelMap[item.detects[0].level]];
      }
      const detectionTypes = algorithms
        .map(alg => alg.type)
        .filter((type, index, arr) => arr.indexOf(type, 0) === index && !!type)
        .map(type => detectionTypeMap[type]);
      const mealNames = item.actions
        .filter((action, index, arr) => arr.map(a => a.config_id).indexOf(action.config_id, 0) === index)
        .map(action => action.config?.name || '--');
      const mealTips = item.actions.map(
        action =>
          `${action.signal
            .map(signal => (signalNames[signal] ? `${signalNames[signal]},` : ''))
            .join('')}${window.i18n.t('执行套餐')}${action.config?.name || '--'}`
      );
      this.data.push({
        id: item.id,
        bizId: item.bk_biz_id,
        bizName: biz.text,
        strategyName: item.name,
        strategyType: item.scenario,
        // firstLabelName: item.first_label_name,
        // secondLabelName: item.second_label_name,
        scenarioDisplayName: '', // 代替firstLabelName && secondLabelName
        targetNodeType: nodeType,
        objectType,
        dataOrigin: item.data_source_type,
        targetNodesCount: item.target_nodes_count,
        totalInstanceCount: item.total_instance_count,
        target: targetString,
        noticeGroupList: Array.from(new Set(noticeGroupList)), // 告警组id
        noticeGroupNameList: Array.from(new Set(noticeGroupNameList)), // 告警组名
        labels: item.labels,
        categoryList: Array.isArray(item.service_category_data) ? item.service_category_data : [],
        updator: item.update_user,
        updateTime: item.update_time.slice(0, item.update_time.indexOf('+')),
        addAllowed: item.add_allowed,
        enabled: item.is_enabled,
        legacy: item.is_legacy,
        isInvalid: item.is_invalid,
        invalidType: invalidTypeMap[item.invalid_type] || item.invalid_type,
        canDelete: item.delete_allowed,
        canEdit: item.edit_allowed,
        overflow: false,
        overflowLabel: false,
        overflowsignals: false,
        overflowdetectionTypes: false,
        overflowlevels: false,
        overflowmealNames: false,
        shieldInfo: item.shield_info,
        abnormalAlertCount: item.alert_count || 0,
        metricDescriptionList: item.metric_description_list,
        itemDescription: this.getItemDescription(item.items[0].query_configs),
        intervalNotifyMode,
        dataTypeLabelName,
        dataMode,
        notifyInterval,
        trigger,
        triggerConfig,
        recovery: item.detects[0]?.recovery_config?.check_window || '--',
        needPoll: item.notice.options.converge_config.need_biz_converge,
        noDataEnabled: item.items[0]?.no_data_config?.is_enabled || false,
        signals,
        levels,
        detectionTypes,
        mealNames,
        mealTips,
        configSource: item.config_source,
        app: item.app,
        shieldAlertCount: item.shield_alert_count || 0,
        editAllowed: !!item?.edit_allowed
      });
      i += 1;
    }
    // this.data = originData
  }

  getTableData() {
    // let ret = this.data
    // if (this.keyword.length) {
    //     const keyword = this.keyword.toLocaleLowerCase()
    //     ret = ret.filter(item => item.strategyName.toLocaleLowerCase().includes(keyword))
    // }
    // this.total = ret.length
    return this.data.slice(0, this.pageSize);
  }

  setDefaultStore() {
    this.keyword = '';
    this.page = 1;
    this.pageSize = +localStorage.getItem('__common_page_size__') || 10;
    this.pageList = [10, 20, 50, 100];
  }
  getItemDescription(itemlist) {
    if (!itemlist) {
      return {
        tip: {
          content: '--',
          delay: 200
        },
        val: '--'
      };
    }
    const res = [];
    itemlist.forEach(item => {
      const metricField = item.metric_field || '';
      const metricFieldName = item.metric_field_name || '';
      const resultTableId = item.result_table_id || '';
      const itemName = item.name || '';
      const queryString = item.query_string || ''; // 日志关键字才有这字段
      const metricMetaId = `${item.data_source_label}|${item.data_type_label}`;
      let tmp = '';
      let tips = '';
      switch (metricMetaId) {
        case 'bk_monitor|time_series':
        default:
          tmp = `${itemName}(${item.data_label || resultTableId}.${metricField})`;
          break;
        case 'bk_monitor|event':
        case 'bk_monitor|log':
          tmp = itemName;
          break;
        case 'bk_monitor|alert':
          tmp = `${window.i18n.t('监控策略')}:${itemName}`;
          break;
        case 'bk_data|time_series':
          tmp = `${metricFieldName}(${resultTableId}.${metricField})`;
          break;
        case 'bk_log_search|time_series':
          tmp = `${metricField}(${window.i18n.t('索引集')}:${itemName})`;
          tips = `<div>
          ${metricField}<span style="color:#c4c6cc;margin-left:12px">(
          ${window.i18n.t('索引集')}:${itemName})</span></div>`;
          break;
        case 'bk_log_search|log':
          tmp = `${queryString}(${window.i18n.t('索引集')}:${itemName})`;
          tips = `<div>${queryString}
            <span style="color:#c4c6cc;margin-left:12px">(${window.i18n.t('索引集')}:${itemName})</span></div>`;
          break;
        case 'custom|event':
          tmp = `${itemName}(${window.i18n.t('数据ID')}:${resultTableId})`;
          break;
        case 'custom|time_series':
          tmp = `${itemName}(${item.data_label || resultTableId}.${metricField})`;
          break;
        case 'bk_fta|alert':
        case 'bk_fta|event':
          tmp = `${window.i18n.t('告警名称')}:${itemName}`;
          break;
        case 'prometheus|time_series':
          tmp = item.promql || '';
          break;
      }
      res.push({
        tip: tips || tmp,
        val: tmp
      });
    });
    return res;
  }
}
