/* eslint-disable @typescript-eslint/naming-convention */
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
/* eslint-disable no-param-reassign */
/* eslint-disable camelcase */
import { Component, Emit, Inject, Prop, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import {
  DEFAULT_MESSAGE_TMPL,
  DEFAULT_TITLE_TMPL
} from '../../../../fta-solutions/pages/setting/set-meal/set-meal-add/meal-content/meal-content-data';
import SetMealAddStore from '../../../../fta-solutions/store/modules/set-meal-add';
import { getConvergeFunction } from '../../../../monitor-api/modules/action';
import { strategySnapshot } from '../../../../monitor-api/modules/alert';
import { listCalendar } from '../../../../monitor-api/modules/calendar';
import { getFunctions } from '../../../../monitor-api/modules/grafana';
import { listActionConfig, listUserGroup } from '../../../../monitor-api/modules/model';
import {
  getMetricListV2,
  getScenarioList,
  getStrategyV2,
  getTargetDetail,
  noticeVariableList,
  promqlToQueryConfig,
  queryConfigToPromql,
  saveStrategyV2
} from '../../../../monitor-api/modules/strategies';
import debouceDecorator from '../../../../monitor-common/utils/debounce-decorator';
import bus from '../../../../monitor-common/utils/event-bus';
// import StrategyMetricSelector from './components/strategy-metric-selector';
import { deepClone, getUrlParam, transformDataKey, typeTools } from '../../../../monitor-common/utils/utils';
import ChangeRcord from '../../../components/change-record/change-record';
import MetricSelector from '../../../components/metric-selector/metric-selector';
import { IProps as ITimeRangeMultipleProps } from '../../../components/time-picker-multiple/time-picker-multiple';
import { getDefautTimezone, updateTimezone } from '../../../i18n/dayjs';
import { ISpaceItem } from '../../../types';
import { IOptionsItem } from '../../calendar/types';
import { IDataRetrieval } from '../../data-retrieval/typings';
import CommonNavBar from '../../monitor-k8s/components/common-nav-bar';
import { HANDLE_HIDDEN_SETTING } from '../../nav-tools';
import { transformLogMetricId } from '../strategy-config-detail/utils';
import StrategyView from '../strategy-config-set/strategy-view/strategy-view';

import { actionConfigGroupList, IAllDefense, IValue as IAlarmItem } from './alarm-handling/alarm-handling';
import AlarmHandlingList from './alarm-handling/alarm-handling-list';
import BaseConfig, { IBaseConfig } from './base-config/base-config';
import GroupPanel from './components/group-panel';
import { ChartType } from './detection-rules/components/intelligent-detect/intelligent-detect';
import { IModelData } from './detection-rules/components/time-series-forecast/time-series-forecast';
import DetectionRules from './detection-rules/detection-rules';
import JudgingCondition, { DEFAULT_TIME_RANGES, IJudgingData } from './judging-condition/judging-condition';
import AiopsMonitorData from './monitor-data/aiops-monitor-data';
import { IFunctionsValue } from './monitor-data/function-select';
import MonitorData from './monitor-data/monitor-data';
import MonitorDataEmpty from './monitor-data/monitor-data-empty';
import NoticeConfigNew, { INoticeValue } from './notice-config/notice-config';
import { IActionConfig } from './type';
import {
  dataModeType,
  EditModeType,
  IBaseInfoRouteParams,
  IDetectionConfig,
  IMetricDetail,
  IScenarioItem,
  ISourceData,
  MetricDetail,
  MetricType,
  strategyType
} from './typings';

import './strategy-config-set.scss';

const { i18n } = window;

const hostTargetFieldType = {
  TOPO: 'host_topo_node',
  INSTANCE: 'ip',
  SERVICE_TEMPLATE: 'host_service_template',
  SET_TEMPLATE: 'host_set_template'
};
const serviceTargetFieldType = {
  TOPO: 'service_topo_node',
  SERVICE_TEMPLATE: 'service_service_template',
  SET_TEMPLATE: 'service_set_template'
};
interface IStrategyConfigSetProps {
  fromRouteName: string;
  id: string | number;
}

interface IStrategyConfigSetEvent {
  onCancel: boolean;
  onSave: void;
}

export interface IAlarmGroupList {
  id: number | string;
  name: string;
  receiver: string[];
}

/* data_source_label 为 prometheus 监控数据模式显示为source模式 */
const PROMETHEUS = 'prometheus';

const LETTERS = 'abcdefghijklmnopqrstuvwxyz';
const DEFAULT_INTERVAL = 60; // 指标默认的周期单位：秒
const DEFAULT_TIME_RANGE: ITimeRangeMultipleProps['value'] = DEFAULT_TIME_RANGES.map(timeRange => [
  `${timeRange[0]}:00`,
  `${timeRange[1]}:59`
]);

Component.registerHooks(['beforeRouteLeave', 'beforeRouteEnter']);
@Component
export default class StrategyConfigSet extends tsc<IStrategyConfigSetProps, IStrategyConfigSetEvent> {
  // 策略Id
  @Prop({ type: [String, Number] }) readonly id: string | number;
  // 来自route id
  @Prop({ type: String }) readonly fromRouteName: string;

  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('authorityMap') authorityMap;
  @Inject('strategyType') strategyType: strategyType;
  @ProvideReactive('metricFunctions') metricFunctions = [];
  @ProvideReactive('strategyId') strategyId = 0;
  /** 当前编辑的策略是否存在智能异常检测算法 */
  @ProvideReactive('editStrategyIntelligentDetectList') editStrategyIntelligentDetectList: string[] = [];

  @Ref('judgingCondition') readonly judgingConditionEl: JudgingCondition;
  @Ref('base-config') readonly baseConfigEl: BaseConfig;
  @Ref('detection-rules') readonly detectionRulesEl: DetectionRules;
  // @Ref('alarmHandling') readonly alarmHandlingRef: AlarmHandling;
  @Ref('noticeConfigNew') noticeConfigRef: NoticeConfigNew;
  @Ref('alarmHandlingList') alarmHandlingListRef: AlarmHandlingList;
  @Ref('noticeConfigPanel') noticeConfigPanelRef: GroupPanel;
  @Ref() contentRef: HTMLElement;
  @Ref('aiopsMonitorData') aiopsMonitorDataRef: AiopsMonitorData;

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
  /* 面包屑 */
  navName = 'loading...';
  // 监控对象
  scenarioList: IScenarioItem[] = [];
  // 告警组
  alarmGroupList: IAlarmGroupList[] = [];

  strategyView: { rightWidth: string | number; range: number[]; show: boolean; isActive: boolean } = {
    rightWidth: '33%',
    range: [300, 1200],
    show: true,
    isActive: false
  };
  // 基本信息数据
  baseConfig: IBaseConfig = {
    bk_biz_id: this.bizId,
    scenario: 'os',
    name: '',
    labels: [],
    isEnabled: true,
    priority: null
  };
  // 检测规则数据
  detectionConfig: IDetectionConfig = {
    unit: '',
    unitType: '', // 单位类型
    unitList: [],
    connector: 'and',
    data: []
  };

  /** 检测规则编辑时需要回填的数据 */
  detectionDataBackfill = [];

  // 告警处理数据(旧)
  // actionList: IAlarmHandleValue[] = [];
  curActionIndex = 0;

  // 判断条件数据
  analyzingConditions: IJudgingData = {
    triggerConfig: {
      // 触发条件
      count: 2,
      checkWindow: 5,
      checkType: 'total',
      timeRanges: DEFAULT_TIME_RANGE,
      calendars: []
    },
    recoveryConfig: {
      // 恢复条件
      checkWindow: 5
    },
    noDataConfig: {
      // 无数据告警
      continuous: 10,
      isEnabled: true,
      dimensions: [],
      level: 2
    },
    noticeTemplate: {
      anomalyTemplate: `{{content.level}}
{{content.begin_time}}
{{content.time}}
{{content.duration}}
{{content.target_type}}
{{content.data_source}}
{{content.content}}
{{content.current_value}}
{{content.biz}}
{{content.target}}
{{content.dimension}}
{{content.detail}}
{{content.related_info}}`,
      triggerList: [],
      variateList: [],
      previewTemplate: false,
      variateListShow: false
    }
  };

  // 防御动作列表
  defenseList: IAllDefense[] = [];
  // 通知设置(新)
  noticeData: INoticeValue = {
    config_id: 0, // 套餐id
    user_groups: [], // 告警组
    signal: ['abnormal'], // 触发信号
    options: {
      converge_config: {
        need_biz_converge: true // 告警风暴开关
      },
      exclude_notice_ways: {
        recovered: [],
        closed: [],
        ack: []
      },
      noise_reduce_config: {
        is_enabled: false,
        count: 10,
        dimensions: []
      },
      chart_image_enabled: true // 告警通知模板是否附带图片的选项
    },
    config: {
      // 高级配置
      interval_notify_mode: 'standard',
      notify_interval: 120,
      template: [
        { signal: 'abnormal', message_tmpl: DEFAULT_MESSAGE_TMPL, title_tmpl: DEFAULT_TITLE_TMPL },
        { signal: 'recovered', message_tmpl: DEFAULT_MESSAGE_TMPL, title_tmpl: DEFAULT_TITLE_TMPL },
        { signal: 'closed', message_tmpl: DEFAULT_MESSAGE_TMPL, title_tmpl: DEFAULT_TITLE_TMPL }
      ]
    }
  };
  // 告警处理(新)
  actionsData: IAlarmItem[] = [];
  actionIndex = -1;

  // 判断条件生效时间段（当isNeedJudgingCondition为false显示）
  // judgeTimeRange: ITimeRangeMultipleProps['value'] = [['00:00', '23:59']];
  // 是否开启告警处理
  isActionEnabled = false;

  // 指标数据
  metricData: MetricDetail[] = [];
  /* source数据 此数据与指标数据隔离 */
  sourceData: ISourceData = {
    /* promql */
    sourceCode: '',
    /* agg_interval */
    step: 60,
    sourceCodeCache: '',
    /* 语法报错 */
    promqlError: false,
    /* 报错信息 */
    errorMsg: ''
  };
  /* ui 转 promql 的报错信息 */
  metricDataErrorMsg = '';
  monitorDataEditMode: EditModeType = 'Edit';
  // 将切换至ui模式
  switchToUI = false;
  expression = '';
  localExpress = '';
  /** 表达式的展示状态 */
  isShowExpress = false;
  /** 表达式函数 */
  localExpFunctions: IFunctionsValue[] = [];
  target: any[] = [];
  defaultCheckedTarget: any = { target_detail: [] };

  loading = false;
  metricSelector: {
    type: MetricType;
    id: string;
    monitorType: string;
    show: boolean;
    key?: string;
    dataTypeLabel?: string;
    isEdit?: boolean;
  } = {
    type: MetricType.TimeSeries,
    id: null,
    monitorType: '',
    show: false,
    key: '',
    dataTypeLabel: ''
  };
  record: {
    data: Record<string, string>;
    show: boolean;
  } = { show: false, data: {} };
  // 监控数据模式 converge: 汇聚 realtime: 实时
  dataMode: dataModeType = 'converge';
  strategyStatusMap = {
    UPDATED: i18n.t('（已修改）'),
    DELETED: i18n.t('（已删除）'),
    UNCHANGED: ''
  };
  strategyStatus = '';

  // 套餐列表
  actionConfigList: IActionConfig[] = [];

  monitorDataLoading = false;

  /** 智能检测算法图表类型 */
  localAiopsChartType: ChartType = 'none';

  aiopsModelMdList: IModelData[] = [];

  activeModelIndex = -1;

  /** 日历列表 */
  calendarList: IOptionsItem[] = [];

  /** 指标选择器触发目标id */
  metricSelectorTargetId = null;

  /* 当前说明类型 */
  descriptionType = '';
  /* 是否为场景智能检测 */
  isMultivariateAnomalyDetection = false;

  /* 是否展示实时查询（只有实时能力的不能隐藏 如系统事件， 如果已经配置了的不能隐藏） */
  showRealtimeStrategy = !!window?.show_realtime_strategy;
  /* 时区 */
  timezone = getDefautTimezone();
  /* 是否可编辑 */
  editAllowed = true;

  get isEdit(): boolean {
    return !!this.$route.params.id;
  }

  get bizList(): ISpaceItem[] {
    return this.$store.getters.bizList;
  }
  get bizId(): string | number {
    return this.$store.getters.bizId;
  }
  get rightWidth() {
    return typeof this.strategyView.rightWidth === 'string'
      ? this.strategyView.rightWidth
      : `${this.strategyView.rightWidth}px`;
  }
  // 是否为详情页面
  get isDetailMode() {
    return this.$route.name === 'strategy-config-detail';
  }
  // 已选中的维度合法列表
  get legalDimensionList() {
    return this.metricData.reduce(
      (pre, cur) =>
        cur.agg_dimension?.length > pre.length
          ? cur.dimensions?.filter(set => cur.agg_dimension.includes(set.id as any))
          : pre,
      []
    );
  }
  // 已选择了一个智能检测算法
  get hasAIntelligentDetect() {
    return !!this.detectionConfig.data.find(item => item.type === 'IntelligentDetect');
  }
  // 是否选择Aiops算法
  get hasAiOpsDetect() {
    return !!this.detectionConfig.data.find(item =>
      ['IntelligentDetect', 'TimeSeriesForecasting', 'AbnormalCluster'].includes(item.type)
    );
  }
  // 是否显示判断条件
  get isNeedJudgingCondition() {
    return this.metricData?.[0]?.data_type_label !== 'alert';
  }
  // 自愈关联告警
  get isFtaAlert() {
    return this.metricData?.[0]?.isRelatedAlert || false;
  }

  /** 是否为克隆策略 */
  get isClone() {
    return this.$route.name === 'strategy-config-clone';
  }
  /** 指标监控对象数据 */
  get scenarioAllList() {
    const list = deepClone(this.scenarioList);
    const res = list.reduce((total, cur) => {
      const child = cur.children || [];
      total = total.concat(child);
      return total;
    }, []);
    return res;
  }
  /* ui 与 promql 转换之间的报错信息 */
  get errMsg() {
    return this.monitorDataEditMode === 'Edit' ? this.metricDataErrorMsg : this.sourceData.errorMsg;
  }

  get selectMetricData() {
    return this.metricData.filter(item => !!item.metric_id);
  }

  /* 提交按钮禁用状态 */
  get submitBtnDisabled() {
    if (this.isMultivariateAnomalyDetection) {
      return false;
    }
    if (!this.editAllowed) {
      return true;
    }
    return this.monitorDataEditMode === 'Edit'
      ? this.metricData?.filter(item => item.metric_id).length < 1 || this.monitorDataLoading
      : !this.sourceData.sourceCode;
  }
  /* 提交按钮禁用提示状态 */
  get submitBtnTipDisabled() {
    if (this.isMultivariateAnomalyDetection) {
      return false;
    }
    if (!this.editAllowed) {
      return false;
    }
    return this.monitorDataEditMode === 'Edit'
      ? !(this.metricData?.filter(item => item.metric_id).length < 1 || this.monitorDataLoading)
      : this.sourceData.sourceCode;
  }

  /** 策略监控目标 */
  get strategyTarget() {
    return this.handleGetTargetParams();
  }
  /**
   * 是否需要展示单位
   * 选择了表达式隐藏检测规则以及预览图的单位的展示
   * 预览图展示原始数据
   * 保存策略也不需要带单位
   */
  @ProvideReactive('yAxisNeedUnit')
  get needShowUnit() {
    return this.isShowExpress ? !this.localExpress || this.localExpress.toLocaleLowerCase() === 'a' : true;
  }

  @Watch('id', { immediate: true })
  handleIdChange(v, old) {
    // 编辑初始化数据
    if (`${v}` !== `${old}` && ['strategy-config-edit', 'strategy-config-clone'].includes(this.$route.name)) {
      this.initData();
    }
  }
  created() {
    !this.loading && this.initData();
  }

  mounted() {
    /** 设置预览图宽度 */
    const { width } = this.contentRef.getBoundingClientRect();
    this.strategyView.rightWidth = Math.ceil(width / 3);
    bus.$on(HANDLE_HIDDEN_SETTING, this.handleUpdateCalendarList);
  }
  beforeDestroy() {
    bus.$off(HANDLE_HIDDEN_SETTING, this.handleUpdateCalendarList);
  }
  @Watch('fromRouteName', { immediate: true })
  async handleRouteChange(v: string) {
    if (!v) return;
    const allowJumpMap = ['alarm-group-add', 'alarm-group-edit', 'set-meal-edit', 'set-meal-add'];
    if (!allowJumpMap.some(item => v.includes(item))) {
      this.handleSetDefaultData();
      if (!this.loading && `${this.id}` === `${this.$route.params.id}`) {
        this.loading = true;
        this.initData().finally(() => {
          this.loading = false;
        });
      }
    } else {
      // 更新从套餐页或者告警组页返回的数据
      if (v.indexOf('set-meal-edit') > -1) {
        this.handleAddMeal(true);
      } else if (v.indexOf('set-meal-add') > -1) {
        this.$route.params.mealId && this.handleAddMeal();
      } else if (v.indexOf('alarm-group-edit') > -1) {
        this.handleAddNoticeGroup(true);
      } else if (v.indexOf('alarm-group-add') > -1) {
        this.$route.params.alarmGroupId && this.handleAddNoticeGroup();
      }
    }
    // this.addDefaultAlarmHandling();
  }
  deactivated() {
    this.clearErrorMsg();
    (this.$refs.noticeConfigNew as NoticeConfigNew)?.excludePopInit();
  }
  handleUpdateCalendarList(settings: string) {
    if (settings === 'calendar') {
      this.getCalendarList();
    }
  }
  /** 更新面包屑数据 */
  updateRouteNavName(name: string) {
    switch (this.$route.name) {
      case 'strategy-config-add':
        this.navName = this.$tc('新建策略');
        break;
      case 'strategy-config-edit':
        this.navName = `${this.$tc('编辑')} ${name}`;
        break;
      case 'strategy-config-detail':
        this.navName = `${this.$tc('查看')} ${name}`;
        break;
      case 'strategy-config-clone':
        this.navName = this.$tc('新建策略');
        break;
      default:
        break;
    }
    const leng = this.routeList.length;
    const theLastOne = this.routeList[leng - 1];
    theLastOne.name = name;
  }
  async handleTransformUrlParam() {
    let metric: any = {};
    // 兼容老版本日志平台传递方式
    if (getUrlParam('indexSetId')) {
      let condition: any = getUrlParam('condition');
      let dimension: any = getUrlParam('dimension');
      try {
        dimension && (dimension = JSON.parse(dimension));
        condition && (condition = JSON.parse(condition));
      } catch (e) {
        dimension = [];
        condition = [];
      }
      metric = {
        indexSetId: getUrlParam('indexSetId'),
        scenarioId: getUrlParam('scenarioId'),
        indexStatement: getUrlParam('indexStatement'),
        condition,
        dimension
      };
    } else {
      try {
        const metricData = this.$route.query.data ? this.$route.query.data : this.$route.params.data;
        metric = typeof metricData === 'string' ? JSON.parse(decodeURIComponent(metricData)) : metricData;
        // promql
        if (metric.mode === 'code' || metric.data?.[0]?.promql) {
          await this.$nextTick();
          this.monitorDataEditMode = 'Source';
          this.sourceData.sourceCode = metric.data[0]?.promql || '';
          this.sourceData.sourceCodeCache = metric.data[0]?.promql || '';
          this.sourceData.step = metric.data[0]?.step === 'auto' ? 60 : metric.data[0]?.step || 60;
          return;
        }
      } catch (e) {
        console.error(e);
        return;
      }
    }
    const metricFields = ['metric_field', 'data_label', 'result_table_id', 'data_source_label', 'data_type_label'];
    if (metric.query_configs?.length) {
      this.metricData = (
        await Promise.all(
          metric.query_configs.map((item, index) => {
            if (item.metrics) {
              item.metric_field = item.metrics[0].field;
              item.refId = item.metrics[0].alias;
            }
            if (item.table) {
              item.result_table_id = item.table || '';
            }
            if (item.interval_unit === 'm') {
              item.interval_unit = 's';
              item.interval *= 60;
            }
            return getMetricListV2({
              bk_biz_id: this.bizId,
              // page: 1,
              // page_size: 1,
              conditions: metricFields
                .map(field => {
                  if (field === 'data_source_label') {
                    return {
                      key: field,
                      value: Array.isArray(item[field]) ? item[field] : [item[field]]
                    };
                  }
                  return {
                    key: field,
                    value: item[field] ?? ''
                  };
                })
                .filter(set => set.key !== 'data_label' || set.value),
              search_value: '',
              tag: ''
            })
              .then(({ metric_list: metricList }) => {
                const curMetric = metricList.find(set => set.metric_field === item.metric_field);
                if (!curMetric) return;
                this.baseConfig.scenario = curMetric.result_table_label;
                return new MetricDetail({
                  ...curMetric,
                  alias: (item.refId || item.alias || LETTERS[index])?.toLocaleLowerCase?.(),
                  agg_condition: this.getAggConditionOfHasDimensionName(item.where, curMetric),
                  agg_dimension: item.group_by || [],
                  agg_interval: !item.interval || item.interval === 'auto' ? DEFAULT_INTERVAL : item.interval,
                  agg_method: item.method,
                  query_string: item.query_string || '',
                  functions: item.functions
                });
              })
              .catch(() => ({}));
          })
        )
      ).filter(item => !!item) as MetricDetail[];
      if (!this.metricData.length) return;
      const expList = metric.expressionList || [];
      if (expList.length) {
        const item = expList.find(item => item.active);
        if (!!item) {
          this.expression = item.expression?.toLocaleLowerCase?.() || this.metricData[0]?.alias;
          this.localExpress = this.expression;
          this.localExpFunctions = item.functions;
        }
      }
      this.baseConfig.name = metric?.strategy_name || '';
      this.handleDetectionRulesUnit();
      this.handleSetOtherData();
      this.handleResetMetricDimension();
      return;
    }
    const isOldLogSearch = !!metric?.indexSetId;
    const isLogSearch =
      isOldLogSearch || (metric.data_type_label === 'log' && metric.data_source_label === 'bk_log_search');
    const data = {
      agg_condition: metric.where || metric.condition || [],
      agg_dimension: metric.group_by || metric.dimension || [],
      agg_interval: metric.interval === 'auto' ? DEFAULT_INTERVAL : metric.interval,
      agg_method: metric.method,
      data_source_label: isOldLogSearch ? 'bk_log_search' : metric.data_source_label,
      data_type_label: isOldLogSearch ? 'log' : metric.data_type_label,
      metric_field: metric.metric_field,
      result_table_id: metric.result_table_id || '',
      data_label: metric.data_label || '',
      result_table_label: isOldLogSearch ? metric.scenarioId : metric.result_table_label,
      query_string: isOldLogSearch ? metric.indexStatement : metric.query_string,
      index_set_id: isOldLogSearch ? metric.indexSetId : metric.index_set_id,
      targets: (metric.target || []).map(item => ({ ip: item.bk_target_ip, bk_cloud_id: item.bk_target_cloud_id }))
    };
    const { metric_list: metricList } = await getMetricListV2({
      bk_biz_id: this.bizId,
      data_source_label: Array.isArray(data.data_source_label) ? data.data_source_label : [data.data_source_label],
      data_type_label: data.data_type_label,
      // page: 1,
      // page_size: 1,
      conditions: isLogSearch
        ? [{ key: 'index_set_id', value: data.index_set_id }]
        : metricFields.map(field => ({
            key: field,
            value: data[field]
          })),
      search_value: '',
      tag: ''
    }).catch(() => ({}));
    if (metricList?.length) {
      const curMetric =
        metricList.find(set =>
          !isLogSearch
            ? set.metric_field === data.metric_field
            : +set.extend_fields?.index_set_id === +data.index_set_id
        ) || {};
      this.baseConfig.scenario = curMetric.result_table_label;
      this.metricData = [
        new MetricDetail({
          ...curMetric,
          alias: 'a',
          agg_condition: (data.agg_condition || []).map(item => ({
            ...item,
            value: typeof item.value === 'string' ? item.value.split(',') : item.value
          })),
          agg_dimension: data.agg_dimension || [],
          agg_interval: data.agg_interval || DEFAULT_INTERVAL,
          agg_method: data.agg_method,
          query_string: data.query_string || ''
        })
      ];
      this.handleDetectionRulesUnit();
    }
  }

  /**
   * @description: 回填基本信息
   */
  handleDisplayBaseInfo() {
    return Promise.resolve().then(() => {
      let baseInfo: IBaseInfoRouteParams = null;
      try {
        const data = this.$route.query.baseInfo ? this.$route.query.baseInfo : this.$route.params.baseInfo;
        baseInfo = typeof data === 'string' ? JSON.parse(decodeURIComponent(data)) : data;
      } catch (e) {
        console.error(e);
        return;
      }
      Object.keys(baseInfo || {}).forEach(key => {
        if (key in this.baseConfig) this.baseConfig[key] = baseInfo[key];
      });
    });
  }
  // 重置数据
  handleSetDefaultData() {
    this.baseConfig = {
      bk_biz_id: this.bizId,
      scenario: 'os',
      name: '',
      labels: [],
      isEnabled: true,
      priority: null
    };

    this.monitorDataEditMode = 'Edit';
    // 检测规则数据
    this.detectionConfig = {
      unit: '',
      unitType: '',
      unitList: [],
      connector: 'and',
      data: []
    };
    // 检测回填数据
    this.detectionDataBackfill = [];

    // 自愈告警处理数据
    // this.actionList = [];
    // 告警处理(新)
    this.actionsData = [];
    // 通知设置(新)
    this.noticeData = {
      config_id: 0, // 套餐id
      user_groups: [], // 告警组
      signal: ['abnormal'], // 触发信号
      options: {
        converge_config: {
          need_biz_converge: true // 告警风暴开关
        },
        exclude_notice_ways: {
          recovered: [],
          closed: [],
          ack: []
        },
        noise_reduce_config: {
          is_enabled: false,
          count: 10,
          dimensions: []
        },
        upgrade_config: {
          is_enabled: false,
          user_groups: [],
          upgrade_interval: undefined
        },
        assign_mode: ['by_rule', 'only_notice'],
        chart_image_enabled: true
      },
      config: {
        interval_notify_mode: 'standard',
        notify_interval: 120,
        template: [
          { signal: 'abnormal', message_tmpl: DEFAULT_MESSAGE_TMPL, title_tmpl: DEFAULT_TITLE_TMPL },
          { signal: 'recovered', message_tmpl: DEFAULT_MESSAGE_TMPL, title_tmpl: DEFAULT_TITLE_TMPL },
          { signal: 'closed', message_tmpl: DEFAULT_MESSAGE_TMPL, title_tmpl: DEFAULT_TITLE_TMPL }
        ]
      }
    };
    this.noticeConfigRef?.templateDataInit();

    // this.judgeTimeRange = [['00:00', '23:59']];

    this.isActionEnabled = false;

    // 判断条件数据
    this.analyzingConditions = {
      triggerConfig: {
        // 触发条件
        count: 2,
        checkWindow: 5,
        checkType: 'total',
        timeRanges: DEFAULT_TIME_RANGE,
        calendars: []
      },
      recoveryConfig: {
        // 恢复条件
        checkWindow: 5
      },
      noDataConfig: {
        // 无数据告警
        continuous: 10,
        isEnabled: false,
        dimensions: [],
        level: 2
      },
      noticeTemplate: {
        anomalyTemplate: `{{content.level}}
{{content.begin_time}}
{{content.time}}
{{content.duration}}
{{content.target_type}}
{{content.data_source}}
{{content.content}}
{{content.current_value}}
{{content.biz}}
{{content.target}}
{{content.dimension}}
{{content.detail}}
{{content.related_info}}`,
        triggerList: [],
        variateList: [],
        previewTemplate: false,
        variateListShow: false
      }
    };

    // 指标数据
    this.metricData = [];
    this.sourceData.sourceCode = '';
    this.expression = '';
    this.localExpress = '';
    this.target = [];
    this.defaultCheckedTarget = {};
    this.metricSelector = {
      type: MetricType.TimeSeries,
      id: null,
      monitorType: '',
      show: false,
      isEdit: false
    };
    // 监控数据模式 converge: 汇聚 realtime: 实时
    this.dataMode = 'converge';
  }
  /**
   * @description: 获取指标函数列表
   * @param {*}
   * @return {*}
   */
  async handleGetMetricFunctions() {
    this.metricFunctions = await getFunctions().catch(() => []);
  }
  // 点击取消
  @Emit('cancel')
  handleCancel(needBack = true) {
    return needBack;
  }
  // 清空校验信息
  clearErrorMsg() {
    this.baseConfigEl?.clearErrorMsg();
    this.detectionRulesEl?.clearErrorMsg();
    this.alarmHandlingListRef?.clearError();
    this.noticeConfigRef?.clearError();
    // this.alarmHandlingRef?.clearErrorMsg();
    // this?.alarmHandlingRef?.clearErrorMsg();
  }
  // 初始化数据
  async initData() {
    this.showRealtimeStrategy = !!window?.show_realtime_strategy;
    if (this.$route.query?.timezone) {
      this.timezone = this.$route.query.timezone as string;
      updateTimezone(this.timezone);
    }
    if (this.isClone || !this.id) {
      this.updateRouteNavName(this.$tc('新建策略'));
    }
    this.loading = true;
    this.strategyId = 0;
    this.editAllowed = true;
    this.isMultivariateAnomalyDetection = false;
    const promiseList = [];
    if (!this.scenarioList?.length) {
      promiseList.push(this.getScenarioList());
    }
    promiseList.push(this.getDefenseList());
    promiseList.push(this.getAlarmGroupList());
    promiseList.push(this.getActionConfigList());
    promiseList.push(this.getCalendarList());
    if (!SetMealAddStore.getMessageTemplateList.length) {
      promiseList.push(SetMealAddStore.getVariableDataList());
    }
    if (!SetMealAddStore.getNoticeWayList.length) {
      promiseList.push(SetMealAddStore.getNoticeWay());
    }
    if (this.id !== '' && this.id !== undefined && this.id !== 'undefined') {
      promiseList.push(this.getStrategyConfigDetail(this.id));
    } else if (this.$route.query?.data || this.$route.params?.data || getUrlParam('indexSetId')) {
      promiseList.push(this.handleTransformUrlParam());
    } else if (this.$route.params.baseInfo || this.$route.query.baseInfo) {
      promiseList.push(this.handleDisplayBaseInfo());
    }
    // const { noticeTemplate } = this.analyzingConditions;
    // if (!noticeTemplate?.variateList.length) {
    //   promiseList.push(this.handleGetVariateList());
    // }
    if (!this?.metricFunctions?.length) {
      promiseList.push(this.handleGetMetricFunctions());
    }
    // 请求标签数据
    this.baseConfigEl && promiseList.push(this.baseConfigEl.getLabelListApi());
    await Promise.all(promiseList).catch(err => {
      console.log(err);
    });
    /* 是否包含场景id 如果包含则自动填充场景智能检测数据 */
    if (this.$route.query?.scene_id) {
      this.handleShowMetric({ type: MetricType.MultivariateAnomalyDetection });
    }
    this.loading = false;
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

  // 获取防御动作列表
  async getDefenseList() {
    const data = await getConvergeFunction().catch(() => []);
    this.defenseList = data;
  }

  // 获取套餐数据
  async getActionConfigList() {
    const data = await listActionConfig({
      with_advance_fields: 'no'
    }).catch(() => []);
    this.actionConfigList = data;
  }

  // 获取告警组数据
  getAlarmGroupList() {
    return listUserGroup({ exclude_detail_info: 1 }).then(data => {
      this.alarmGroupList = data.map(item => ({
        id: item.id,
        name: item.name,
        needDuty: item.need_duty,
        receiver:
          item?.users?.map(rec => rec.display_name).filter((item, index, arr) => arr.indexOf(item) === index) || []
      }));
    });
  }

  // 获取监控对象数据
  getScenarioList() {
    return getScenarioList().then(data => {
      this.scenarioList = data;
    });
  }

  // 获取告警变量
  getNoticeVariableList() {
    return noticeVariableList().catch(() => []);
  }
  // 策略详情数据获取
  async getStrategyConfigDetail(id) {
    // 策略快照start
    this.strategyId = 0;
    const { fromEvent } = this.$route.query;
    let snapshotRes: { strategy_status?: string; name?: string; id?: number } = {};
    if (fromEvent) {
      snapshotRes = await strategySnapshot({ id });
      this.strategyStatus = snapshotRes.strategy_status;
      this.$store.commit(
        'app/SET_NAV_TITLE',
        `${`${this.$t('route-' + '策略详情')}`.replace('route-', '')} - #${snapshotRes.id} ${snapshotRes.name}${
          this.strategyStatusMap[snapshotRes.strategy_status]
        }`
      );
    }
    this.strategyId = snapshotRes?.id || id;
    // 策略快照end
    const targetDetail = await getTargetDetail({ strategy_ids: [this.strategyId] }).catch(() => ({}));
    const strategyDetail = snapshotRes.name
      ? snapshotRes
      : await getStrategyV2({ id: this.strategyId }).catch(() => ({}));
    this.updateRouteNavName(strategyDetail.name);
    const strategyTarget = targetDetail?.[this.strategyId];
    const filed = strategyDetail?.items?.[0]?.target?.[0]?.[0]?.field || '';
    const targetType = strategyTarget?.node_type || '';
    let targetList = strategyDetail?.items?.[0]?.target?.[0]?.[0]?.value || [];
    // 对旧版的策略target进行特殊处理
    if (targetType === 'INSTANCE' && filed === 'bk_target_ip') {
      targetList = targetList.map(item => ({ ...item, ip: item.bk_target_ip, bk_cloud_id: item.bk_target_cloud_id }));
    }
    targetList.length && (targetList[0].instances_count = strategyTarget?.instance_count || 0);
    if (this.strategyId) {
      const algorithms = strategyDetail?.items?.[0]?.algorithms || [];
      this.editStrategyIntelligentDetectList = algorithms
        .filter(algorithm => ['IntelligentDetect', 'TimeSeriesForecasting', 'AbnormalCluster'].includes(algorithm.type))
        .map(item => item.type);
    } else {
      this.editStrategyIntelligentDetectList = [];
    }
    if (!snapshotRes.name) {
      this.editAllowed = !!strategyDetail?.edit_allowed;
    }
    await this.handleProcessData({
      ...strategyDetail,
      targetDetail: { ...strategyTarget, detail: strategyTarget?.target_detail, target_detail: targetList }
    });
  }

  /* 返回包含DimensionName 的 AggCondition */
  getAggConditionOfHasDimensionName(aggCondition = [], curMetric = null) {
    return (aggCondition || [])
      .filter(setCondition => setCondition.key)
      .map(setCondition => ({
        ...setCondition,
        dimensionName: (() => {
          const dimensions = JSON.parse(JSON.stringify(curMetric?.dimensions || []));
          const dimensionName = dimensions.find(d => d.id === setCondition.key)?.name;
          const temp = dimensionName || setCondition?.dimensionName || setCondition?.dimension_name;
          return temp || setCondition.key;
        })(),
        value: typeof setCondition.value === 'string' ? setCondition.value.split(',') : setCondition.value
      }));
  }
  async handleProcessData(data) {
    this.baseConfig = {
      bk_biz_id: data.bk_biz_id,
      scenario: data.scenario,
      name: this.isClone ? `${data.name}_copy` : data.name,
      labels: data.labels || [],
      isEnabled: data.is_enabled,
      priority: data.priority || null
    };
    const { triggerConfig, recoveryConfig, noDataConfig } = this.analyzingConditions;
    const {
      create_user: createUser,
      create_time: createTime,
      update_time: updateTime,
      update_user: updateUser,
      bk_biz_id: bizId,
      targetDetail = [],
      detects: [
        {
          level = 1,
          connector = 'and',
          trigger_config: detectsTriggerConfig = triggerConfig,
          recovery_config: detectsRecoveryConfig = recoveryConfig
        } = { connector: 'and', level: 1 }
      ] = [],
      items: [
        {
          no_data_config: dataConfig = noDataConfig,
          expression,
          origin_sql: sourceCode,
          query_configs: queryConfigs,
          algorithms,
          functions
        }
      ],
      metric_type
      // actions: [{ notice_template: template = noticeTemplate }]
    } = data;
    this.expression = (expression || '').toLocaleLowerCase();
    this.localExpress = this.expression;
    this.localExpFunctions = functions || [];
    this.sourceData.sourceCode = sourceCode || '';
    this.record.data = {
      createUser,
      createTime,
      updateTime,
      updateUser
    };
    this.defaultCheckedTarget = targetDetail || { target_detail: [] };
    this.target = targetDetail?.target_detail || [];
    /* 是否为场景智能检测 */
    if (algorithms?.[0]?.type === MetricType.MultivariateAnomalyDetection) {
      const curMetricData = new MetricDetail({
        targetType: targetDetail?.node_type,
        objectType: targetDetail?.instance_type,
        sceneConfig: {
          algorithms,
          query_configs: queryConfigs
        }
      } as any);
      this.metricData.push(curMetricData);
      this.isMultivariateAnomalyDetection = true;
    } else if (queryConfigs?.length) {
      const isPrometheus = queryConfigs[0]?.data_source_label === PROMETHEUS;
      this.monitorDataEditMode = 'Edit';
      if (isPrometheus) {
        const promqlItem = queryConfigs[0];
        this.monitorDataEditMode = 'Source';
        this.sourceData.sourceCode = promqlItem.promql;
        this.sourceData.step = promqlItem.agg_interval;
      }
      const { metric_list: metricList = [] } = await getMetricListV2({
        bk_biz_id: bizId,
        // page: 1,
        // page_size: queryConfigs.length,
        // result_table_label: scenario, // 不传result_table_label，避免关联告警出现不同监控对象时报错
        conditions: [{ key: 'metric_id', value: queryConfigs.map(item => transformLogMetricId(item)) }]
      }).catch(() => ({}));
      this.metricData = queryConfigs.map(
        ({
          data_source_label,
          data_type_label,
          result_table_id,
          data_label,
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
          agg_interval,
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
            data_label,
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

          if (this.dataMode === 'realtime') {
            this.showRealtimeStrategy = true;
          }
          return new MetricDetail({
            ...curMetric,
            agg_method,
            agg_condition: this.getAggConditionOfHasDimensionName(agg_condition, curMetric),
            agg_dimension,
            agg_interval,
            alias: (alias || '').toLocaleLowerCase(),
            level,
            targetType: targetDetail?.node_type,
            objectType: targetDetail?.instance_type,
            query_string,
            functions: functions || [],
            intelligent_detect,
            metric_type,
            logMetricList: metricList
          });
        }
      );
      /* 当前选择器类型 */
      this.metricSelector.dataTypeLabel = this.metricData[0].data_type_label;
    }
    /* eslint-disable camelcase */
    const triggerConfigData = detectsTriggerConfig;
    const recoveryConfigData = detectsRecoveryConfig;
    const noDataConfigData = dataConfig;
    // const noticeTemplateData = template;
    triggerConfig.count = triggerConfigData.count || 0;
    triggerConfig.checkWindow = triggerConfigData.check_window || 0;
    triggerConfig.calendars = triggerConfigData.uptime?.calendars || [];
    // eslint-disable-next-line max-len
    triggerConfig.timeRanges =
      triggerConfigData.uptime?.time_ranges?.map?.(timeRange => [`${timeRange.start}:00`, `${timeRange.end}:59`]) ||
      DEFAULT_TIME_RANGE;
    recoveryConfig.checkWindow = recoveryConfigData.check_window || 0;
    noDataConfig.continuous = noDataConfigData.continuous || 0;
    noDataConfig.isEnabled = noDataConfigData.is_enabled || false;
    if (this.monitorDataEditMode === 'Edit') {
      noDataConfig.dimensions = noDataConfigData.agg_dimension || [];
    } else {
      this.judgingConditionEl.promqlDimensions = noDataConfigData.agg_dimension || [];
    }
    noDataConfig.level = noDataConfigData.level || 2;
    // noticeTemplate.anomalyTemplate = noticeTemplateData.anomaly_template || '';
    // 告警处理数据回显
    // this.actionList = (data.actions || []).map((item) => {
    //   this.$set(item, 'show', true);
    //   return item;
    // });
    // 告警处理回显(新)
    const action = data.actions;
    if (action) {
      this.actionsData = action.map(item => ({
        ...item,
        options: {
          converge_config: {
            ...item.options.converge_config,
            timedelta: item.options.converge_config.timedelta / 60
          }
        }
      }));
    } else {
      this.isActionEnabled = false;
    }
    // 通知设置回显(新)
    const { notice } = data;
    const legalDimensionList = this.metricData.reduce(
      (pre, cur) =>
        cur.agg_dimension?.length > pre.length
          ? cur.dimensions?.filter(set => cur.agg_dimension.includes(set.id as any))
          : pre,
      []
    );
    // eslint-disable-next-line max-len
    const isDimensionsAll = legalDimensionList.every(item =>
      (notice.options?.noise_reduce_config?.dimensions || []).includes(item.id)
    );
    this.noticeData = {
      ...notice,
      config: {
        ...notice.config,
        notify_interval: notice.config.notify_interval / 60
      },
      options: {
        converge_config: {
          need_biz_converge: notice.options.converge_config.need_biz_converge
        },
        exclude_notice_ways: {
          recovered: notice.options?.exclude_notice_ways?.recovered || [],
          closed: notice.options?.exclude_notice_ways?.closed || [],
          ack: notice.options?.exclude_notice_ways?.ack || []
        },
        noise_reduce_config: {
          dimensions: isDimensionsAll ? ['all'] : notice.options?.noise_reduce_config?.dimensions || [],
          is_enabled: notice.options?.noise_reduce_config?.is_enabled || false,
          count: notice.options?.noise_reduce_config?.count || 10
        },
        upgrade_config: {
          is_enabled: notice.options?.upgrade_config?.is_enabled || false,
          user_groups: notice.options?.upgrade_config?.user_groups || [],
          upgrade_interval: notice.options?.upgrade_config?.upgrade_interval || undefined
        },
        assign_mode: notice.options?.assign_mode || [],
        chart_image_enabled: !!notice.options?.chart_image_enabled
      },
      user_groups: notice.user_groups.filter(u => ['string', 'number'].includes(typeof u))
    };
    // 检测算法数据回显
    this.handleDetectionRulesUnit();
    // eslint-disable-next-line
    this.detectionConfig.data = algorithms.map(({ unit_prefix, ...item }) => this.displayDetectionRulesConfig(item));
    this.detectionDataBackfill = deepClone(this.detectionConfig.data);
    this.detectionConfig.connector = connector;
    this.detectionConfig.unit = algorithms?.[0]?.unit_prefix || ''; // eslint-disable-line
    this.metricSelector.type = metric_type || MetricType.TimeSeries;
  }
  // 检测算法回显空数据转换
  displayDetectionRulesConfig(item) {
    const { config } = item;
    if (item.type === 'IntelligentDetect' && !config.anomaly_detect_direct) config.anomaly_detect_direct = 'all';
    // 如果服务端没有返回 fetch_type 数据，这里将提供一个默认的数值。（向前兼容）
    // eslint-disable-next-line @typescript-eslint/no-unused-expressions
    if (['AdvancedRingRatio', 'AdvancedYearRound'].includes(item.type) && !config.fetch_type) config.fetch_type = 'avg';
    const isArray = typeTools.isArray(config);
    if (isArray) return item;
    Object.keys(config).forEach(key => {
      const value = config[key];
      if (value === null) config[key] = '';
    });
    return item;
  }

  // 弹出指标选择器
  handleShowMetric(item) {
    this.monitorDataEditMode = 'Edit';
    /* 关联告警 */
    if (item.type === 'alert' && !this.metricData.length) {
      this.handleAddNullMetric(item);
      this.expression = LETTERS[0];
    } else if (item.type === MetricType.MultivariateAnomalyDetection) {
      this.isMultivariateAnomalyDetection = true;
      // const nullMetric = new MetricDetail();
      // this.metricData.push(nullMetric);
    }
    this.handleAddNullMetric(item);
    this.handleResetMetricAlias();
    this.showRealtimeStrategy = !!window?.show_realtime_strategy;
  }

  // 继续添加指标
  handleShowMetricContinue(data: { type: MetricType; key: string; metric_id: string }) {
    this.metricSelectorTargetId = `#set-panel-item-${data.type}${data.key || ''}`;
    // if (!data.metric_id) {
    //   this.metricSelector.key = data.key;
    // }
    this.metricSelector.key = data.key;
    if (!this.metricData.length) {
      this.metricSelector.dataTypeLabel = data.type;
    }
    this.metricSelector.id = data.metric_id;
    this.metricSelector.type = data.type;
    this.metricSelector.show = true;
  }
  // 添加空指标
  handleAddNullMetric(data: { type: MetricType }) {
    this.metricSelector.dataTypeLabel = data.type;
    const nullMetric = new MetricDetail({
      metric_id: '',
      alias: LETTERS[this.metricData.length],
      data_type_label: this.metricSelector.dataTypeLabel
    } as any);
    this.metricData.push(nullMetric);
  }

  // 处理检测算法单位
  handleDetectionRulesUnit() {
    let notNeededDetectionUnit = false; //  handleResetMetricAlias不需要算法单位 汇聚方法为COUNT || 函数有ignore_unit: true的不需要算法单位
    const leng = this.metricData.length;
    if (leng === 1) {
      const firstMetric = this.metricData[0];
      const allFuncList = this.metricFunctions.reduce((total, cur) => total.concat(cur.children), []);
      const ignoreUnit = firstMetric.functions.some(
        item => !!allFuncList.find(set => item.id === set.id && set.ignore_unit)
      );
      notNeededDetectionUnit = firstMetric.agg_method === 'COUNT' || ignoreUnit;
    }
    if (!leng || leng > 1 || notNeededDetectionUnit) {
      this.detectionConfig.unit = '';
      this.detectionConfig.unitType = '';
    } else {
      this.detectionConfig.unitType = this.metricData[0].unit;
      !this.detectionConfig.unitType && (this.detectionConfig.unit = '');
    }
  }

  // 添加指标
  async handleAddMetric(metric: IMetricDetail) {
    await this.$nextTick();
    const list: IMetricDetail[] = !Array.isArray(metric) ? [metric] : metric;
    if (!this.metricData?.length) {
      this.metricData = list.map((item, index) => {
        const instance = new MetricDetail({ ...item, alias: LETTERS[index] });
        instance.setMetricType(this.metricSelector.type);
        return instance;
      });
      this.handleDetectionRulesUnit();
      this.expression = LETTERS.slice(0, list.length)
        .split('')
        .join(`${this.metricData[0].data_type_label === 'alert' ? ' && ' : ' + '}`);
      this.localExpress = this.expression;
      this.handleSetOtherData();
      this.handleResetMetricDimension();
      return;
    }

    // 切换不同的metricMetaId指标清空检测算法和检测算法回填数据
    if (`${list[0].data_source_label}|${list[0].data_type_label}` !== this.metricData[0].metricMetaId) {
      this.detectionConfig.data = [];
      this.detectionDataBackfill = [];
    }

    // const metricList = [...this.metricData];
    // for (let i = 0; i < metricList.length; i++) {
    //   const item = metricList[i];
    //   if (!list.some(set => set.metric_id === item.metric_id)) {
    //     metricList.splice(i, 1);
    //     if (i >= 0 && metricList.length > 0) {
    //       i -= 1;
    //     }
    //   }
    // }
    // if (this.metricData.length !== metricList.length) {
    //   this.metricData = [...metricList.map(item => new MetricDetail(item))];
    // }
    /* 点击空指标项增加 */
    // list = list.filter(item => this.metricData.every(set => set.metric_id !== item.metric_id));
    // this.metricData.push(...list.map(item => new MetricDetail(item)));
    let targetMetricIndex = 0;
    targetMetricIndex = this.metricData.findIndex(item => item.key === this.metricSelector.key);
    if (targetMetricIndex < 0) {
      targetMetricIndex = this.metricData.findIndex(item => item.metric_id === this.metricSelector.id);
    }
    const targetMetricItem = new MetricDetail(list[0]);
    targetMetricItem.setMetricType(this.metricSelector.type);
    this.$set(this.metricData, targetMetricIndex, targetMetricItem);
    if (this.metricData.length >= 1 && !!this.metricData[0].metric_id) {
      this.baseConfig.scenario = this.metricData[0].result_table_label;
    }
    this.handleDetectionRulesUnit();
    this.handleSetOtherData();
    this.handleResetMetricDimension();
    this.handleResetMetricAlias();
  }
  handleSetOtherData() {
    const hasRealtime = !!this.metricData?.some(item => item.metricMetaId === 'bk_monitor|event');
    if (!(this.metricSelector.type === MetricType.TimeSeries && this.metricData.length === 1 && !hasRealtime)) {
      this.dataMode = hasRealtime ? 'realtime' : 'converge';
    }
    if (this.dataMode === 'realtime') {
      this.showRealtimeStrategy = true;
    } else {
      this.showRealtimeStrategy = !!window?.show_realtime_strategy;
    }
  }
  handleResetMetricDimension() {
    const longDimension = this.metricData.reduce(
      (pre, cur) => (cur?.agg_dimension?.length > pre?.length ? cur.agg_dimension : pre),
      []
    );
    this.metricData.forEach(item => {
      item.agg_dimension = longDimension.filter(id => item.agg_dimension.includes(id));
    });
    // 设置无数据告警默认维度
    this.$nextTick(() => {
      this.setDefaultDimension();
    });
  }
  handleResetMetricAlias() {
    const metricData = this.metricData.filter(item => !!item.metric_id);
    this.metricData.forEach((item, index) => {
      item.alias = LETTERS[index];
      if (!this.expression.includes(item.alias)) {
        this.expression += ` ${item.data_type_label === 'alert' ? '&&' : '+'} ${item.alias}`;
        this.localExpress = this.expression;
      }
    });
    if (metricData.length < 2) {
      this.expression = metricData.length ? metricData[0].alias : '';
      this.localExpress = this.expression;
    }
  }
  handleDeleteMetric(index) {
    const deleteItem = this.metricData[index];
    if (deleteItem) {
      this.metricData.splice(index, 1);
      this.handleDetectionRulesUnit();
      this.handleResetMetricDimension();
      this.handleResetMetricAlias();
    }
    if (!this.metricData.length) {
      this.target = [];
      this.defaultCheckedTarget.target_detail = [];
      this.detectionConfig.data = [];
      this.dataMode = 'converge';
    }
  }

  // 指标选择器关闭事件
  handleHideMetricDialog(show) {
    this.metricSelector.show = show;
  }

  // 检测算法值更新
  handleDetectionRulesChange(v) {
    this.detectionConfig.data = v;
  }

  // 基本信息值更新
  handleBaseConfigChange() {}

  // 判断条件值更新
  handleJudgingChange() {}

  handleNoticeGroupChange() {}

  handleTargetChange(target) {
    this.target = target;
    this.defaultCheckedTarget.target_detail = target;
  }

  handleMouseDown(e) {
    const node = e.target;
    const { parentNode } = node;

    if (!parentNode) return;

    const nodeRect = node.getBoundingClientRect();
    const rect = parentNode.getBoundingClientRect();
    document.onselectstart = () => false;
    document.ondragstart = () => false;
    this.strategyView.isActive = true;
    const handleMouseMove = event => {
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

  async handleValidateStrategyConfig() {
    let validate = true;
    if (this.monitorDataEditMode === 'Source') {
      if (!this.sourceData.sourceCode) {
        this.$bkMessage({
          message: this.$t('promql不能为空'),
          theme: 'error',
          delay: 3000
        });
        validate = false;
      }
      if ((Number(this.sourceData.step) || 0) <= 0) {
        this.$bkMessage({
          message: this.$t('Step需填写合法的整数值'),
          theme: 'error',
          delay: 3000
        });
        validate = false;
      }
    }
    if (
      this.monitorDataEditMode === 'Edit' &&
      this.metricData.length > 1 &&
      this.metricData.some(item => item.agg_dimension.length > 0)
    ) {
      // 验证多指标的维度合法关系
      const longDimension = this.metricData.reduce(
        (pre, cur) => (cur.agg_dimension.length > pre.agg_dimension.length ? cur : pre),
        this.metricData[0]
      ).agg_dimension;
      if (this.metricData.some(item => item.agg_dimension.some(set => !longDimension.includes(set)))) {
        validate = false;
        this.$bkMessage({
          message: this.$t('多指标维度选择必须是相互包含关系'),
          theme: 'error',
          delay: 3000
        });
      }
    }
    const firstMetric = this.metricData?.[0];
    if (firstMetric?.data_type_label === 'alert' && this.metricData.length < 2) {
      validate = false;
      this.$bkMessage({
        message: this.$t('关联告警需至少选择2个告警进行管理'),
        theme: 'error',
        delay: 3000
      });
    }
    if (
      firstMetric?.metricMetaId === 'bk_log_search|log' &&
      firstMetric.agg_method !== 'COUNT' &&
      !firstMetric.curRealMetric
    ) {
      validate = false;
      this.$bkMessage({
        message: this.$t('索引集非COUNT汇聚方法需要选择一个指标'),
        theme: 'error',
        delay: 3000
      });
    }
    const promiseList = [];
    promiseList.push(this.baseConfigEl.validate()); // 校验基本信息
    this.detectionRulesEl && promiseList.push(this.detectionRulesEl.validate()); // 校验检测规则
    this.alarmHandlingListRef && promiseList.push(this.alarmHandlingListRef.validate());
    this.noticeConfigRef &&
      promiseList.push(
        this.noticeConfigRef.validator().catch(() => {
          this.noticeConfigPanelRef.handleExpandChange(true);
          return Promise.reject();
        })
      ); // 通知设置校验
    if (this.isMultivariateAnomalyDetection) {
      this.aiopsMonitorDataRef && promiseList.push(this.aiopsMonitorDataRef.validate());
    }
    const otherValidate = await Promise.all(promiseList)
      .then(() => true)
      .catch(() => false);
    const judgingValidate = this.isNeedJudgingCondition ? this.judgingConditionEl.validator() : true;

    return validate && judgingValidate && !this.sourceData.promqlError && otherValidate;
  }

  async handleSubmitStrategyConfig() {
    // 验证
    const validate = await this.handleValidateStrategyConfig();
    if (validate) {
      const { noDataConfig } = this.analyzingConditions;
      const itemsParams = [];
      /* 无数据配置 */
      const noDataConfigParams = {
        // 监控项名称
        continuous: noDataConfig.continuous, // 无数据判断周期
        is_enabled: noDataConfig.isEnabled, // 是否启用无数据告警
        agg_dimension:
          this.monitorDataEditMode === 'Source' ? this.judgingConditionEl.promqlDimensions : noDataConfig.dimensions, // 无数据检测维度
        level: noDataConfig.level // 无数据告警级别
      };
      if (this.isMultivariateAnomalyDetection) {
        const curMetricData = this.metricData[0] as IMetricDetail;
        itemsParams.push({
          name: curMetricData.sceneConfig.scene_name,
          no_data_config: noDataConfigParams,
          target: this.handleGetTargetParams(), // 监控目标
          expression: 'a',
          functions: [],
          origin_sql: '',
          query_configs: curMetricData.sceneConfig.query_configs,
          algorithms: curMetricData.sceneConfig.algorithms
        });
      } else {
        itemsParams.push({
          name: this.handleMetricName(), // 监控项名称
          no_data_config: {
            // 监控项名称
            continuous: noDataConfig.continuous, // 无数据判断周期
            is_enabled: noDataConfig.isEnabled, // 是否启用无数据告警
            agg_dimension:
              this.monitorDataEditMode === 'Source'
                ? this.judgingConditionEl.promqlDimensions
                : noDataConfig.dimensions, // 无数据检测维度
            level: noDataConfig.level // 无数据告警级别
          },
          target: this.handleGetTargetParams(), // 监控目标
          expression: this.expression?.toLocaleLowerCase?.() || 'a', // 表达式
          functions: this.localExpFunctions, // 表达式函数
          origin_sql: this.sourceData.sourceCode, // source
          // 指标信息
          query_configs:
            this.monitorDataEditMode === 'Source' ? this.handlePromsqlQueryConfig() : this.handleQueryConfig(),
          // 检测算法
          algorithms: this.getAlgorithmList(this.metricData[0])
        });
      }
      // 当 input 手动清空时 priority 为 空串，不符合后端的类型，这里做一次调整或转换。
      if (this.baseConfig.priority === '') this.baseConfig.priority = null;
      if (this.baseConfig.priority) {
        this.baseConfig.priority = Number(this.baseConfig.priority);
      }
      const params = {
        type: this.strategyType,
        ...this.baseConfig,
        items: itemsParams,
        // 检测配置列表
        detects: this.getLevelDetects(),
        // 告警处理数据
        // actions: this.actionList.filter(item => item.show)
        // 告警处理数据(新)
        actions: this.actionsData.map(item => ({
          ...item,
          options: {
            converge_config:
              'converge_func' in item.options.converge_config
                ? {
                    ...item.options.converge_config,
                    timedelta: item.options.converge_config.timedelta * 60
                  }
                : { is_enabled: false }
          }
        })),
        // 通知设置
        notice: {
          ...this.noticeData,
          config: {
            ...this.noticeData.config,
            notify_interval: this.noticeData.config.notify_interval * 60
          },
          options: {
            ...this.noticeData.options,
            noise_reduce_config: {
              ...this.noticeData.options.noise_reduce_config,
              is_enabled:
                this.metricData?.[0]?.data_type_label === 'time_series'
                  ? this.noticeData.options.noise_reduce_config.is_enabled
                  : false,
              dimensions: this.noticeData.options.noise_reduce_config.dimensions.includes('all')
                ? this.legalDimensionList.map(l => l.id)
                : this.noticeData.options.noise_reduce_config.dimensions
            }
          },
          user_groups: this.noticeData.user_groups.filter(u => ['string', 'number'].includes(typeof u))
        },
        metric_type: this.metricSelector.type || this.selectMetricData?.[0]?.metric_type || MetricType.TimeSeries
      };
      this.loading = true;
      // eslint-disable-next-line max-len
      await saveStrategyV2(
        transformDataKey(Object.assign(params, this.id && !this.isClone ? { id: this.id } : {}), true)
      )
        .then(() => {
          this.$bkMessage({
            theme: 'success',
            message: this.id && !this.isClone ? this.$t('编辑策略成功') : this.$t('创建策略成功')
          });
          this.$emit('save');
        })
        .catch(err => {
          console.log(err);
        })
        .finally(() => {
          this.loading = false;
        });
    }
  }

  /**
   * @description: 处理query_config提交参数
   */
  handleQueryConfig(type: 'sumbit' | 'promsql' = 'sumbit') {
    const hasIntelligentDetect = this.detectionConfig?.data?.some(item => item.type === 'IntelligentDetect');
    return this.selectMetricData.map(item => {
      const common = {
        data_label: item.curRealMetric?.data_label || item.data_label,
        data_source_label: item.curRealMetric?.data_source_label || item.data_source_label,
        data_type_label: item.curRealMetric?.data_type_label || item.data_type_label,
        alias: item.alias?.toLocaleLowerCase?.() || 'a', // 表达式上对应的别名
        result_table_id: item.curRealMetric?.result_table_id || item.result_table_id || '',
        agg_method: this.dataMode === 'realtime' ? 'REAL_TIME' : item.agg_method,
        agg_interval: item.agg_interval,
        agg_dimension: item.agg_dimension,
        agg_condition: item.agg_condition.filter(item => item.key && item.value?.length),
        metric_field: item.curRealMetric?.metric_field || item.metric_field,
        unit: this.detectionConfig.unit ? item.unit : '',
        metric_id: item.metric_id
      };

      !common.data_label && delete common.data_label;

      // 提交所需参数
      const submit = {
        index_set_id: item.index_set_id,
        query_string: item.keywords_query_string,
        custom_event_name: item.metric_field || item.custom_event_name,
        functions: hasIntelligentDetect ? [] : item.functions,
        intelligent_detect: this.id && hasIntelligentDetect ? item.intelligent_detect : undefined,
        time_field: (hasIntelligentDetect ? 'dtEventTimeStamp' : item.time_field) || 'time',
        bkmonitor_strategy_id: item.metric_field || item.bkmonitor_strategy_id,
        alert_name: item.metric_field
      };
      // promsql所需参数
      const promsql = {
        functions: item.functions
      };

      const result = Object.assign(common, type === 'sumbit' ? submit : promsql);
      return result;
    });
  }

  /* promsql模式下query_config提交参数 */
  handlePromsqlQueryConfig() {
    return [
      {
        data_source_label: PROMETHEUS,
        data_type_label: 'time_series',
        promql: this.sourceData.sourceCode,
        agg_interval: this.sourceData.step,
        alias: 'a'
      }
    ];
  }

  /**
   * @description: 处理保存时监控项名字
   */
  handleMetricName() {
    if (this.monitorDataEditMode === 'Source') {
      return this.baseConfig.name;
    }
    const exp = this.expression || 'a';
    const name = exp.replace(/[a-zA-z]/g, (subStr: string) => {
      const { agg_method = '', metric_field_name = '' } =
        this.metricData.find(item => subStr?.toLocaleLowerCase() === item.alias?.toLocaleLowerCase()) || {};
      return metric_field_name ? `${agg_method}(${metric_field_name})` : subStr;
    });
    return name;
  }

  /**
   * @description: 处理新建参数-检测算法
   * @param {MetricDetail} item 第一条指标数据
   * @return {*}
   */
  getAlgorithmList(item: MetricDetail) {
    let algorithmList = [];
    // 系统事件
    if (item?.metricMetaId === 'bk_monitor|event') {
      algorithmList.push({
        level: item.level,
        type: '',
        config: [],
        unit_prefix: ''
      });
    } else {
      algorithmList = this.detectionConfig.data.map(({ level, type, config }) => ({
        level,
        type,
        config: this.handleDetectionRulesConfig(config),
        unit_prefix: (() => {
          if (this.monitorDataEditMode === 'Source') {
            return '';
          }
          return this.needShowUnit ? this.detectionConfig.unit : '';
        })()
      }));
    }
    return algorithmList;
  }

  // 提交数据检测算法转换空数据
  handleDetectionRulesConfig(config) {
    const isArray = typeTools.isArray(config);
    if (isArray) {
      return config;
    }
    Object.keys(config).forEach(key => {
      const value = config[key];
      if (value === '') config[key] = null;
    });
    return config;
  }

  // 处理提交参数detects
  getLevelDetects() {
    const levelMap = [];
    const { data, connector } = this.detectionConfig;
    // 场景智能异常检测
    if (this.isMultivariateAnomalyDetection) {
      const level = this.metricData?.[0]?.sceneConfig?.algorithms?.[0]?.level;
      level && levelMap.push(level);
    } else if (
      // 系统事件
      this.selectMetricData.length &&
      this.selectMetricData.every(item => item.metricMetaId === 'bk_monitor|event' || item.data_type_label === 'alert')
    ) {
      levelMap.push(this.metricData[0].level);
    } else {
      data.forEach(item => {
        if (!levelMap.includes(item.level)) levelMap.push(item.level);
      });
    }
    const { triggerConfig, recoveryConfig } = this.analyzingConditions;
    const detects = levelMap.map(level => ({
      level, // 检测算法对应告警级别
      expression: this.isFtaAlert ? this.expression : '', // 计算表达式 为空
      // 触发配置
      trigger_config: {
        // 触发次数
        count: triggerConfig.count,
        // 触发周期
        check_window: triggerConfig.checkWindow,
        uptime: {
          // 关联日历
          calendars: triggerConfig.calendars,
          // 生效时间段
          time_ranges: triggerConfig.timeRanges.map(item => ({
            start: item[0].replace(/:\d{2}$/, ''),
            end: item[1].replace(/:\d{2}$/, '')
          }))
        }
      },
      // 恢复配置
      recovery_config: {
        // 恢复周期
        check_window: recoveryConfig.checkWindow
      },
      // 算法连接符
      connector
    }));
    return detects;
  }
  // 获取监控目标报错参数值
  handleGetTargetParams() {
    const [metricItem] = this.metricData;
    if (!metricItem) return [];
    if (metricItem.canSetTarget && this.target?.length) {
      let field = '';
      if (metricItem.objectType === 'HOST') {
        field = hostTargetFieldType[metricItem.targetType];
      } else {
        field = serviceTargetFieldType[metricItem.targetType];
      }
      return this.target?.length
        ? [
            [
              {
                field,
                method: 'eq',
                value: this.handleCheckedData(metricItem.targetType, this.target)
              }
            ]
          ]
        : [];
    }
    return [];
  }
  // 简化参数给后端，不然会报错
  handleCheckedData(type: string, data: any[]) {
    const checkedData = [];
    if (type === 'INSTANCE') {
      data.forEach(item => {
        checkedData.push({
          ip: item.ip,
          bk_cloud_id: item.bk_cloud_id,
          bk_host_id: item.bk_host_id,
          bk_supplier_id: item.bk_supplier_id
        });
      });
    } else {
      data.forEach(item => {
        checkedData.push({
          bk_inst_id: item.bk_inst_id,
          bk_obj_id: item.bk_obj_id
        });
      });
    }
    return checkedData;
  }
  handleUnitChange(v: string) {
    this.detectionConfig.unit = v;
  }
  connectorChange(v: 'and' | 'or') {
    this.detectionConfig.connector = v;
  }
  @debouceDecorator(300)
  handleExpressionChange(v: string) {
    this.expression = v;
  }
  async handleExpressionBlur() {
    await this.$nextTick();
    this.localExpress = this.expression;
  }
  handleExpFunctionsChange(functions: IFunctionsValue[]) {
    this.localExpFunctions = functions;
  }
  handleSourceChange(v: string) {
    this.sourceData.sourceCode = v;
  }
  handleSourceStepChange(v: number | string) {
    this.sourceData.step = v;
  }
  // 清空指标
  handleClearMetric() {
    this.metricData = [];
    this.target = [];
    this.detectionConfig.data = [];
    this.detectionDataBackfill = [];
    this.defaultCheckedTarget.target_detail = [];
    this.dataMode = 'converge';
    this.sourceData = {
      ...this.sourceData,
      step: 60,
      sourceCode: '',
      errorMsg: '',
      promqlError: false,
      sourceCodeCache: ''
    };
    this.monitorDataEditMode = 'Edit';
    this.isMultivariateAnomalyDetection = false;
  }
  // 切换监控数据模式
  handleModeChange(v: dataModeType) {
    this.dataMode = v;
    this.metricData.forEach(item => {
      item.agg_method =
        v === 'realtime' ? 'REAL_TIME' : item.method_list?.[0]?.id || (item.onlyCountMethod ? 'COUNT' : 'AVG');
    });
  }
  // 跳转到编辑策略
  handleGoEdit() {
    this.$router.push({
      name: 'strategy-config-edit',
      params: {
        id: String(this.strategyId || this.id)
      }
    });
  }
  // 获取策略模板变量列表
  async handleGetVariateList() {
    const data = await this.getNoticeVariableList();
    const { noticeTemplate } = this.analyzingConditions;
    noticeTemplate.variateList = data;
    noticeTemplate.triggerList = data.reduce((pre, cur) => {
      pre.push(...cur.items);
      return pre;
    }, []);
  }
  // 选择监控目标时需切换target_type
  handleTargetTypeChange(v: string) {
    this.metricData.forEach(item => (item.targetType = v));
  }
  // 切换监控对象
  changeScenario(v) {
    this.baseConfig.scenario = v;
  }
  /**
   * @description: 记录当前操作的告警处理
   * @param {number} index 告警处理索引
   * @return {*}
   */
  getActionIndex(index: number) {
    this.curActionIndex = index;
  }
  /**
   * @description: 处理新增告警组返回
   * @param {*}
   * @return {*}
   */
  async handleAddNoticeGroup(isEdit = false) {
    if (isEdit) {
      await this.getAlarmGroupList();
      return;
    }
    this.loading = true;
    await this.getAlarmGroupList();
    const id = +this.$route.params.alarmGroupId;
    this.noticeData.user_groups.push(id);
    this.loading = false;
  }

  /**
   * @description: 新增处理套餐
   * @param {*} isEdit // 是否从处理套餐编辑页面回来
   * @return {*}
   */
  async handleAddMeal(isEdit = false) {
    if (isEdit) {
      await this.getActionConfigList();
      return;
    }
    const id = +this.$route.params.mealId;
    this.loading = true;
    await this.getActionConfigList();
    const pluginType = this.actionConfigList.find(item => item.id === id).plugin_type;
    if (pluginType === 'notice') {
      // 告警通知
      this.noticeData.config_id = id;
    } else {
      // 告警处理
      if (this.actionIndex > -1) {
        this.actionsData[this.actionIndex].config_id = id;
      }
    }
    this.loading = false;
  }

  /**
   * @description: 处理无数据告警联动
   * @param {boolean} val
   * @return {*}
   */
  // handleNoDataChange(val: boolean) {
  // this.alarmHandlingRef.handleNoDataHandling(val);
  // }

  /**
   * @description: 新增添加一条默认的告警时处理
   * @param {*}
   * @return {*}
   */
  // addDefaultAlarmHandling() {
  //   // 新建默认选中告警异常处理
  //   !this.id
  //     && !this.actionList.length
  //     && this.actionList.push({
  //       signal: 'abnormal',
  //       config_id: 1,
  //       user_groups: [],
  //       show: true
  //     });
  // }
  /**
   * @description: promql语法报错处理
   * @param {boolean} hasError
   * @param {IDataRetrieval} type
   */
  handlePromqlError(hasError: boolean, type: IDataRetrieval.promEventType) {
    this.sourceData.promqlError = hasError;
    !hasError && this.handlePromsqlToQueryConfig(type);
  }
  /**
   * @description: promsql语法转query_config配置
   * @param {string} sql
   */
  async handlePromsqlToQueryConfig(type?: IDataRetrieval.promEventType) {
    if (
      !this.sourceData.sourceCode ||
      (this.sourceData.sourceCodeCache === this.sourceData.sourceCode && type === 'blur')
    )
      return;
    this.monitorDataLoading = true;
    const params = {
      promql: this.sourceData.sourceCode,
      step: this.sourceData.step
    };
    const res = await promqlToQueryConfig('', params, { needMessage: false })
      .then(res => {
        this.sourceData.promqlError = false;
        this.sourceData.errorMsg = '';
        return res;
      })
      .catch(err => {
        this.sourceData.promqlError = true;
        this.monitorDataLoading = false;
        this.sourceData.errorMsg = err.data.message || '';
      });
    if (this.sourceData.promqlError || ['blur', 'enter'].includes(type)) {
      this.monitorDataLoading = false;
      return;
    }
    const targetRes = res || {
      expression: 'a',
      query_configs: this.metricData
    };
    this.expression = targetRes.expression || 'a';
    this.sourceData.sourceCodeCache = this.sourceData.sourceCode;
    const { metric_list: metricList = [] } = await getMetricListV2({
      // page: 1,
      // page_size: res.query_configs.length,
      conditions: [{ key: 'metric_id', value: targetRes.query_configs.map(item => item.metric_id) }]
    }).catch(() => {
      this.monitorDataLoading = false;
      return {};
    });
    if (metricList.length) {
      this.metricData = targetRes.query_configs.map(item => {
        const metricItem = metricList?.find(set => set.metric_id === item.metric_id);
        const resultTableIdList = (item.result_table_id || metricItem.result_table_id).split('.');
        const curMetric = metricItem || {
          data_source_label: metricList?.data_source_label || item.data_source_label,
          metric_field_name: item.metric_field,
          metric_field: item.metric_field,
          result_table_label_name: item.data_source_label,
          related_name: resultTableIdList[0],
          result_table_name: resultTableIdList[1],
          data_label: item.data_label
        };
        return new MetricDetail({
          ...curMetric,
          agg_method: item.agg_method,
          agg_condition: this.getAggConditionOfHasDimensionName(item.agg_condition, curMetric),
          agg_dimension: item.agg_dimension,
          agg_interval: item.agg_interval,
          alias: item.alias?.toLocaleLowerCase?.(),
          functions: item.functions || []
        });
      });
    } else {
      // const { metric_list: metricList = [] } = await getMetricListV2({
      //   // page: 1,
      //   // page_size: res.query_configs.length,
      //   conditions: [],
      //   data_type_label: this.metricData?.[0]?.data_type_label || 'time_series',
      //   page: 1,
      //   page_size: 1
      // }).catch(() => {
      //   this.monitorDataLoading = false;
      //   return {};
      // });
      // if (metricList.length) {
      //   this.metricData = metricList.map(item => new MetricDetail({
      //     ...item,
      //     agg_method: item.agg_method,
      //     agg_condition: item.agg_condition,
      //     agg_dimension: item.agg_dimension,
      //     agg_interval: item.agg_interval,
      //     alias: item.alias?.toLocaleLowerCase?.() || 'a',
      //     functions: item.functions || []
      //   }));
      // }
      const metricIds = targetRes.query_configs.map(item => item.metric_id);
      this.sourceData.errorMsg = `${metricIds.join('、')}${this.$t('指标不存在')}`;
      this.monitorDataLoading = false;
      return;
    }
    this.monitorDataEditMode = 'Edit';
    this.monitorDataLoading = false;
  }

  /**
   * @description: query_config配置转promsql语法
   */
  async handleQueryConfigToPromsql() {
    if (this.metricData.some(item => item.isNullMetric)) return false;
    this.monitorDataLoading = true;
    const param = {
      query_config_format: 'strategy',
      expression: this.expression?.toLocaleLowerCase?.(),
      query_configs: this.handleQueryConfig('promsql')
    };
    const res = await queryConfigToPromql('', param, { needMessage: false })
      .catch(err => {
        this.metricDataErrorMsg = err.data.message || err.msg || '';
        return false;
      })
      .finally(() => {
        setTimeout(() => (this.monitorDataLoading = false), 0);
      });
    if (!res) return false;
    this.sourceData.sourceCode = res.promql;
    this.sourceData.sourceCodeCache = res.promql;
    return res;
  }
  /**
   * @description: 切换指标的编辑模式
   * @param {EditModeType} mode
   */
  async handleEditModeChange({ mode }: { mode: EditModeType; hasError: boolean }) {
    if (mode === 'Source') {
      if (this.metricData.every(item => item.isNullMetric)) {
        this.sourceData.sourceCode = '';
        this.sourceData.promqlError = false;
        this.monitorDataEditMode = mode;
        return;
      }
      const success = await this.handleQueryConfigToPromsql();
      if (!!success) this.monitorDataEditMode = mode;
    } else {
      if (!this.sourceData.sourceCode) {
        this.sourceData.promqlError = false;
        this.metricData = [];
        this.handleAddNullMetric({ type: MetricType.TimeSeries });
        this.monitorDataEditMode = mode;
        return;
      }
      this.handlePromsqlToQueryConfig();
    }
  }

  // 无数据告警默认维度
  getDefaultDimension(scenario: string) {
    const hostScenario = ['os', 'host_process', 'host_device'];
    const serviceScenario = ['service_module', 'component', 'service_process'];
    const uptimeScenario = ['uptimecheck'];
    const metricData = deepClone(this.metricData).sort(
      (a, b) =>
        b.dimensions.filter(dim => dim.is_dimension || dim.is_dimension === undefined).length -
        a.dimensions.filter(dim => dim.is_dimension || dim.is_dimension === undefined).length
    )[0];
    const aggDimension = metricData.agg_dimension;
    if (uptimeScenario.includes(scenario)) {
      return ['task_id'];
    }
    if (serviceScenario.includes(scenario)) {
      if (aggDimension.includes('bk_target_service_instance_id')) {
        return ['bk_target_service_instance_id'];
      }
      if (this.target.length) {
        return ['bk_obj_id', 'bk_inst_id'];
      }
    }
    if (hostScenario.includes(scenario)) {
      if (aggDimension.includes('bk_target_ip')) {
        return ['bk_target_ip', 'bk_target_cloud_id'];
      }
      if (aggDimension.includes('ip')) {
        return ['ip', 'bk_cloud_id'];
      }
      return ['bk_target_ip', 'bk_target_cloud_id'];
    }
  }

  // 设置默认维度
  setDefaultDimension() {
    if (this.metricData.length) {
      const aggDimension = this.metricData.reduce((acc, cur) => {
        cur.agg_dimension.forEach(dim => {
          if (!acc.includes(dim)) {
            acc.push(dim);
          }
        });
        return acc;
      }, []);
      const allDimension =
        this.metricData
          .map(item => item.dimensions.filter(dim => dim.is_dimension || dim.is_dimension === undefined))
          .sort((a, b) => b.length - a.length)[0]
          ?.filter(dim => aggDimension.includes(dim.id))
          .map(item => item.id) || [];
      const defalutDimension =
        this.getDefaultDimension(this.baseConfig.scenario)?.filter(item => allDimension.includes(item)) || [];
      this.analyzingConditions.noDataConfig.dimensions = defalutDimension;
    }
  }

  /** 智能检测算法图表类型 */
  handleAiopsChartType(type: ChartType) {
    this.localAiopsChartType = type;
  }

  /** 智能检测算法模型数据变更 */
  handleModelChange(data: IModelData[]) {
    this.aiopsModelMdList = data;
  }

  /* 当前hover的类型 */
  handleEmptyHoverType(type: string) {
    this.descriptionType = type;
  }

  /* 判断条件校验未通过调用 */
  judgingValidatorErr() {
    (this.$refs.judgingConditionGroupPanel as any).expand = true;
    setTimeout(() => {
      (this.$refs.judgingConditionGroupPanel as any).$el.scrollIntoView();
    }, 50);
  }

  /**
   * @param val 是否展示了表达式
   */
  handleShowExpress(val: boolean) {
    this.isShowExpress = val;
  }

  // 点击智能算法展开对应的算法说明
  handleRuleClick(index: number) {
    if (index !== -1) this.activeModelIndex = index;
  }

  /* 场景智能检测数据 */
  handleSceneConfigChange(sceneConfig) {
    if (this.metricData.length) {
      this.metricData = [
        new MetricDetail({
          ...this.metricData[0],
          sceneConfig
        })
      ];
    } else {
      this.metricData = [
        new MetricDetail({
          sceneConfig
        } as any)
      ];
    }
  }

  metricDataContent() {
    /* 是否为场景智能检测 */
    if (this.isMultivariateAnomalyDetection) {
      return (
        <AiopsMonitorData
          ref='aiopsMonitorData'
          defaultCheckedTarget={this.defaultCheckedTarget}
          metricData={this.metricData as any}
          onChange={this.handleSceneConfigChange}
          onTargetTypeChange={this.handleTargetTypeChange}
          onTargetChange={this.handleTargetChange}
        ></AiopsMonitorData>
      );
    }
    return (
      <MonitorData
        readonly={this.isDetailMode}
        dataMode={this.dataMode}
        metricData={this.metricData}
        source={this.sourceData.sourceCode}
        expression={this.expression}
        expFunctions={this.localExpFunctions}
        defaultCheckedTarget={this.defaultCheckedTarget}
        hasAIntelligentDetect={this.hasAIntelligentDetect}
        loading={this.monitorDataLoading}
        editMode={this.monitorDataEditMode}
        promqlError={this.sourceData.promqlError}
        dataTypeLabel={this.metricSelector.dataTypeLabel}
        sourceStep={this.sourceData.step}
        hasAiOpsDetect={this.hasAiOpsDetect}
        errMsg={this.errMsg}
        onMethodChange={this.handleDetectionRulesUnit}
        onFunctionChange={this.handleDetectionRulesUnit}
        onModeChange={this.handleModeChange}
        onExpressionChange={this.handleExpressionChange}
        onExpressionBlur={this.handleExpressionBlur}
        onExpFunctionsChange={this.handleExpFunctionsChange}
        onSourceChange={this.handleSourceChange}
        onTargetChange={this.handleTargetChange}
        onDelete={this.handleDeleteMetric}
        onAddMetric={this.handleShowMetricContinue}
        onAddNullMetric={this.handleAddNullMetric}
        onTargetTypeChange={this.handleTargetTypeChange}
        onPromqlEnter={hasError => this.handlePromqlError(hasError, 'enter')}
        onPromqlBlur={hasError => this.handlePromqlError(hasError, 'blur')}
        onPromqlFocus={() => {
          this.sourceData.promqlError = false;
          this.sourceData.errorMsg = '';
        }}
        onclearErr={() => (this.metricDataErrorMsg = '')}
        onEditModeChange={this.handleEditModeChange}
        onShowExpress={this.handleShowExpress}
        onSouceStepChange={this.handleSourceStepChange}
      />
    );
  }

  render() {
    return (
      <div class='strategy-config-set'>
        {this.isDetailMode && (
          <div class='config-header'>
            {this.strategyStatus !== 'DELETED' ? (
              <bk-button
                text
                style='margin-right: 8px'
                v-authority={{ active: !this.authority.MANAGE_AUTH }}
                onClick={() => (this.authority.MANAGE_AUTH ? this.handleGoEdit() : this.handleShowAuthorityDetail())}
              >
                {this.$t('编辑策略')}
              </bk-button>
            ) : undefined}{' '}
            |
            <bk-button
              text
              style='margin-left: 8px'
              onClick={() => (this.record.show = true)}
            >
              {this.$t('查看变更记录')}
            </bk-button>
          </div>
        )}
        <CommonNavBar
          class='strategy-config-nav'
          routeList={this.routeList}
          needCopyLink={false}
          needBack={true}
          navMode={'copy'}
        >
          <div slot='custom'>{this.navName}</div>
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
          class='set-content'
          v-bkloading={{ isLoading: this.loading }}
          ref='contentRef'
        >
          {/* <!-- 策略编辑和新建 --> */}
          <div class='set-content-left'>
            <GroupPanel
              title={this.$t('基本信息')}
              class='mb10'
            >
              <BaseConfig
                ref='base-config'
                bizList={this.bizList}
                bizId={this.bizId}
                readonly={this.isDetailMode}
                data={this.baseConfig}
                scenarioList={this.scenarioList}
                scenarioReadonly={
                  this.monitorDataEditMode === 'Source' ? false : !!this.metricData.some(item => !!item.metric_id)
                }
                on-change={this.handleBaseConfigChange}
              />
            </GroupPanel>

            <GroupPanel
              title={this.$t('监控数据')}
              class='mb10'
            >
              {!this.isDetailMode && (
                <bk-button
                  on-click={this.handleClearMetric}
                  style={{ paddingRight: 0, display: this.metricData.length ? 'inline-block' : 'none' }}
                  slot='tools'
                  size='small'
                  text
                  theme='primary'
                >
                  {this.$t('清除')}
                </bk-button>
              )}
              {!this.metricData.length && !this.sourceData.sourceCode
                ? !this.loading && (
                    <MonitorDataEmpty
                      on-add-metric={this.handleShowMetric}
                      onHoverType={this.handleEmptyHoverType}
                    />
                  )
                : this.metricDataContent()}
            </GroupPanel>
            {this?.metricData?.filter(item => !!item.metric_id)?.[0]?.canSetDetEctionRules ||
            this.monitorDataEditMode === 'Source' ? (
              <GroupPanel
                key='detectionRulesGroupPanel' // 增加唯一key避免与其他grouppanel混淆出错
                title={this.$t('检测规则')}
                subtitle={this.$t('通过查询的数据按检测规则判断是否需要进行告警')}
                class='mb10'
                show-expand={!this.isDetailMode}
                default-expand={true}
              >
                <DetectionRules
                  ref='detection-rules'
                  metricData={this.selectMetricData}
                  readonly={this.isDetailMode}
                  backfillData={this.detectionDataBackfill}
                  value={this.detectionConfig.data}
                  unit={this.detectionConfig.unit}
                  connector={this.detectionConfig.connector}
                  unitType={this.detectionConfig.unitType}
                  isEdit={this.isEdit}
                  dataMode={this.dataMode}
                  needShowUnit={this.needShowUnit}
                  onModelChange={this.handleModelChange}
                  onAiopsTypeChange={this.handleAiopsChartType}
                  onConnectorChange={this.connectorChange}
                  onChange={this.handleDetectionRulesChange}
                  onUnitChange={this.handleUnitChange}
                  onRuleClick={this.handleRuleClick}
                ></DetectionRules>
              </GroupPanel>
            ) : undefined}
            {
              <GroupPanel
                key='judgingConditionGroupPanel'
                title={this.$t('判断条件')}
                subtitle={this.$t('判断最终是否要产生告警')}
                readonly={this.isDetailMode}
                class='mb10'
                show-expand={!this.isDetailMode}
                default-expand={this.isDetailMode}
                ref='judgingConditionGroupPanel'
              >
                <JudgingCondition
                  ref='judgingCondition'
                  data={this.analyzingConditions}
                  scenario={this.baseConfig.scenario}
                  // onNoDataChange={this.handleNoDataChange}
                  metricData={this.metricData}
                  isDetailMode={this.isDetailMode}
                  isAlert={!this.isNeedJudgingCondition}
                  // judgeTimeRange={this.judgeTimeRange}
                  legalDimensionList={this.legalDimensionList}
                  calendarList={this.calendarList}
                  editMode={this.monitorDataEditMode}
                  onChange={this.handleJudgingChange}
                  // onTimeChange={(v: string[]) => this.judgeTimeRange = v}
                  onValidatorErr={this.judgingValidatorErr}
                ></JudgingCondition>
              </GroupPanel>
            }
            <GroupPanel
              title={this.$t('告警处理')}
              subtitle={this.$t('告警产生后是否要触发动作')}
              class='mb10'
              show-expand={!this.isDetailMode}
            >
              <AlarmHandlingList
                ref='alarmHandlingList'
                value={this.actionsData}
                allAction={actionConfigGroupList(this.actionConfigList)}
                allDefense={this.defenseList}
                readonly={this.isDetailMode}
                strategyId={this.id ? +this.id : ''}
                onChange={v => (this.actionsData = v)}
                onAddMeal={(v: number) => (this.actionIndex = v)}
              ></AlarmHandlingList>
            </GroupPanel>
            <GroupPanel
              ref='noticeConfigPanel'
              title={this.$t('通知设置')}
              subtitle={this.$t('告警产生后是否要触发通知')}
              class='mb10'
              show-expand={!this.isDetailMode}
              defaultExpand={false}
              expand={!!this.detectionConfig.data.length}
              onExpand={() => (this.$refs.noticeConfigNew as NoticeConfigNew)?.excludePopInit()}
            >
              {!this.loading && (
                <NoticeConfigNew
                  ref='noticeConfigNew'
                  allAction={actionConfigGroupList(this.actionConfigList)}
                  userList={this.alarmGroupList}
                  value={this.noticeData}
                  readonly={this.isDetailMode}
                  strategyId={this.id ? +this.id : ''}
                  isExecuteDisable={!this.isActionEnabled}
                  legalDimensionList={this.legalDimensionList}
                  dataTypeLabel={this.metricData?.[0]?.data_type_label || ''}
                  onChange={(data: INoticeValue) => (this.noticeData = data)}
                ></NoticeConfigNew>
              )}
            </GroupPanel>
            {!this.isDetailMode && (
              <div class='set-footer mt20 mb20'>
                <div
                  v-bk-tooltips={{
                    disabled: this.submitBtnTipDisabled,
                    content: !this.editAllowed ? this.$t('内置策略不允许修改') : this.$t('未选择监控数据'),
                    allowHTML: false
                  }}
                >
                  <bk-button
                    disabled={this.submitBtnDisabled}
                    theme='primary'
                    class='save-btn'
                    on-click={this.handleSubmitStrategyConfig}
                  >
                    {this.$t('提交')}
                  </bk-button>
                </div>
                <bk-button
                  class='btn cancel'
                  on-click={this.handleCancel}
                >
                  {this.$t('取消')}
                </bk-button>
              </div>
            )}
            <div style='padding-top: 16px;'></div>
          </div>
          {/* <!-- 策略辅助视图 --> */}
          <div
            class='set-content-right'
            style={{ width: this.strategyView.show ? this.rightWidth : 0 }}
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
                metricData={this.selectMetricData}
                detectionConfig={this.detectionConfig}
                expression={this.localExpress}
                expFunctions={this.localExpFunctions}
                legalDimensionList={this.legalDimensionList}
                dataMode={this.dataMode}
                editMode={this.monitorDataEditMode}
                sourceData={this.sourceData}
                aiopsChartType={this.localAiopsChartType}
                aiopsModelMdList={this.aiopsModelMdList}
                activeModelMd={this.activeModelIndex}
                descriptionType={this.descriptionType}
                isMultivariateAnomalyDetection={this.isMultivariateAnomalyDetection}
                strategyTarget={this.strategyTarget}
              />
            </div>
          </div>
        </div>
        <MetricSelector
          metricId={this.metricSelector.id}
          show={this.metricSelector.show}
          targetId={this.metricSelectorTargetId}
          scenarioList={this.scenarioAllList}
          type={this.metricSelector.type}
          metricKey={this.metricSelector.key}
          defaultScenario={this.baseConfig.scenario}
          onShowChange={val => (this.metricSelector.show = val)}
          onSelected={this.handleAddMetric}
        ></MetricSelector>
        {/* <StrategyMetricSelector
          type={this.metricSelector.type}
          show={this.metricSelector.show}
          isEdit={this.metricSelector.isEdit}
          monitorType={this.baseConfig.scenario}
          metricData={this.metricData}
          scenarioList={this.scenarioList}
          multiple={this.dataMode !== 'realtime'}
          strategyType={this.strategyType}
          on-change={this.handleAddMetric}
          on-on-hide={this.handleHideMetricDialog}
          on-scenario={this.changeScenario}
        ></StrategyMetricSelector> */}
        <ChangeRcord
          recordData={this.record.data}
          show={this.record.show}
          onUpdateShow={v => (this.record.show = v)}
        />
      </div>
    );
  }
}
