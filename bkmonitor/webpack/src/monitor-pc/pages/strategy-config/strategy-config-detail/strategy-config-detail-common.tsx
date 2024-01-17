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
import { Component, Inject, Prop, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import CustomTab from '../../../../fta-solutions/pages/setting/set-meal/set-meal-add/components/custom-tab';
import { templateSignalName } from '../../../../fta-solutions/pages/setting/set-meal/set-meal-add/meal-content/meal-content-data';
import SetMealAddStore from '../../../../fta-solutions/store/modules/set-meal-add';
import { getConvergeFunction } from '../../../../monitor-api/modules/action';
import { strategySnapshot } from '../../../../monitor-api/modules/alert';
import { listCalendar } from '../../../../monitor-api/modules/calendar';
import { listActionConfig, listUserGroup } from '../../../../monitor-api/modules/model';
import {
  getMetricListV2,
  getScenarioList,
  getStrategyV2,
  getTargetDetail,
  strategyLabelList
} from '../../../../monitor-api/modules/strategies';
import { deepClone, random, transformDataKey } from '../../../../monitor-common/utils/utils';
import PromqlEditor from '../../../../monitor-ui/promql-editor/promql-editor';
import HistoryDialog from '../../../components/history-dialog/history-dialog';
import { ISpaceItem } from '../../../types';
import AlarmGroupDetail from '../../alarm-group/alarm-group-detail/alarm-group-detail';
import CommonNavBar from '../../monitor-k8s/components/common-nav-bar';
import { handleSetTargetDesc } from '../common';
import StrategyTemplatePreview from '../strategy-config-set/strategy-template-preview/strategy-template-preview.vue';
import StrategyVariateList from '../strategy-config-set/strategy-variate-list/strategy-variate-list.vue';
import StrategyView from '../strategy-config-set/strategy-view/strategy-view';
import { IValue as IAlarmItem } from '../strategy-config-set-new/alarm-handling/alarm-handling';
import { signalNames } from '../strategy-config-set-new/alarm-handling/alarm-handling-list';
import { ChartType } from '../strategy-config-set-new/detection-rules/components/intelligent-detect/intelligent-detect';
import { IModelData } from '../strategy-config-set-new/detection-rules/components/time-series-forecast/time-series-forecast';
import AiopsMonitorData from '../strategy-config-set-new/monitor-data/aiops-monitor-data';
import { IFunctionsValue } from '../strategy-config-set-new/monitor-data/function-select';
import {
  hasExcludeNoticeWayOptions,
  INoticeValue,
  intervalModeNames
} from '../strategy-config-set-new/notice-config/notice-config';
import { levelList, noticeMethod } from '../strategy-config-set-new/type';
import {
  dataModeType,
  IDetectionConfig,
  IScenarioItem,
  MetricDetail,
  MetricType
} from '../strategy-config-set-new/typings';

import DetectionRulesDisplay from './components/detection-rules-display';
import MetricListItem from './components/metric-list-item';
import StrategyTargetTable from './strategy-config-detail-table.vue';
import { transformLogMetricId } from './utils';

import './strategy-config-detail-common.scss';

interface IAnalyzingConditions {
  triggerConfig: {
    count: number;
    checkWindow: number;
    checkType: string;
  };
  recoveryConfig: {
    checkWindow: number;
  };
  noDataConfig: {
    continuous: number;
    isEnabled: boolean;
    dimensions: unknown[];
    level: number;
  };
  timeRange: string[];
}

interface IBaseInfo {
  name: string; // 策略名
  bizName: string; // 业务名
  enabled: string; // 是否启用
  scenario: string; // 监控对象
  labels: string[]; // 标签
  priority: number | null | string; // 优先级
}
type BaseInfoRequire = {
  name: string;
  key: keyof Omit<IBaseInfo, 'labels'>;
};

type EditModeType = 'Source' | 'Edit';

@Component({
  components: {
    StrategyTargetTable
  }
})
export default class StrategyConfigDetailCommon extends tsc<{}> {
  // 策略Id
  @Prop({ type: [String, Number] }) readonly id: string | number;

  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('authorityMap') authorityMap;
  @ProvideReactive('strategyId') strategyId = 0;

  strategyView: { rightWidth: string | number; range: number[]; isActive: boolean; show: boolean } = {
    rightWidth: '33%',
    range: [300, 1200],
    isActive: false,
    show: true
  };

  /** 导航面包屑 */
  routeList = [
    {
      id: 'strategy-config',
      name: window.i18n.tc('策略配置')
    },
    {
      id: '',
      name: 'loading...'
    }
  ];
  /* 告警组 */
  alarmGroupList = [];
  /* 面包屑 */
  navName = 'loading...';
  /** 详情信息 */
  detailData: Record<string, any> = {};
  /** 监控目标 */
  targetDetail: Record<string, any> = {};
  /** 选中的监控目标表格展示数据 */
  targetsTableData: any[] = [];

  /** 展示选中的监控目标 */
  showTargetTable = false;

  /** 监控目标数据 */
  targetsDesc = {
    message: '',
    subMessage: ''
  };

  /** 告警等级 */
  alertLevel = 1;
  /** 告警等级列表 */
  levelList = [
    { id: 1, name: window.i18n.tc('致命'), icon: 'icon-danger' },
    { id: 2, name: window.i18n.tc('预警'), icon: 'icon-mind-fill' },
    { id: 3, name: window.i18n.tc('提醒'), icon: 'icon-tips' }
  ];

  /** 基本信息 */
  baseInfo: IBaseInfo = {
    name: '',
    bizName: '',
    enabled: '',
    scenario: '',
    labels: [],
    priority: null
  };
  /** 自定义标签数据 */
  customLabelsList: string[] = [];
  baseInfoRequireList: BaseInfoRequire[] = [
    {
      key: 'bizName',
      name: window.i18n.tc('所属')
    },
    {
      key: 'scenario',
      name: window.i18n.tc('监控对象')
    },
    {
      key: 'name',
      name: window.i18n.tc('策略名称')
    },
    {
      key: 'priority',
      name: window.i18n.tc('优先级')
    },
    {
      key: 'enabled',
      name: window.i18n.tc('是否启用')
    }
  ];
  /** 监控对象列表 */
  scenarioList: IScenarioItem[] = [];

  /** 表达式 */
  expression = '';
  /** 表达式函数 */
  expFunctions: IFunctionsValue[] = [];

  // 指标数据
  metricData: MetricDetail[] = [];
  // 检测规则数据
  detectionConfig: IDetectionConfig = {
    unit: '',
    unitType: '', // 单位类型
    unitList: [],
    connector: 'and',
    data: []
  };
  // 判断条件数据
  analyzingConditions: IAnalyzingConditions = {
    triggerConfig: {
      // 触发条件
      count: 1,
      checkWindow: 5,
      checkType: 'total'
    },
    recoveryConfig: {
      // 恢复条件
      checkWindow: 5
    },
    noDataConfig: {
      continuous: 10,
      isEnabled: true,
      dimensions: [],
      level: 2
    },
    timeRange: ['00:00:00', '23:59:59']
  };
  // 告警处理
  actionsData: IAlarmItem[] = [];
  // 通知设置。
  noticeData: INoticeValue = {
    config_id: 0, // 套餐id
    user_groups: [], // 告警组
    signal: ['abnormal'], // 触发信号
    options: {
      converge_config: {
        need_biz_converge: true // 告警风暴开关
      },
      noise_reduce_config: {
        dimensions: [],
        count: 0,
        is_enabled: false
      }
    },
    config: {
      // 高级配置
      interval_notify_mode: 'standard',
      notify_interval: 120,
      // 该项为后端返回后执行一次 computed 方法。
      template: [
        { signal: 'abnormal', message_tmpl: '', title_tmpl: '' },
        { signal: 'recovered', message_tmpl: '', title_tmpl: '' },
        { signal: 'closed', message_tmpl: '', title_tmpl: '' },
        { signal: 'ack', message_tmpl: '', title_tmpl: '' }
      ]
    }
  };

  localExpress = '';
  // 监控数据模式 converge: 汇聚 realtime: 实时
  dataMode: dataModeType = 'converge';
  strategyStatusMap = {
    UPDATED: window.i18n.t('（已修改）'),
    DELETED: window.i18n.t('（已删除）'),
    UNCHANGED: ''
  };
  strategyStatus = '';
  // 套餐列表
  actionConfigMap: { [propName: string | number]: { name?: string; plugin_name?: string } } = {};
  actionsKey = random(8);
  defenseMap: { [propName: string]: { key: string; name: string } } = {};
  templateActive = '';
  // 告警模板数据
  templateData: {
    signal: string;
    message_tmpl: string;
    title_tmpl: string;
  } = { signal: 'abnormal', message_tmpl: '', title_tmpl: '' };
  // 告警组想详情
  alarmGroupDetail: { id: number; show: boolean } = {
    id: 0,
    show: false
  };
  variateListShow = false;
  isShowTemplate = false;
  loading = false;

  /** 监控目标 */
  checkedTarget: Record<string, any> = { target_detail: [] };

  /* 维度数据（用于展示维度中文名称） */
  dimensionsMap: { [propName: string]: { id?: string; name?: string } } = {};

  /** 智能检测算法图表类型 */
  localAiopsChartType: ChartType = 'none';

  /** 时序预测 | 智能检测算法模型方案描述 */
  aiopsModelDescMd = '';
  /* aiops 使用说明 */
  aiopsModelDocMd = '';
  /* aiops 模型名称 */
  aiopsModelName = '';

  /** 生效时间 */
  timeRanges = [];
  /** 关联日历 */
  calendars = [];
  /** 关联日历可选项列表 */
  calendarList = [];
  /* source数据 此数据与指标数据隔离 */
  sourceData = {
    /* promql */
    sourceCode: '',
    /* agg_interval */
    step: 'auto'
  };
  editMode: EditModeType = 'Edit';
  /* 是否为场景智能检测 */
  isMultivariateAnomalyDetection = false;

  /** 预览图描述文档  智能检测算法 | 时序预测 需要展示算法说明 */
  get aiopsModelDescMdGetter() {
    const needMdDesc = this.detectionConfig.data.some(item =>
      ['IntelligentDetect', 'TimeSeriesForecasting', 'AbnormalCluster'].includes(item.type)
    );
    return needMdDesc
      ? [
          {
            name: this.aiopsModelName,
            instruction: this.aiopsModelDescMd,
            document: this.aiopsModelDocMd
          }
        ]
      : [];
  }
  /** 当前告警等级 */
  get currentAlertLevel() {
    return this.levelList.find(item => item.id === this.alertLevel);
  }

  get bizList(): ISpaceItem[] {
    return this.$store.getters.bizList;
  }

  // 已选中的维度合法列表
  get legalDimensionList() {
    return this.metricData.reduce(
      (pre, cur) =>
        cur.agg_dimension?.length > pre.length
          ? cur.dimensions.filter(set => cur.agg_dimension.includes(set.id as any))
          : pre,
      []
    );
  }
  get rightWidth() {
    // eslint-disable-next-line no-nested-ternary
    return this.strategyView.show
      ? typeof this.strategyView.rightWidth === 'string'
        ? this.strategyView.rightWidth
        : `${this.strategyView.rightWidth}px`
      : '0px';
  }

  get historyList() {
    return [
      { label: this.$t('创建人'), value: this.detailData.create_user || '--' },
      { label: this.$t('创建时间'), value: this.detailData.create_time || '--' },
      { label: this.$t('最近更新人'), value: this.detailData.update_user || '--' },
      { label: this.$t('修改时间'), value: this.detailData.update_time || '--' }
    ];
  }

  // 模板类型
  get templateTypes() {
    return (
      this.noticeData.config.template?.map(item => ({
        key: item.signal,
        label: templateSignalName[item.signal]
      })) || []
    );
  }

  // 变量列表
  get variateList() {
    return SetMealAddStore.getVariables;
  }

  // 通知方式
  get noticeWayList() {
    return SetMealAddStore.noticeWayList;
  }

  /**
   * @description 是否显示检测算法
   */
  get showDetectionConfig() {
    if (this.isMultivariateAnomalyDetection) {
      return false;
    }
    return this.metricData[0]?.canSetDetEctionRules || this.editMode === 'Source';
  }

  created() {
    this.loading = true;
    const promiseList = [];
    this.getActionConfigList();
    this.getAlarmGroupList();
    // promiseList.push(this.getActionConfigList());
    promiseList.push(this.getDefenseList());
    promiseList.push(this.getScenarioList());
    promiseList.push(this.getLabelListApi());
    promiseList.push(this.getCalendarList());
    if (!SetMealAddStore.getMessageTemplateList.length) {
      promiseList.push(SetMealAddStore.getVariableDataList());
    }
    if (!SetMealAddStore.getNoticeWayList.length) {
      promiseList.push(SetMealAddStore.getNoticeWay());
    }
    promiseList.push(this.getStrategyConfigDetail(this.id));
    Promise.all(promiseList)
      .then(() => {
        this.handleDisplaybackDetail();
      })
      .catch(err => {
        console.log(err);
      })
      .finally(() => (this.loading = false));
  }

  mounted() {
    this.strategyView.rightWidth = this.$el.clientWidth * 0.33;
  }
  // 获取告警组数据
  async getAlarmGroupList() {
    const data = await listUserGroup().catch(() => []);
    this.alarmGroupList = data.map(item => ({
      id: item.id,
      name: item.name,
      receiver: item.users?.map(rec => rec.display_name) || []
    }));
  }

  /** 获取告警组名 */
  getAlarmGroupByID(id: number) {
    return this.alarmGroupList.find(item => item.id === id)?.name || id;
  }
  /**
   * 获取通知方式
   * @param list 通知方式列表
   * @param userGroups 告警组列表
   */
  getNoticeMethodName(list, userGroups) {
    const assignMode = [...list];
    if (userGroups?.length) {
      assignMode.push('only_notice');
    }
    return noticeMethod
      .filter(item => assignMode.includes(item.value))
      .map(item => item.name)
      .join(' > ');
  }

  /**
   * 获取日历列表
   */
  async getCalendarList() {
    const params = {
      page: 1,
      page_size: 1000
    };
    const data = await listCalendar(params).catch(() => null);
    if (data) {
      this.calendarList = data.data.map(item => ({
        id: item.id,
        name: item.name
      }));
    }
    return data;
  }

  /**
   * 处理详情数据回显数据
   */
  handleDisplaybackDetail() {
    /** 基本信息 */
    this.getBaseInfo(this.detailData);
    this.targetsDesc = handleSetTargetDesc(
      this.targetDetail.target_detail,
      this.metricData[0]?.targetType,
      this.metricData[0]?.objectType,
      this.checkedTarget.node_count,
      this.checkedTarget.instance_count
    );
    /** 监控目标数据 */
    this.targetsTableData = !!this.targetDetail.detail ? transformDataKey(this.targetDetail.detail) : null;
    /** 同级别算法关系 */
    const {
      detects: [{ connector, level }]
    } = this.detailData;
    this.detectionConfig.connector = connector;
    /** 告警等级 */
    this.alertLevel = level;
  }

  /** 获取标签列表数据 */
  getLabelListApi() {
    const params = {
      strategy_id: 0
    };
    strategyLabelList(params).then(res => {
      this.customLabelsList = res.custom.map(item => item.id.replace(/\//g, ''));
    });
  }

  /**
   * @description 处理查询项数据
   * @param srcData
   * @returns
   */
  async handleQueryConfigData(srcData = this.detailData) {
    const [{ expression, query_configs: queryConfigs, functions = [], algorithms }] = srcData.items;
    if (algorithms?.[0]?.type === MetricType.MultivariateAnomalyDetection) {
      const curMetricData = new MetricDetail({
        targetType: this.targetDetail?.node_type,
        objectType: this.targetDetail?.instance_type,
        sceneConfig: {
          algorithms,
          query_configs: queryConfigs
        }
      } as any);
      this.metricData.push(curMetricData);
      this.isMultivariateAnomalyDetection = true;
      return;
    }
    const { metric_type } = srcData;
    const isPromql = queryConfigs?.[0]?.data_source_label === 'prometheus';
    if (isPromql) {
      const queryConfig = queryConfigs[0];
      this.editMode = 'Source';
      this.sourceData.sourceCode = queryConfig.promql;
      this.sourceData.step = queryConfig.agg_interval;
      return;
    }
    this.expression = expression;
    this.expFunctions = functions || [];
    const { metric_list: metricList = [] } = await getMetricListV2({
      // page: 1,
      // page_size: queryConfigs.length,
      conditions: [{ key: 'metric_id', value: queryConfigs.map(item => transformLogMetricId(item)) }]
    }).catch(() => ({}));
    this.metricData = queryConfigs.map(
      ({
        data_source_label,
        data_type_label,
        result_table_id,
        unit,
        index_set_id,
        functions,
        intelligent_detect,
        // eslint-disable-next-line camelcase
        metric_field,
        metric_id,
        agg_method,
        agg_condition = [],
        agg_dimension = [],
        agg_interval = 60,
        alias,
        query_string,
        custom_event_name,
        bkmonitor_strategy_id
      }) => {
        // eslint-disable-next-line camelcase
        const curMetric = metricList?.find(set => set.metric_id === metric_id) || {
          data_source_label,
          data_type_label,
          metric_field,
          metric_field_name: metric_field,
          metric_id,
          result_table_id,
          unit,
          index_set_id,
          query_string,
          custom_event_name,
          bkmonitor_strategy_id,
          dimensions: []
        };
        // eslint-disable-next-line camelcase
        this.dataMode =
          agg_method === 'REAL_TIME' || (data_type_label === 'event' && data_source_label === 'bk_monitor')
            ? 'realtime'
            : 'converge';
        return new MetricDetail({
          ...curMetric,
          agg_method,
          agg_condition,
          agg_dimension,
          agg_interval,
          alias: (alias || '').toLocaleLowerCase(),
          level: srcData.detects?.[0].level,
          targetType: this.targetDetail?.node_type,
          objectType: this.targetDetail?.instance_type,
          query_string,
          functions: functions || [],
          intelligent_detect,
          metric_type,
          logMetricList: metricList
        });
      }
    );
    this.detectionConfig.unitType = this.metricData[0]?.unit || '';
    /* 获取维度名称（无数据维度） */
    this.metricData.forEach(item => {
      item.dimensions?.forEach(dim => {
        this.dimensionsMap[dim.id] = dim as any;
      });
    });
  }
  // 获取套餐数据
  async getActionConfigList() {
    const data = await listActionConfig({
      with_advance_fields: 'no'
    }).catch(() => []);
    data.forEach(item => {
      this.actionConfigMap[item.id] = item;
    });
    this.actionsKey = random(8);
  }

  // 获取防御动作列表
  async getDefenseList() {
    const data = await getConvergeFunction().catch(() => []);
    data.forEach(item => {
      this.defenseMap[item.key] = item;
    });
  }

  // 获取监控对象数据
  getScenarioList() {
    return getScenarioList().then(data => {
      this.scenarioList = data;
    });
  }
  /**
   * @description 策略详情数据获取
   * @param id
   */
  async getStrategyConfigDetail(id) {
    // 策略快照start
    this.strategyId = 0;
    const { fromEvent } = this.$route.query;
    let snapshotRes: { strategy_status?: string; name?: string; id?: number } = {};
    if (fromEvent) {
      snapshotRes = await strategySnapshot({ id });
      this.strategyStatus = snapshotRes.strategy_status;
      const navName = `${this.$t('策略名')}: ${snapshotRes.name}${this.strategyStatusMap[snapshotRes.strategy_status]}`;
      this.$store.commit('app/SET_NAV_TITLE', navName);
      this.navName = navName;
    }
    this.strategyId = snapshotRes?.id || id;
    // 策略快照end
    const targetDetail = await getTargetDetail({ strategy_ids: [this.strategyId] }).catch(() => ({}));
    const strategyDetail = snapshotRes.name
      ? snapshotRes
      : await getStrategyV2({ id: this.strategyId }).catch(() => ({}));
    this.detailData = strategyDetail;
    this.detectionConfig.data = strategyDetail?.items?.[0]?.algorithms?.filter(item => !!item.type) || [];
    this.detectionConfig.unit = strategyDetail?.items?.[0]?.algorithms?.[0]?.unit_prefix || '';
    const strategyTarget = targetDetail?.[this.strategyId];
    const filed = strategyDetail?.items?.[0]?.target?.[0]?.[0]?.field || '';
    const targetType = strategyTarget?.node_type || '';
    let targetList = strategyDetail?.items?.[0]?.target?.[0]?.[0]?.value || [];
    // 对旧版的策略target进行特殊处理
    if (targetType === 'INSTANCE' && filed === 'bk_target_ip') {
      targetList = targetList.map(item => ({ ...item, ip: item.bk_target_ip, bk_cloud_id: item.bk_target_cloud_id }));
    }
    targetList.length && (targetList[0].instances_count = strategyTarget?.instance_count || 0);
    this.targetDetail = { ...strategyTarget, detail: strategyTarget?.target_detail, target_detail: targetList };
    await this.handleQueryConfigData();
    await this.handleProcessData({
      ...strategyDetail,
      targetDetail: this.targetDetail
    });
  }

  async handleProcessData(data) {
    this.getAnalyzingData(data);
    this.getActionsData(data);
    this.getNoticeConfigData(data);
  }

  /**
   * @description 处理基本信息数据
   * @param data
   */
  getBaseInfo(data: Record<string, any>) {
    const bizItem = this.bizList.find(item => item.id === data.bk_biz_id);
    this.baseInfo = {
      name: data.name ?? '',
      bizName: bizItem?.text ?? '',
      enabled: this.$tc(data.is_enabled ? '是' : '否'),
      labels: data.labels.map(item => item.replace(/\//g, ' : ')),
      scenario: this.findTreeItem(this.scenarioList, data.scenario)?.name ?? '',
      priority: data.priority ?? null
    };
    if (!this.strategyStatus) {
      this.navName = `${this.$t('策略名')}: ${this.baseInfo.name}`;
    }
    const leng = this.routeList.length;
    const theLastOne = this.routeList[leng - 1];
    theLastOne.name = this.baseInfo.name;
  }

  /**
   * @description 查找treeData
   * @param treeData
   * @param id
   * @returns
   */
  findTreeItem(treeData, id) {
    const fn = data => {
      for (const item of data) {
        if (item.id === id) return item;
        if (!!item.children?.length) {
          const res = fn(item.children);
          if (!!res) return res;
        }
      }
    };
    const res = fn(treeData);
    return res;
  }
  /**
   * @description 获取判断条件数据
   * @param data
   */
  getAnalyzingData(data) {
    const [detect] = data.detects;
    const [item] = data.items;
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { start_time, end_time } = data.notice?.options || {};
    this.analyzingConditions.timeRange = start_time && end_time ? [start_time, end_time] : [];
    this.analyzingConditions.triggerConfig = {
      ...this.analyzingConditions.triggerConfig,
      count: detect.trigger_config.count || 0,
      checkWindow: detect.trigger_config.check_window || 0
    };
    this.analyzingConditions.recoveryConfig = {
      checkWindow: detect.recovery_config.check_window || 0
    };
    this.analyzingConditions.noDataConfig = {
      continuous: item.no_data_config.continuous || 0,
      isEnabled: item.no_data_config.is_enabled || false,
      dimensions: item.no_data_config.agg_dimension || [],
      level: item.no_data_config.level || 2
    };
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { time_ranges, calendars } = detect.trigger_config.uptime || {};
    this.timeRanges = time_ranges ? time_ranges : [];
    this.calendars = calendars ? calendars : [];
  }
  /**
   * @description 获取告警处理数据
   * @param data
   */
  getActionsData(data) {
    const { actions } = data;
    this.actionsData = actions.map(item => ({
      ...item,
      options: {
        converge_config: {
          ...item.options.converge_config,
          timedelta: item.options.converge_config.timedelta / 60
        }
      }
    }));
  }

  // 获取通知设置数据
  getNoticeConfigData(data) {
    const { notice } = data;
    this.noticeData = {
      ...notice,
      config: {
        ...notice.config,
        notify_interval: notice.config.notify_interval / 60
      },
      options: {
        ...notice.options,
        converge_config: {
          need_biz_converge: notice.options.converge_config.need_biz_converge
        },
        exclude_notice_ways: {
          closed: [],
          recovered: [],
          ...notice.options?.exclude_notice_ways
        },
        noise_reduce_config: {
          dimensions: notice.options?.noise_reduce_config?.dimensions || [],
          is_enabled: notice.options?.noise_reduce_config?.is_enabled || false,
          count: notice.options?.noise_reduce_config?.count || 10
        },
        chart_image_enabled: !!notice.options?.chart_image_enabled
      }
    };
    this.templateActive = this.noticeData.config.template[0].signal;
    this.templateData = deepClone(this.noticeData.config.template[0]);
  }

  handleMouseDown(e) {
    const node = e.target;
    const { parentNode } = node;

    if (!parentNode) return;

    const nodeRect = node.getBoundingClientRect();
    const rect = parentNode.getBoundingClientRect();
    document.onselectstart = () => false;
    document.ondragstart = () => false;
    const handleMouseMove = event => {
      this.strategyView.isActive = true;
      const [min, max] = this.strategyView.range;
      const newWidth = rect.right - event.clientX + nodeRect.width;
      if (newWidth < min) {
        this.strategyView.rightWidth = min;
        this.strategyView.show = false;
      } else {
        this.strategyView.rightWidth = Math.min(newWidth, max);
      }
    };
    const handleMouseUp = () => {
      this.strategyView.isActive = false;
      document.body.style.cursor = '';
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.onselectstart = null;
      document.ondragstart = null;
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }

  // 切换告警类型
  handleChangeTemplate(v: string) {
    this.templateActive = v;
    this.templateData = deepClone(this.noticeData.config.template.find(item => item.signal === v));
  }

  // 展示变量列表
  handleShowVariateList() {
    this.variateListShow = true;
  }

  // 展示模板预览
  handleShowTemplate() {
    if (!this.templateData.message_tmpl) return;
    this.isShowTemplate = true;
  }

  // 跳转到告警组
  handleEditAlarmGroup(id) {
    this.alarmGroupDetail.show = false;
    this.$router.push({
      name: 'alarm-group-edit',
      params: {
        id,
        strategyId: `${this.strategyId}`
      }
    });
  }

  // 告警组详情
  handleSelcetAlarmGroup(id: number) {
    this.alarmGroupDetail.id = id;
    this.alarmGroupDetail.show = true;
  }

  /** 跳转编辑策略 */
  handleToEdit() {
    this.$router.push({
      name: 'strategy-config-edit',
      params: {
        id: String(this.strategyId || this.id)
      }
    });
  }

  /** 查看选中的监控目标 */
  handleShowTargetTable() {
    this.showTargetTable = true;
  }

  /** 智能检测算法模型数据变更 */
  handleModelChange(data: IModelData) {
    this.aiopsModelName = data.name || '';
    this.aiopsModelDescMd = data.instruction || '';
    this.aiopsModelDocMd = data.document || '';
  }
  /** 智能检测算法图表类型 */
  handleAiopsChartType(type: ChartType) {
    this.localAiopsChartType = type;
  }

  render() {
    const panelItem = (title: string, content: any, style = {}, titleRight?: any) => (
      <div
        class='panel'
        style={style}
      >
        <div class='panel-title'>
          <span class='title'>{title}</span>
          {titleRight ? <span class='title-right'>{titleRight}</span> : undefined}
        </div>
        <div class='panel-content'>{content}</div>
      </div>
    );

    const commonItem = (title: any = '', content: any = '', style = {}, contentStyle = {}) => (
      <div
        class='comm-item'
        style={style}
      >
        <div
          class='comm-item-title'
          v-en-style='min-width: 130px'
        >
          {title}:
        </div>
        <div
          class='comm-item-content'
          style={contentStyle}
        >
          {content}
        </div>
      </div>
    );

    const { triggerConfig, recoveryConfig, noDataConfig } = this.analyzingConditions;

    const aggList = [{ id: 'total', name: this.$t('累计') }];

    const noticeOptions = {
      abnormal: window.i18n.t('当告警触发时'),
      recovered: window.i18n.t('当告警恢复时'),
      closed: window.i18n.t('当告警关闭时'),
      ack: window.i18n.t('告警确认时')
    };
    const actionOptions = {
      execute: window.i18n.t('执行前'),
      execute_success: window.i18n.t('执行成功'),
      execute_failed: window.i18n.t('执行失败')
    };

    return (
      <div class='strategy-config-detail'>
        <CommonNavBar
          class='strategy-config-nav'
          routeList={this.routeList}
          needCopyLink
          position-text={this.navName}
          navMode='copy'
        >
          <span slot='custom'>{this.$t('策略详情')}</span>
          <span
            slot='append'
            class={['icon-monitor icon-audit', { active: this.strategyView.show }]}
            v-bk-tooltips={{
              content: this.$t(this.strategyView.show ? '收起' : '展开'),
              delay: 200,
              appendTo: () => document.body
            }}
            onClick={() => (this.strategyView.show = !this.strategyView.show)}
          />
        </CommonNavBar>
        <div
          class='strategy-config-detail-page'
          v-bkloading={{ isLoading: this.loading }}
        >
          <div class='detail-content-left'>
            <div class='left-main'>
              {panelItem(
                this.$tc('基本信息'),
                <div class='base-info-main'>
                  <div class='base-info-row'>
                    {this.baseInfoRequireList.map(item => (
                      <span class='base-info-item'>
                        <span class='base-info-label'>{item.name} :</span>
                        <span class='base-info-value'>{this.baseInfo[item.key] ?? '--'}</span>
                      </span>
                    ))}
                  </div>
                  <div class='base-info-row'>
                    <span class='base-info-item lables-item'>
                      <span class='base-info-label'>{this.$t('标签')} :</span>
                      <span class='labels-list'>
                        {!!this.baseInfo.labels.length
                          ? this.baseInfo.labels.map(item => (
                              <span class={['labels-item', { 'custom-label': this.customLabelsList.includes(item) }]}>
                                {item}
                              </span>
                            ))
                          : '--'}
                      </span>
                    </span>
                  </div>
                </div>,
                { marginTop: 0 },
                [
                  <bk-button
                    theme={'primary'}
                    outline
                    style={{ width: '88px', margin: '0 8px 0 24px' }}
                    v-authority={{ active: !this.authority.MANAGE_AUTH }}
                    disabled={!this.detailData?.edit_allowed}
                    onClick={() =>
                      this.authority.MANAGE_AUTH
                        ? !!this.detailData?.edit_allowed && this.handleToEdit()
                        : this.handleShowAuthorityDetail()
                    }
                  >
                    {this.$t('编辑')}
                  </bk-button>,
                  <HistoryDialog list={this.historyList} />
                ]
              )}
              {panelItem(
                this.$tc('数据查询'),
                this.isMultivariateAnomalyDetection ? (
                  <AiopsMonitorData
                    metricData={this.metricData}
                    readonly={true}
                    defaultCheckedTarget={this.targetDetail || { target_detail: [] }}
                  ></AiopsMonitorData>
                ) : (
                  <div class='query-configs-main'>
                    <div>
                      {(() => {
                        if (this.editMode === 'Edit') {
                          return [
                            this.metricData.map(metricItem => <MetricListItem metric={metricItem} />),
                            this.metricData.length > 1 ? (
                              <MetricListItem
                                expression={this.expression}
                                expFunctions={this.expFunctions}
                              />
                            ) : undefined
                          ];
                        }
                        return (
                          <div class='promql-content'>
                            <div class='edit-wrap'>
                              <PromqlEditor
                                class='promql-editor'
                                readonly={true}
                                value={this.sourceData.sourceCode}
                              ></PromqlEditor>
                            </div>
                            <div class='step-wrap'>
                              <bk-input
                                class='step-input'
                                type='number'
                                min={10}
                                value={this.sourceData.step}
                                disabled
                              >
                                <div
                                  slot='prepend'
                                  class='step-input-prepend'
                                >
                                  <span>{'Step'}</span>
                                  <span
                                    class='icon-monitor icon-hint'
                                    v-bk-tooltips={{
                                      content: this.$t('数据步长'),
                                      placements: ['top']
                                    }}
                                  ></span>
                                </div>
                              </bk-input>
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                    {this.targetsDesc.message || this.targetsDesc.subMessage ? (
                      <div class='targets-desc'>
                        <span onClick={this.handleShowTargetTable}>
                          <i class='icon-monitor icon-mc-tv'></i>
                          <span class='targets-desc-text'>
                            {this.targetsDesc.message}
                            {this.targetsDesc.subMessage}
                          </span>
                        </span>
                      </div>
                    ) : undefined}
                    {!!this.metricData
                      .slice(0, 1)
                      .find(item => item.metricMetaId === 'bk_monitor|event' || item.data_type_label === 'alert') ? (
                      <div class='event-alert-level'>
                        <span class='level-label'>{this.$t('告警级别')} : </span>
                        <span class='level-content'>
                          <i
                            class={[
                              'icon-monitor',
                              this.currentAlertLevel.icon,
                              `level-icon-${this.currentAlertLevel.id}`
                            ]}
                          ></i>
                          <span class='level-text'>{this.currentAlertLevel.name}</span>
                        </span>
                      </div>
                    ) : undefined}
                  </div>
                )
              )}
              {this.showDetectionConfig
                ? panelItem(
                    this.$tc('检测算法'),
                    <div class='algorithms-wrap'>
                      <div class='alg-desc'>
                        <i18n path='同级别的各算法之间是{0}的关系'>
                          {this.detectionConfig.connector === 'and' ? this.$tc('且') : this.$tc('或')}
                        </i18n>
                      </div>
                      {this.detectionConfig.data.map(item => (
                        <DetectionRulesDisplay
                          class='detection-rules-item'
                          value={item}
                          metricData={this.metricData}
                          onModelChange={this.handleModelChange}
                          onAiopsTypeChange={this.handleAiopsChartType}
                        />
                      ))}
                    </div>
                  )
                : undefined}
              {panelItem(
                this.$tc('判断条件'),
                <div class='analyzing-conditions'>
                  {commonItem(
                    this.$t('触发条件'),
                    <i18n path='在{0}个周期内{1}满足{2}次检测算法，触发告警通知'>
                      <span class='bold-span'>{triggerConfig.checkWindow}</span>
                      <span class='bold-span'>{aggList.find(item => triggerConfig.checkType === item.id).name}</span>
                      <span class='bold-span'>{triggerConfig.count}</span>
                    </i18n>
                  )}
                  {commonItem(
                    this.$t('恢复条件'),
                    <i18n
                      path='连续{0}个周期内不满足条件表示恢复'
                      class='i18n-path'
                    >
                      <span class='bold-span'>{recoveryConfig.checkWindow}</span>
                    </i18n>
                  )}
                  {commonItem(
                    this.$t('无数据'),
                    noDataConfig.isEnabled ? (
                      <i18n
                        path={
                          !!noDataConfig.dimensions.length
                            ? '{0}当数据连续丢失{1}个周期时，触发告警通知基于以下维度{2}进行判断，告警级别{3}'
                            : '{0}当数据连续丢失{1}个周期时，触发告警通知，告警级别{2}'
                        }
                      >
                        <span></span>
                        <span class='bold-span'>{noDataConfig.continuous}</span>
                        {noDataConfig.dimensions.length ? (
                          <span class='bold-span'>
                            {noDataConfig.dimensions
                              .map(id => this.dimensionsMap?.[id as string]?.name || id)
                              .join(',')}
                          </span>
                        ) : undefined}
                        <span class='bold-span'>{levelList.find(item => noDataConfig.level === item.id).name}</span>
                      </i18n>
                    ) : (
                      '--'
                    )
                  )}
                  {commonItem(
                    this.$t('生效时间段'),
                    this.timeRanges.length
                      ? this.timeRanges.reduce((str, timeRange, index) => {
                          // eslint-disable-next-line no-param-reassign
                          str += `${timeRange.start}~${timeRange.end}${
                            index !== this.timeRanges.length - 1 ? ', ' : ''
                          }`;
                          return str;
                        }, '')
                      : '--'
                  )}
                  {commonItem(
                    this.$t('关联日历'),
                    !!this.calendars.length
                      ? this.calendars.reduce((str, item, index) => {
                          const target = this.calendarList.find(set => set.id === item);
                          // eslint-disable-next-line no-param-reassign
                          str += `${target?.name || item}${index !== this.calendars.length - 1 ? ', ' : ''}`;
                          return str;
                        }, '')
                      : '--'
                  )}
                </div>
              )}
              {panelItem(
                this.$tc('告警处理'),
                <div
                  class='actions-list'
                  key={this.actionsKey}
                >
                  {this.actionsData.length ? (
                    this.actionsData.map((item, index) => (
                      <div
                        class='action-item'
                        key={index}
                      >
                        <div class='item-head'>{item.signal.map(key => signalNames[key]).join(',')}</div>
                        <div class='item-content'>
                          <span class='title'>{this.$t('处理套餐')}:</span>
                          <span class='content'>
                            {this.actionConfigMap[item.config_id]?.name || ''}
                            {this.actionConfigMap[item.config_id] ? (
                              <span class='grey'>{`（${this.actionConfigMap[item.config_id].plugin_name}）`}</span>
                            ) : undefined}
                          </span>
                        </div>
                        <div class='item-content'>
                          <span class='title'>{this.$t('防御规则')}:</span>
                          {item.options.converge_config.is_enabled ? (
                            <span class='content'>
                              <i18n path='当{0}分钟内执行{1}次时，防御动作{2}'>
                                <span class='bold-span'>{item.options.converge_config.timedelta}</span>
                                <span class='bold-span'>{item.options.converge_config.count}</span>
                                <span class='bold-span'>
                                  {this.defenseMap[item.options.converge_config.converge_func]?.name || ''}
                                </span>
                              </i18n>
                            </span>
                          ) : (
                            window.i18n.t('关闭')
                          )}
                        </div>
                      </div>
                    ))
                  ) : (
                    <span>{this.$t('空')}</span>
                  )}
                </div>
              )}
              {panelItem(
                this.$tc('通知设置'),
                <div class='notice-config'>
                  {commonItem(
                    this.$t('告警阶段'),
                    this.noticeData.signal
                      .filter(key => !!noticeOptions[key])
                      .map((key, index) => {
                        if (hasExcludeNoticeWayOptions.includes(key)) {
                          return (
                            <span>
                              {index === 0 ? '' : ', '}
                              {noticeOptions[key]}
                              {this.noticeData.options?.exclude_notice_ways?.[key]?.length ? (
                                <span class='exclude-ways'>
                                  ({`${window.i18n.tc('明确排除')} `}
                                  {this.noticeData.options.exclude_notice_ways[key]
                                    .map(way => this.noticeWayList.find(item => item.type === way)?.label || '')
                                    .join(',')}
                                  {` ${window.i18n.tc('通知方式')}`})
                                </span>
                              ) : (
                                ''
                              )}
                            </span>
                          );
                        }
                        return (
                          <span>
                            {index === 0 ? '' : ', '}
                            {noticeOptions[key]}
                          </span>
                        );
                      })
                    // this.noticeData.signal.map(key => noticeOptions[key] || '').filter(item => !!item)
                    //   .join(',') || '--'
                  )}
                  {commonItem(
                    this.$t('处理阶段'),
                    this.noticeData.signal
                      .map(key => actionOptions[key] || '')
                      .filter(item => !!item)
                      .join(',') || '--'
                  )}
                  {commonItem(
                    this.$t('通知方式'),
                    <div class='user-groups'>
                      <div>
                        {' '}
                        &nbsp;
                        {this.getNoticeMethodName(
                          this.noticeData.options?.assign_mode || [],
                          this.noticeData?.user_group_list
                        )}
                      </div>
                      <div class='user-groups-container mb10'>
                        <div class='user-notice-item'>
                          <span class='groups-title-warp'>{this.$t('告警组')}：</span>
                          <span>
                            {this.noticeData?.user_group_list?.map(item => (
                              <span
                                class='user-group'
                                onClick={(e: Event) => {
                                  e.stopPropagation();
                                  this.handleSelcetAlarmGroup(item.id);
                                }}
                              >
                                {item.name}
                              </span>
                            ))}
                          </span>
                        </div>
                        <div class='user-notice-item'>
                          <span class='groups-title-warp'>{this.$t('通知升级')}：</span>
                          {this.noticeData?.options?.upgrade_config?.is_enabled ? (
                            <span>
                              <span>
                                <i18n
                                  class='text'
                                  path='当告警持续时长每超过{0}分种，将逐个按告警组升级通知'
                                >
                                  <span>{this.noticeData?.options?.upgrade_config?.upgrade_interval || 0}</span>
                                </i18n>
                              </span>
                              <span class='ml10'>
                                {this.noticeData?.options?.upgrade_config?.user_groups?.map(alarm => (
                                  <span
                                    class='user-group'
                                    onClick={(e: Event) => {
                                      e.stopPropagation();
                                      this.handleSelcetAlarmGroup(alarm);
                                    }}
                                  >
                                    {this.getAlarmGroupByID(alarm)}
                                  </span>
                                ))}
                              </span>
                            </span>
                          ) : (
                            <span>{this.$t('关闭')}</span>
                          )}
                        </div>
                      </div>
                    </div>,
                    {},
                    { width: '100%' }
                  )}
                  {commonItem(
                    this.$t('通知间隔'),
                    <span>
                      <i18n path='若产生相同的告警未确认或者未屏蔽,则{0}间隔{1}分钟再进行告警。'>
                        <span class='bold-span'>{intervalModeNames[this.noticeData.config.interval_notify_mode]}</span>
                        <span class='bold-span'>{this.noticeData.config.notify_interval}</span>
                      </i18n>
                    </span>,
                    { marginTop: 0 }
                  )}
                  {commonItem(
                    this.$t('告警风暴'),
                    <span>
                      {this.noticeData.options.converge_config.need_biz_converge ? this.$t('开启') : this.$t('关闭')}
                    </span>
                  )}
                  {this.metricData?.[0]?.data_type_label === 'time_series'
                    ? commonItem(
                        this.$t('降噪设置'),
                        <span>
                          {this.noticeData.options.noise_reduce_config.is_enabled ? (
                            <span>
                              {this.$t('开启')}，
                              {this.$t('基于维度{0},当前策略异常告警达到比例{1}%才进行发送通知。', [
                                this.noticeData.options.noise_reduce_config.dimensions.length
                                  ? this.noticeData.options.noise_reduce_config.dimensions
                                      .map(id => this.dimensionsMap?.[id]?.name || id)
                                      .join(',')
                                  : '--',
                                this.noticeData.options.noise_reduce_config.count
                              ])}
                            </span>
                          ) : (
                            this.$t('关闭')
                          )}
                        </span>
                      )
                    : undefined}
                  <div class='content-wraper'>
                    <div class='wrap-top'>
                      <CustomTab
                        panels={this.templateTypes}
                        active={this.templateActive}
                        type={'text'}
                        onChange={this.handleChangeTemplate}
                      ></CustomTab>
                    </div>
                    <div class='wrap-bottom'>
                      <div class='template-title'>
                        <span class='title'>{this.$t('告警标题')}:</span>
                        <span class='content'>{this.templateData.title_tmpl}</span>
                      </div>
                      <div
                        class='label-wrap'
                        style={{ marginTop: '7px' }}
                      >
                        <span class='label'>
                          <span>{this.$t('告警通知模板')}</span>
                          <span class='need-img-check'>
                            {this.$t('是否附带图片')}：
                            {this.noticeData.options.chart_image_enabled ? this.$t('是') : this.$t('否')}
                          </span>
                        </span>
                        <div class='wrap-right'>
                          <div
                            style={{ marginRight: '26px' }}
                            class={'template-btn-wrap'}
                            onClick={this.handleShowVariateList}
                          >
                            <i class='icon-monitor icon-audit'></i>
                            <span class='template-btn-text'>{this.$t('变量列表')}</span>
                          </div>
                          <div
                            class={['template-btn-wrap', { 'template-btn-disabled': !this.templateData.message_tmpl }]}
                            onClick={this.handleShowTemplate}
                          >
                            <i class='icon-monitor icon-audit'></i>
                            <span class='template-btn-text'>{this.$t('模板预览')}</span>
                          </div>
                        </div>
                      </div>
                      <div class='template-pre'>
                        <pre>{this.templateData.message_tmpl}</pre>
                      </div>
                      <StrategyTemplatePreview
                        dialogShow={this.isShowTemplate}
                        template={this.templateData.message_tmpl}
                        {...{ on: { 'update:dialogShow': v => (this.isShowTemplate = v) } }}
                      ></StrategyTemplatePreview>
                      <StrategyVariateList
                        dialogShow={this.variateListShow}
                        {...{ on: { 'update:dialogShow': val => (this.variateListShow = val) } }}
                        variate-list={this.variateList}
                      ></StrategyVariateList>
                    </div>
                  </div>
                  <AlarmGroupDetail
                    id={this.alarmGroupDetail.id as any}
                    v-model={this.alarmGroupDetail.show}
                    customEdit
                    onEditGroup={this.handleEditAlarmGroup}
                    onShowChange={val => !val && (this.alarmGroupDetail.id = 0)}
                  ></AlarmGroupDetail>
                </div>
              )}
            </div>
            <div style='padding-top: 16px;'></div>
          </div>
          <div
            class='detail-content-right'
            style={{ width: this.rightWidth }}
          >
            <div
              class='right-wrapper'
              style={{ width: this.rightWidth }}
            >
              <div
                class={['drag', { active: this.strategyView.isActive }]}
                on-mousedown={this.handleMouseDown}
              ></div>
              <StrategyView
                metricData={this.metricData}
                sourceData={this.sourceData}
                detectionConfig={this.detectionConfig}
                expression={this.expression}
                editMode={this.editMode}
                expFunctions={this.expFunctions}
                legalDimensionList={this.legalDimensionList}
                dataMode={this.dataMode}
                aiopsChartType={this.localAiopsChartType}
                aiopsModelMdList={this.aiopsModelDescMdGetter}
                strategyTarget={this.detailData?.items?.[0]?.target || []}
              />
            </div>
          </div>
        </div>
        {!!this.targetsTableData ? (
          <bk-dialog
            v-model={this.showTargetTable}
            on-change={v => (this.showTargetTable = v)}
            show-footer={false}
            header-position='left'
            need-footer={false}
            width='1100'
            title={this.$t('监控目标')}
            ext-cls='target-table-wrap'
          >
            <strategy-target-table
              tableData={this.targetsTableData}
              targetType={this.metricData[0]?.targetType}
              objType={this.metricData[0]?.objectType}
            />
          </bk-dialog>
        ) : undefined}
      </div>
    );
  }
}
