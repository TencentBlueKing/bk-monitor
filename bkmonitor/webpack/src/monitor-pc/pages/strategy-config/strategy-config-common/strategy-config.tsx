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
import { Component, Mixins, Prop, Watch } from 'vue-property-decorator';
import { ofType, modifiers } from 'vue-tsx-support';

import { addListener, removeListener } from '@blueking/fork-resize-detector';
import SearchSelect from '@blueking/search-select-v3/vue2';
import dayjs from 'dayjs';
import { CancelToken } from 'monitor-api/cancel';
import { exportConfigFile } from 'monitor-api/modules/as_code';
import { noticeGroupList } from 'monitor-api/modules/notice_group';
import { disableShield } from 'monitor-api/modules/shield';
import {
  deleteStrategyV2,
  getScenarioList,
  getStrategyListV2,
  getTargetDetail,
  updatePartialStrategyV2,
} from 'monitor-api/modules/strategies';
import { commonPageSizeGet, commonPageSizeSet, copyText, tryURLDecodeParse } from 'monitor-common/utils';
import { debounce } from 'throttle-debounce';

import EmptyStatus from '../../../components/empty-status/empty-status';
import TableSkeleton from '../../../components/skeleton/table-skeleton';
import SvgIcon from '../../../components/svg-icon/svg-icon.vue';
import TableFilter from '../../../components/table-filter/table-filter.vue';
import { isEn } from '../../../i18n/lang';
import authorityMixinCreate from '../../../mixins/authorityMixin';
import UserConfigMixin from '../../../mixins/userStoreConfig';
import AuthComponent from '../../../pages/exception-page/auth-component';
import { downFile } from '../../../utils';

// import StrategySetTarget from '../strategy-config-set/strategy-set-target/strategy-set-target.vue';
import AlarmGroupDetail from '../../alarm-group/alarm-group-detail/alarm-group-detail';
import AlarmShieldStrategy from '../../alarm-shield/quick-alarm-shield/quick-alarm-shield-strategy.vue';
import * as strategyAuth from '../authority-map';
import { isRecoveryDisable, isStatusSetterNoData } from '../common';
import TableStore, { invalidTypeMap } from '../store';
import StrategyConfigDialog from '../strategy-config-dialog/strategy-config-dialog';
import FilterPanel from '../strategy-config-list/filter-panel';
import { DetectionRuleTypeEnum, MetricDetail } from '../strategy-config-set-new/typings';
import StrategyIpv6 from '../strategy-ipv6/strategy-ipv6';
import { compareObjectsInArray, countElementsNotInFirstRow, handleMouseDown, handleMouseMove } from '../util';
import DeleteSubtitle from './delete-subtitle';
import FilterPanelPopover from './filter-panel-popover';

import type { EmptyStatusOperationType, EmptyStatusType } from '../../../components/empty-status/types';
import type { INodeType, TargetObjectType } from '../../../components/monitor-ip-selector/typing';
import type { IGroupData } from '../strategy-config-list/group';
import type { IHeader, ILabel, IPopover, IStrategyConfigProps } from './type';

import './strategy-config.scss';
import '@blueking/search-select-v3/vue2/vue2.css';

const { i18n: I18N } = window;
const UN_SET_ACTION = 'UN_SET_ACTION';
const STRATEGY_CONFIG_SETTING = 'strategy_config_setting';
/** 过滤项 */
const FILTER_PANEL_FIELD = 'FILTER_PANEL_FIELD';

@Component({
  name: 'StrategyConfig',
})
class StrategyConfig extends Mixins(UserConfigMixin, authorityMixinCreate(strategyAuth, false)) {
  @Prop({ type: String, default: '' }) fromRouteName: IStrategyConfigProps['fromRouteName'];
  @Prop({ type: String, default: '' }) strategyType: string;
  @Prop({ type: String, default: '' }) noticeName: IStrategyConfigProps['noticeName'];
  @Prop({ type: String, default: '' }) serviceCategory: IStrategyConfigProps['serviceCategory'];
  @Prop({ type: [String, Number], default: '' }) taskId: IStrategyConfigProps['taskId'];
  @Prop({ type: String, default: '' }) ip: IStrategyConfigProps['ip'];
  @Prop({ type: [String, Number], default: '' }) bkCloudId: IStrategyConfigProps['bkCloudId'];
  @Prop({ type: Number, default: 0 }) bkEventGroupId: IStrategyConfigProps['bkEventGroupId'];
  @Prop({ type: Number, default: 0 }) timeSeriesGroupId: IStrategyConfigProps['timeSeriesGroupId'];
  @Prop({ type: String, default: '' }) pluginId: IStrategyConfigProps['pluginId'];
  @Prop({ type: String, default: '' }) metricId: IStrategyConfigProps['metricId'];
  @Prop({ type: Array, default: null }) bkStrategyId: IStrategyConfigProps['bkStrategyId'];
  @Prop({ type: Array, default: null }) dataSource: IStrategyConfigProps['dataSource'];
  @Prop({ type: String, default: '' }) actionName: IStrategyConfigProps['actionName'];
  @Prop({ type: String, default: '' }) strategyLabels: IStrategyConfigProps['strategyLabels'];
  @Prop({ type: [String, Array] }) scenario: string;
  @Prop({ type: [String, Array] }) strategyState: string;
  @Prop({ type: Array }) keywords: IStrategyConfigProps['keywords']; /** 支持传入自定义搜索关键词 */
  @Prop({ type: String, default: '' }) resultTableId: IStrategyConfigProps['resultTableId']; /** 结果表搜索条件 */

  showFilterPanel = true;
  showFilterPanelField = [
    'strategy_status',
    'scenario',
    'data_source_list',
    'user_group_name',
    'label_name',
    'action_name',
  ];
  /** 过滤面板字段展示顺序 */
  filterPanelFieldOrder = [
    'status',
    'scenario',
    'dataSource',
    'noticeName',
    'strategyLabels',
    'actionName',
    'level',
    'algorithmType',
    'invalidType',
  ];
  header: IHeader = {
    value: 0,
    dropdownShow: false,
    list: [
      // { id: 0, name: I18N.t('修改告警组') },
      { id: 1, name: I18N.t('修改触发条件') },
      { id: 5, name: I18N.t('修改恢复条件') },
      // { id: 2, name: I18N.t('修改通知间隔') },
      { id: 3, name: I18N.t('修改无数据告警') },
      // { id: 4, name: I18N.t('修改告警恢复通知') },
      { id: 6, name: I18N.t('启/停策略') },
      { id: 7, name: I18N.t('删除策略') },
      { id: 23, name: I18N.t('分享策略') },
      // { id: 9, name: I18N.t('修改告警模版') },
      { id: 8, name: I18N.t('增删目标') },
      { id: 10, name: I18N.t('修改标签') },
      // { id: 11, name: I18N.t('修改处理套餐') }
      { id: 21, name: I18N.t('修改算法') },
      { id: 12, name: I18N.t('修改生效时间段') },
      { id: 13, name: I18N.t('修改处理套餐') },
      { id: 14, name: I18N.t('修改告警组') },
      { id: 15, name: I18N.t('修改通知场景') },
      { id: 20, name: I18N.t('修改通知升级') },
      { id: 16, name: I18N.t('修改通知间隔') },
      { id: 17, name: I18N.t('修改通知模板') },
      { id: 18, name: I18N.t('修改告警风暴开关') },
      { id: 19, name: I18N.t('As Code') },
      { id: 22, name: I18N.t('导入/导出') },
    ],
    keyword: '',
    keywordObj: [], // 搜索框绑定值
    condition: [], // 搜索条件接口参数
    conditionList: [], // 搜索可选项
    handleSearch: () => {},
  };
  dataSourceList = [
    {
      value: '',
      id: 'bk_monitor',
      checked: 'bk_monitor',
      cancel: '',
      name: I18N.t('监控采集'),
    },
    {
      value: '',
      id: 'log',
      checked: 'bk_monitor',
      cancel: '',
      name: I18N.t('日志采集'),
    },
  ];
  label: ILabel = {
    target: null,
    isSelected: false,
    selectedLabels: '',
    serviceCategory: '',
    noticeName: '',
  };
  popover: IPopover = {
    instance: null,
    hover: -1,
    edit: false,
    status: '',
    data: {
      shieldInfo: {
        is_shielded: true,
      },
      strategyName: '',
    },
  };
  table = {
    data: [],
    loading: false,
    select: [],
  };
  pageCount = 0;
  dialog = {
    show: false,
    selectList: [],
  };
  alarmGroupDialog = {
    id: null,
    show: false,
  };
  tableInstance: TableStore = {
    total: 0,
    data: [],
    keyword: '',
    page: 1,
    pageSize: 10,
    pageList: [10, 20, 50, 100],
    getTableData: () => [],
    setDefaultStore: () => {},
    getItemDescription: () => [],
  };
  loading = false;
  isShowStrategy = false;
  isShowTableFilter = false;
  strategyId = 0;
  backDisplayMap: any = {};
  targetSet = {
    show: false,
    strategyIds: [],
    bizId: '',
    objectType: '',
    title: I18N.t('监控目标'),
    nodeType: '',
  };
  strategyLabelList = []; // 标签筛选俩表
  actionNameList = []; // 自愈套餐列表
  sourceList = []; // 数据来源筛选列表
  typeList = []; // 分类可筛选列表
  filterType = 'checkbox'; // 筛选列表类型
  curFilterType = I18N.t('数据来源'); // 当前筛选类型
  dialogLoading = false;
  groupList = []; // 告警组数据列表
  scenarioList = []; // 监控对象
  fieldSettingData: any = {};
  fieldAllSelected = false; // 是否全选
  dropWidth = 214;
  noticeGroupList = [];
  conditionList = [];
  /** 策略状态数据 */
  strategyStatusOptions = [
    {
      id: 'ALERT',
      name: window.i18n.tc('告警中'),
      count: 0,
    },
    {
      id: 'INVALID',
      name: window.i18n.tc('已失效'),
      count: 0,
    },
    {
      name: window.i18n.tc('已停用'),
      id: 'OFF',
      count: 0,
    },
    {
      name: window.i18n.tc('已启用'),
      id: 'ON',
      count: 0,
    },
    {
      name: window.i18n.tc('屏蔽中'),
      id: 'SHIELDED',
      count: 0,
    },
  ];
  ipCheckValue = {};
  ipSelectorPanels = [];
  ipTargetType = 'TOPO';
  ipSelectorShow = false;
  emptyType: EmptyStatusType = 'empty'; // 空状态
  selectKey = 1;
  firstRequest = true; // 第一次请求
  cancelFn = () => {}; // 取消监控目标接口方法

  get bizList() {
    return this.$store.getters.bizList;
  }
  get idList() {
    return this.table.select.map(item => item.id);
  }
  get isSameObjectType() {
    const list = this.table.select;
    return (
      list.length &&
      list.every((item, index) => {
        if (index === 0) return true;

        const preItem = list[index - 1];
        return item.objectType === preItem.objectType;
      })
    );
  }

  // 筛选面板所有字段
  get filterPanelData(): IGroupData[] {
    const iconMap = {
      ALERT: 'icon-mc-chart-alert',
      INVALID: 'icon-shixiao',
      OFF: 'icon-zanting1',
      ON: 'icon-kaishi1',
      SHIELDED: 'icon-menu-shield',
    };
    const strategyStatusFilter = {
      id: 'strategy_status',
      name: this.$t('状态'),
      data: this.strategyStatusOptions.map(item => ({
        ...item,
        count: item.count || 0,
        icon: iconMap[item.id],
      })),
    };
    return this.filterPanelFieldOrder.map(key => {
      if (key === 'status') return strategyStatusFilter;
      const { id, name, list } = this.backDisplayMap[key];
      return {
        id,
        name,
        data: key === 'noticeName' ? this.groupList.map(({ name, count }) => ({ id: name, name, count })) : list,
      };
    });
  }

  /** 筛选面板展示字段 */
  get showFilterPanelData(): IGroupData[] {
    return this.filterPanelData.filter(item => this.showFilterPanelField.includes(item.id as string));
  }

  get isFta() {
    return this.strategyType === 'fta';
  }

  get uptimeCheckMap() {
    const local = {
      available: DetectionRuleTypeEnum.Threshold,
      task_duration: DetectionRuleTypeEnum.Threshold,
      message: DetectionRuleTypeEnum.PartialNodes,
      response_code: DetectionRuleTypeEnum.PartialNodes,
    };
    const list = this.$store.getters['strategy-config/uptimeCheckMap'];
    return list || local;
  }

  get hasEditDetection() {
    let canSetDetEctionRules = true;
    const res = this.table.select.map(item => {
      // 检测算法是否禁用枚举
      const detectionDisabledStatusMap = {
        [DetectionRuleTypeEnum.IntelligentDetect]: false,
        [DetectionRuleTypeEnum.TimeSeriesForecasting]: false,
        [DetectionRuleTypeEnum.AbnormalCluster]: false,
        [DetectionRuleTypeEnum.Threshold]: false,
        [DetectionRuleTypeEnum.YearRound]: false,
        [DetectionRuleTypeEnum.RingRatio]: false,
        [DetectionRuleTypeEnum.PartialNodes]: true,
      };

      const { queryConfigs } = item;
      const uptimeItem = this.uptimeCheckMap?.[queryConfigs?.[0]?.metric_field];
      const { data_source_label: dataSourceLabel, data_type_label: dataTypeLabel, functions } = queryConfigs?.[0] || {};

      const isCanSetAiops =
        queryConfigs?.length === 1 &&
        ['bk_data', 'bk_monitor'].includes(dataSourceLabel) &&
        dataTypeLabel === 'time_series' &&
        !functions?.length;

      if (canSetDetEctionRules) {
        // 指标拥有设置检测算法的功能
        canSetDetEctionRules =
          `${dataSourceLabel}|${dataTypeLabel}` !== 'bk_monitor|event' && dataTypeLabel !== 'alert';
      }
      for (const key of Object.keys(detectionDisabledStatusMap)) {
        if (!canSetDetEctionRules) detectionDisabledStatusMap[key] = true;

        // ICMP协议的拨测服务开放所有的检测算法选项、HTTP、TCP、UDP协议仅有静态阈值检测算法
        if (uptimeItem) {
          if (!queryConfigs?.[0]?.isICMP) {
            detectionDisabledStatusMap[key] = key !== uptimeItem;
          }
        }

        // 智能检测算法 | 时序预测算法一致 | 离群检测
        if (
          [
            DetectionRuleTypeEnum.IntelligentDetect,
            DetectionRuleTypeEnum.TimeSeriesForecasting,
            DetectionRuleTypeEnum.AbnormalCluster,
          ].includes(key as DetectionRuleTypeEnum)
        ) {
          if (!isCanSetAiops) {
            detectionDisabledStatusMap[key] = true;
          }
          if (!window.enable_aiops) {
            detectionDisabledStatusMap[key] = true;
          }
        }
      }
      return detectionDisabledStatusMap;
    });
    return compareObjectsInArray(Object.values(res)) && canSetDetEctionRules;
  }

  get selectMetric() {
    if (!this.table.select.length) return [];
    return this.table.select[0].queryConfigs.map(item => new MetricDetail({ ...item }));
  }

  deactivated() {
    this.selectKey += 1;
  }

  @Watch('table.data')
  handleTableDataChange(v) {
    // 用于数据样式自适应
    setTimeout(() => {
      v.forEach((item, index) => {
        /* 告警组 */
        const ref = (this.$refs.strategyTable as Element & { $refs: Record<string, HTMLDivElement> })?.$refs[
          `table-row-${index}`
        ];
        // 这里计算整个 告警组 容器内是否会出现 换行 的可能，若换行就显示 +n。
        item.overflow = ref && ref.clientHeight > 32;
        const overflowCount = (item.overflow && countElementsNotInFirstRow(ref)) || 0;
        this.$set(item, 'overflowCount', overflowCount);
        /* 标签组 */
        const refLabel = (this.$refs.strategyTable as Element & { $refs: Record<string, HTMLDivElement> })?.$refs[
          `table-labels-${index}`
        ];
        // 这里计算整个 label 容器内是否会出现 换行 的可能，若换行就显示 +n。
        /* 标签组样式 */
        item.overflowLabel = refLabel && refLabel.clientHeight > 32;
        const overflowLabelCount = (item.overflowLabel && countElementsNotInFirstRow(refLabel)) || 0;
        this.$set(item, 'overflowLabelCount', overflowLabelCount);
        const overflowMap = ['signals', 'levels', 'detectionTypes', 'mealNames'];
        for (const key of overflowMap) {
          // 通用数据样式
          const refDom: any = this.$refs[`table-${key}-${index}`];
          item[`overflow${key}`] = refDom && refDom.clientHeight > 32;
        }
      });
    }, 100);
  }
  created() {
    this.backDisplayMap = {
      bkStrategyId: {
        name: this.$t('策略ID'),
        value: [],
        id: 'strategy_id',
      },
      bkStrategyName: {
        name: this.$t('策略名'),
        value: [],
        id: 'strategy_name',
      },
      // 告警组
      noticeName: {
        name: this.$t('告警组'), // 输入框回显的名称
        value: this.noticeName, // 回显的值
        id: 'user_group_name', // 传给后端的字段名
        multiple: true,
      },
      // 服务分类
      serviceCategory: {
        name: this.$t('服务分类'),
        value: this.serviceCategory,
        id: 'service_category',
      },
      // 拨测任务
      taskId: {
        name: this.$t('拨测任务ID'),
        value: this.taskId,
        id: 'task_id',
      },
      // 主机监控
      ip: {
        name: 'IP',
        value: this.ip,
        id: 'IP',
      },
      // 管控区域ID
      bkCloudId: {
        name: this.$t('管控区域ID'),
        value: this.bkCloudId,
        id: 'bk_cloud_id',
      },
      // 自定义事件
      bkEventGroupId: {
        name: this.$t('自定义事件分组ID'),
        value: this.bkEventGroupId,
        id: 'bk_event_group_id',
      },
      // 自定义指标分组ID
      timeSeriesGroupId: {
        name: this.$t('分组ID'),
        value: this.timeSeriesGroupId,
        id: 'time_series_group_id',
      },
      // 插件ID
      pluginId: {
        name: this.$t('插件ID'),
        value: this.pluginId,
        id: 'plugin_id',
      },
      // 仪表盘
      metricId: {
        name: this.$t('指标ID'),
        value: this.metricId,
        id: 'metric_id',
      },
      metricAlias: {
        name: this.$t('指标别名'),
        value: '',
        id: 'metric_alias',
      },
      metricName: {
        name: this.$t('指标名'),
        value: '',
        id: 'metric_name',
      },
      creators: {
        name: this.$t('创建人'),
        value: '',
        id: 'creators',
      },
      updaters: {
        name: this.$t('最近更新人'),
        value: '',
        id: 'updaters',
      },
      strategyState: {
        name: this.$t('状态'),
        value: '',
        id: 'strategy_status',
        list: this.strategyStatusOptions,
        multiple: true,
      },
      dataSource: {
        name: this.$t('数据来源'),
        value: '',
        id: 'data_source_list',
        list: [],
        multiple: true,
      },
      scenario: {
        name: this.$t('监控对象'),
        value: '',
        id: 'scenario',
        list: [],
        multiple: true,
      },
      strategyLabels: {
        name: this.$t('标签'),
        value: '',
        id: 'label_name',
        list: [],
        multiple: true,
      },
      actionName: {
        name: this.$t('套餐名'),
        value: '',
        id: 'action_name',
        list: [],
        multiple: true,
      },
      resultTableId: {
        name: this.$t('结果表'),
        value: '',
        id: 'result_table_id',
        list: [],
        multiple: true,
      },
      level: {
        name: this.$t('告警级别'),
        value: '',
        id: 'level',
        list: [
          { id: 1, name: this.$t('致命') },
          { id: 2, name: this.$t('预警') },
          { id: 3, name: this.$t('提醒') },
        ],
        multiple: true,
      },
      algorithmType: {
        name: this.$t('算法类型'),
        value: '',
        id: 'algorithm_type',
        list: [
          {
            id: 'Threshold',
            name: window.i18n.tc('静态阈值'),
          },
          {
            id: 'SimpleRingRatio',
            name: window.i18n.tc('简易环比'),
          },
          {
            id: 'AdvancedRingRatio',
            name: window.i18n.tc('高级环比'),
          },
          {
            id: 'SimpleYearRound',
            name: window.i18n.tc('简易同比'),
          },
          {
            id: 'AdvancedYearRound',
            name: window.i18n.tc('高级同比'),
          },
          {
            id: 'PartialNodes',
            name: window.i18n.tc('部分节点数算法'),
          },
          {
            id: 'OsRestart',
            name: window.i18n.tc('主机重启'),
          },
          {
            id: 'ProcPort',
            name: window.i18n.tc('进程端口'),
          },
          {
            id: 'PingUnreachable',
            name: window.i18n.tc('Ping不可达算法'),
          },
          {
            id: 'YearRoundAmplitude',
            name: window.i18n.tc('同比振幅'),
          },
          {
            id: 'YearRoundRange',
            name: window.i18n.tc('同比区间'),
          },
          {
            id: 'RingRatioAmplitude',
            name: window.i18n.tc('环比振幅'),
          },
          {
            id: 'IntelligentDetect',
            name: window.i18n.tc('智能异常检测算法'),
          },
          {
            id: 'TimeSeriesForecasting',
            name: window.i18n.tc('时序预测'),
          },
          {
            id: 'AbnormalCluster',
            name: window.i18n.tc('离群检测'),
          },
        ],
        multiple: true,
      },
      invalidType: {
        name: this.$t('失效类型'),
        value: '',
        id: 'invalid_type',
        list: Object.entries(invalidTypeMap).map(item => ({
          id: item[0],
          name: item[1],
        })),
        multiple: true,
      },
    };
    this.fieldSettingData = {
      id: {
        checked: true,
        disable: true,
        name: 'ID',
        id: 'id',
      },
      strategyName: {
        checked: true,
        disable: true,
        name: this.$t('策略名'),
        id: 'strategyName',
      },
      itemDescription: {
        checked: true,
        disable: false,
        name: this.$t('监控项'),
        id: 'itemDescription',
      },
      dataOrigin: {
        checked: false,
        disable: false,
        name: this.$t('数据来源'),
        id: 'dataOrigin',
      },
      target: {
        checked: !this.isFta,
        disable: this.isFta,
        name: this.$t('监控目标'),
        id: 'target',
      },
      labels: {
        checked: true,
        disable: false,
        name: this.$t('标签'),
        id: 'labels',
      },
      noticeGroupList: {
        checked: true,
        disable: false,
        name: this.$t('告警组'),
        id: 'noticeGroupList',
      },
      updator: {
        checked: false,
        disable: false,
        name: this.$t('更新记录'),
        id: 'updator',
      },
      enabled: {
        checked: true,
        disable: true,
        name: this.$t('启/停'),
        id: 'enabled',
      },
      dataTypeLabelName: {
        checked: false,
        disable: false,
        name: this.$t('策略类型'),
        id: 'dataTypeLabelName',
      },
      intervalNotifyMode: {
        checked: false,
        disable: false,
        name: this.$t('通知间隔类型'),
        id: 'intervalNotifyMode',
      },
      dataMode: {
        checked: false,
        disable: false,
        name: this.$t('查询类型'),
        id: 'dataMode',
      },
      notifyInterval: {
        checked: false,
        disable: false,
        name: this.$t('通知间隔'),
        id: 'notifyInterval',
      },
      trigger: {
        checked: false,
        disable: false,
        name: this.$t('触发条件'),
        id: 'trigger',
      },
      recovery: {
        checked: false,
        disable: false,
        name: this.$t('恢复条件'),
        id: 'recovery',
      },
      needPoll: {
        checked: false,
        disable: false,
        name: this.$t('告警风暴'),
        id: 'needPoll',
      },
      noDataEnabled: {
        checked: false,
        disable: false,
        name: this.$t('无数据'),
        id: 'noDataEnabled',
      },
      signals: {
        checked: false,
        disable: false,
        name: this.$t('通知场景'),
        id: 'signals',
      },
      levels: {
        checked: false,
        disable: false,
        name: this.$t('级别'),
        id: 'levels',
      },
      detectionTypes: {
        checked: false,
        disable: false,
        name: this.$t('检测规则类型'),
        id: 'detectionTypes',
      },
      mealNames: {
        checked: false,
        disable: false,
        name: this.$t('处理套餐'),
        id: 'mealNames',
      },
      configSource: {
        checked: false,
        disable: false,
        name: this.$t('配置来源'),
        id: 'configSource',
      },
      app: {
        checked: false,
        disable: false,
        name: this.$t('配置分组'),
        id: 'app',
      },
      operator: {
        checked: true,
        disable: true,
        name: this.$t('操作'),
        id: 'operator',
      },
    };
    this.header.handleSearch = debounce(300, () => {
      this.handleGetListData(false, 1);
    });
  }

  async activated() {
    await this.getAuthCreated();
    if (!this.hasPageViewAuth) return;
    /** 获取筛选面板用户配置 */
    this.handleGetUserConfig<{ fields: string[]; order: string[] }>(FILTER_PANEL_FIELD, { reject403: true }).then(
      res => {
        if (!res?.order?.length) {
          this.handleSetUserConfig(
            FILTER_PANEL_FIELD,
            JSON.stringify({
              fields: this.showFilterPanelField,
              order: this.filterPanelFieldOrder,
            })
          );
        } else {
          this.showFilterPanelField = res.fields;
          this.filterPanelFieldOrder = res.order;
        }
      }
    );
    if (
      !['strategy-config-edit', 'strategy-config-add', 'strategy-config-detail', 'strategy-config-target'].includes(
        this.fromRouteName
      )
    ) {
      if (this.tableInstance.setDefaultStore) {
        this.tableInstance.setDefaultStore();
        this.handleResetRoute('Get');
      }
      this.header.keyword = '';
    }
    this.checkColInit();
    this.handleSetDashboard();
    this.handleSearchBackDisplay();
    this.handleGetListData(true, this.tableInstance.page);
    this.getGroupList();
  }
  /**
   * 由于父容器 content-right 进行自适应宽度调整的过程中
   * 会让 table 中的标签 label 无法显示省略号（浏览器宽度缩小的情况下）
   * 本方法在 table 的 mounted 或 activated 完毕时监听容器的 resize 事件
   */
  handleTableMountedOrActivated() {
    const resize = debounce(50, () => {
      this.handleTableDataChange(this.table.data);
    });
    const container = document.querySelector('#content-for-watch-resize') as HTMLElement;
    if (!container) return;
    addListener(container, () => {
      resize();
    });
    this.$once('hook:beforeDestory', () => {
      removeListener(container);
    });
    this.$once('hook:deactivated', () => {
      removeListener(container);
    });
  }
  handleSearchChange(v) {
    if (JSON.stringify(v || []) === JSON.stringify(this.header.keywordObj || [])) return;
    this.header.keywordObj = v;
    // this.createdConditionList();
    this.header.handleSearch();
  }
  /**
   * @description: 表格设置
   * @param {*}
   * @return {*}
   */
  checkColInit() {
    const { columns } = this.$route.query;
    const checkedColumns = tryURLDecodeParse(columns as string, []);
    if (checkedColumns.length) {
      for (const key in this.fieldSettingData) {
        if (checkedColumns.includes(key)) {
          this.fieldSettingData[key].checked = true;
        } else {
          this.fieldSettingData[key].checked = false;
        }
      }
    } else {
      let fieldSettingData: any = localStorage.getItem(STRATEGY_CONFIG_SETTING);
      if (fieldSettingData) {
        fieldSettingData = JSON.parse(fieldSettingData);
        for (const item of fieldSettingData) {
          if (this.fieldSettingData[item.id]) {
            this.fieldSettingData[item.id].checked = item.checked;
          }
        }
      }
    }
    this.fieldAllSelected = Object.keys(this.fieldSettingData).every(key => this.fieldSettingData[key].checked);
  }
  /**
   * @description: 选择字段
   * @param item
   * @return {*}
   */
  handleCheckColChange(item) {
    this.fieldSettingData[item.id].checked = !item.checked;
    const result = Object.keys(this.fieldSettingData).map(key => ({
      id: key,
      checked: this.fieldSettingData[key].checked,
    }));
    localStorage.setItem(STRATEGY_CONFIG_SETTING, JSON.stringify(result));
    this.fieldAllSelected = Object.keys(this.fieldSettingData).every(key => this.fieldSettingData[key].checked);
  }
  /**
   * @description: 是否全选
   * @param v
   * @return {*}
   */
  handleFieldAllSelected(v: boolean) {
    this.fieldAllSelected = v;
    for (const key of Object.keys(this.fieldSettingData)) {
      if (v) {
        this.fieldSettingData[key].checked = true;
      }
      if (!this.fieldSettingData[key].disable && !v) {
        this.fieldSettingData[key].checked = false;
      }
    }
    const result = Object.keys(this.fieldSettingData).map(key => ({
      id: key,
      checked: this.fieldSettingData[key].checked,
    }));
    localStorage.setItem(STRATEGY_CONFIG_SETTING, JSON.stringify(result));
  }
  async handleHeaderDragend(newWidth, oldWidth, column) {
    const labelMap = [
      this.$t('告警组'),
      this.$t('标签'),
      this.$t('通知场景'),
      this.$t('级别'),
      this.$t('检测规则类型'),
      this.$t('处理套餐'),
    ];
    if (labelMap.includes(column.label)) {
      await this.$nextTick();
      this.handleTableDataChange(this.table.data);
    }
  }
  /**
   * @description: 回显搜索条件
   * @param {*}
   * @return {*}
   */
  handleSearchBackDisplay() {
    const temp = [];
    const map = this.backDisplayMap;
    for (const key of Object.keys(map)) {
      let value = this[key];
      if (value) {
        try {
          value = JSON.parse(value);
        } catch (error) {
          console.info(error);
        }
        let values = [];
        if (Array.isArray(value)) {
          values = value.map(item => {
            const listItem = map[key]?.list?.find(li => li.id === item);
            return { id: item, name: listItem?.name || item };
          });
        } else {
          const listItem = map[key]?.list?.find(li => li.id === value);
          values = [{ id: value, name: listItem?.name || value }];
        }
        temp.push({
          id: map[key].id,
          name: map[key].name,
          values,
        });
      }
    }
    if (this.keywords?.length) {
      /** 自定义搜索条件 */
      temp.push(...this.keywords.map(id => ({ id, name: id })));
    }
    if (temp.length) {
      this.header.keywordObj = temp;
    }
  }
  /**
   * @description: 处理搜索条件
   * @param {*} data
   * @return {*}
   */
  handleSearchCondition(data = this.header.keywordObj) {
    const res = [];
    for (const item of data) {
      const key = item.values ? item.id : 'query';
      let value = item.values ? item.values.map(val => val.id) : item.id;
      if (key === 'action_name') {
        if (Array.isArray(value)) {
          value = value.map(id => (id === UN_SET_ACTION ? '' : id));
        } else if (value === UN_SET_ACTION) {
          value = [''];
        }
      }
      const temp = {
        key,
        value,
      };
      res.push(temp);
    }
    this.header.condition = res;
  }
  /**
   * @description: 创建搜索可选列表
   * @param {*}
   * @return {*}
   */
  createdConditionList() {
    const res = [];
    const map = this.backDisplayMap;
    for (const key of Object.keys(map)) {
      const { name, id, list, multiple } = map[key];
      if (id === 'scenario') {
        const resChildren = [];
        for (const listItem of list) {
          if (listItem.children) {
            for (const item of listItem.children) {
              resChildren.push(item);
            }
          }
        }
        res.push({
          name,
          id,
          multiple: true,
          children: resChildren ? resChildren : [],
        });
      } else {
        res.push({
          name,
          id,
          multiple: multiple ?? false,
          children: list ? list : [],
        });
      }
    }
    this.selectKey += 1;
    this.conditionList = res;
  }
  /**
   * 初始化查询参数
   * @param {String} metricId（指标ID有可能从sessionStorage中来）
   */
  handleInitQueryParams(metricId) {
    for (const key of Object.keys(this.backDisplayMap)) {
      // 判断props中是否存在该属性 指标id数组支持多指标
      if (metricId && key === 'metricId') {
        let metricIds = metricId;
        try {
          metricIds = JSON.parse(metricId);
        } catch (error) {
          console.info(error);
        }
        let values = [];
        if (Array.isArray(metricIds)) {
          values = metricIds.map(item => ({ id: item, name: item }));
        } else {
          values = [{ id: metricIds, name: metricIds }];
        }
        this.backDisplayMap[key].value = values;
        const index = this.header.keywordObj.findIndex(item => item.id === this.backDisplayMap[key].id);
        if (index > 0) {
          this.header.keywordObj[index].values = values;
        } else {
          this.header.keywordObj.push({
            id: this.backDisplayMap.metricId.id,
            name: this.backDisplayMap.metricId.name,
            values,
          });
        }
      }
    }
  }
  /**
   * @description:设置dashabord
   * @param {*}
   * @return {*}
   */
  handleSetDashboard() {
    const { metricId } = this.$route.query;
    // || sessionStorage.getItem('__dashboard-Metric-Id__');
    // if (metricId) {
    //   metricId = metricId.replace(/"/gim, '');
    //   sessionStorage.removeItem('__dashboard-Metric-Id__');
    // }
    this.handleInitQueryParams(metricId);
  }
  /**
   * @description: 监控目标设置
   * @param {*} tableData
   * @param {*} targetMap
   * @return {*}
   */
  handleTargetString(tableData, targetMap) {
    const textMap = {
      TOPO: '{0}个拓扑节点',
      SERVICE_TEMPLATE: '{0}个服务模板',
      SET_TEMPLATE: '{0}个集群模板',
      DYNAMIC_GROUP: '{0}个动态分组',
    };
    for (const item of tableData) {
      const target = targetMap[item.id];
      item.objectType = item.objectType || target.instance_type;
      item.targetNodeType = item.node_type;
      if (target.instance_type === 'HOST') {
        if (['SERVICE_TEMPLATE', 'SET_TEMPLATE', 'TOPO', 'DYNAMIC_GROUP'].includes(target.node_type)) {
          item.target = `${this.$t(textMap[target.node_type], [target.node_count])} （${this.$t('共{0}台主机', [target.instance_count])}）`;
        } else if (target.node_type === 'INSTANCE') {
          item.target = this.$t('{0}台主机', [target.node_count]);
        }
      } else if (target.instance_type === 'SERVICE') {
        if (['SERVICE_TEMPLATE', 'SET_TEMPLATE', 'TOPO'].includes(target.node_type)) {
          item.target = `${this.$t(textMap[target.node_type], [target.node_count])} （${this.$t('共{0}个实例', [
            target.instance_count,
          ])}）`;
        }
      } else {
        item.target = '';
      }
    }
    return tableData;
  }
  setTableFilterSelect(filterType) {
    this.curFilterType = filterType;
    const displayMap = this.backDisplayMap;
    const mapKeys = Object.keys(displayMap);
    const keyMap = {
      [String(this.$t('数据来源'))]: () => mapKeys.find(key => displayMap[key].name === filterType),
      [String(this.$t('告警组'))]: () => mapKeys.find(key => displayMap[key].name === filterType),
    };
    // const backDisplayMapKey = keyMap[filterType]()
    const searchKey = displayMap[keyMap[filterType]()].id;
    const res = this.header.keywordObj.find(item => item.id === searchKey);
    if (res) {
      this.handleFilterDataSourece(
        res.values.map(item => item.id),
        false
      );
    } else {
      this.handleResetSourceFilter(false);
    }
  }
  /**
   * @description: 获取监控目标数据
   * @param {*} data
   * @return {*}
   */
  getTargetDetail(data) {
    const ids = data.map(item => item.id);
    getTargetDetail({ strategy_ids: ids }, { cancelToken: new CancelToken(c => (this.cancelFn = c)) }).then(
      targetMap => {
        this.table.data = this.handleTargetString(data, targetMap);
      }
    );
  }
  /**
   * @description: 获取list data
   * @param {*} needLoading
   * @param {*} defPage
   * @param {*} defPageSize
   * @return {*}
   */
  handleGetListData(needLoading = false, defPage?, defPageSize?) {
    this.setTableFilterSelect(this.$t('数据来源'));
    this.setTableFilterSelect(this.$t('告警组'));
    this.handleSearchCondition();
    this.loading = needLoading;
    this.table.loading = !needLoading;
    this.table.data = [];
    const page = defPage || this.tableInstance.page || 1;
    const pageSize = defPageSize || this.tableInstance.pageSize || commonPageSizeGet();
    const params = {
      type: this.strategyType,
      page,
      page_size: pageSize,
      // search: this.header.keyword,
      conditions: this.header.condition,
      // data_source_list: this.label.selectedLabels || [],
      order_by: '-update_time',
      with_user_group: true,
      // service_category: this.label.serviceCategory
    };
    this.emptyType = this.header.condition.length > 0 ? 'search-empty' : 'empty';
    this.cancelFn(); // 取消上一次监控目标的请求
    getStrategyListV2(params)
      .then(async data => {
        this.noticeGroupList = data.user_group_list;
        this.tableInstance = new TableStore(data.strategy_config_list, this.bizList);
        this.tableInstance.page = page;
        this.tableInstance.pageSize = pageSize;
        this.tableInstance.keyword = this.header.keyword;
        const tableData = this.tableInstance.getTableData();
        this.table.data = tableData;
        this.getTargetDetail(tableData);
        this.handleTableDataChange(this.table.data);
        this.pageCount = await this.handelScenarioList(data, this.table.data);
        this.strategyStatusOptions = data.strategy_status_list || [];
        this.sourceList = data.data_source_list
          .map(item => {
            const { type, name, count } = item;
            return { id: type, name, count: count ? count : 0 };
          })
          .sort((pre, next) => next.count - pre.count);
        this.backDisplayMap.dataSource.list = this.sourceList;
        this.strategyLabelList = data.strategy_label_list
          .map(item => {
            const { id, count } = item;
            return { id, count, name: item.label_name };
          })
          .sort((pre, next) => next.count - pre.count);
        this.backDisplayMap.strategyLabels.list = this.strategyLabelList;
        this.actionNameList = data.action_config_list
          .map(item => {
            const { name, count, id } = item;
            return { id: id !== 0 ? name : UN_SET_ACTION, count, name };
          })
          .sort((pre, next) => next.count - pre.count);
        this.backDisplayMap.actionName.list = this.actionNameList;
        const noticeGroupList = data.user_group_list;
        this.groupList = noticeGroupList
          .map(item => {
            const { count } = item;
            return {
              count,
              name: item.user_group_name,
              id: item.user_group_id,
            };
          })
          .sort((pre, next) => next.count - pre.count);
        this.backDisplayMap.noticeName.list = this.groupList.map(item => ({
          id: item.name,
          name: item.name,
        }));
        this.backDisplayMap.level.list = data.alert_level_list || [];
        this.backDisplayMap.algorithmType.list = data.algorithm_type_list || [];
        this.backDisplayMap.invalidType.list = data.invalid_type_list || [];
        this.createdConditionList();
        this.handleResetRoute('Set');
        // magic code  refresh bk table
        (this.$refs.strategyTable as Element & { doLayout?: () => void })?.doLayout?.();
        this.firstRequest = false;
      })
      .catch(() => {
        this.emptyType = '500';
      })
      .finally(() => {
        this.loading = false;
        this.table.loading = false;
      });
  }

  handleResetRoute(type: 'Get' | 'Set') {
    if (type === 'Get') {
      const { page, pageSize, filters } = this.$route.query;
      this.tableInstance.page = Number(page) || 1;
      this.tableInstance.pageSize = Number(pageSize) || commonPageSizeGet();
      this.header.condition = tryURLDecodeParse(filters as string, []);
    } else {
      const { route } = this.$router.resolve({
        name: this.$route.name,
        query: {
          page: String(this.tableInstance.page),
          pageSize: String(this.tableInstance.pageSize),
          filters: JSON.stringify(this.header.condition),
        },
      });
      if (this.$route.fullPath !== route.fullPath) {
        this.$router.replace(route);
      }
    }
    if (this.firstRequest) {
      this.header.keywordObj = this.header.condition.map(item => {
        const { id, name, data } = this.filterPanelData.find(panel => item.key === panel.id) || {
          id: item.key,
          name: item.key,
          data: [],
        };
        let values = [];
        /**
         * 因为有些筛选项需要等待列表接口请求完成后才能知道，所以这里需要判断一下
         * 如果该筛选项没有子级，就暂时使用Url传递的值构造一个id为值的对象,等待接口返回后在进行处理
         */
        if (data?.length) {
          values = data.reduce((values, cur) => {
            if (Array.isArray(cur.children)) {
              values.push(...cur.children.filter(child => item.value.includes(child.id)));
            } else {
              item.value.includes(cur.id) && values.push(cur);
            }
            return values;
          }, []);
        } else if (typeof item.value === 'string') {
          return {
            id: item.value,
            name: item.value,
          };
        } else if (Array.isArray(item.value)) {
          values = item.value.map(id => ({
            id,
            name: id,
          }));
        }
        return {
          id: id,
          name,
          values,
        };
      });
    }
  }
  /**
   * @description: 监控对象处理
   * @param {*} data
   * @param {*} tableData
   * @return {*}
   */
  async handelScenarioList(data, tableData) {
    if (this.scenarioList.length === 0) {
      this.scenarioList = await getScenarioList().catch(() => []);
    }
    let total = 0;
    const scenarioFather = this.scenarioList.map(item => {
      const { name, id, index, children } = item;
      return { name, id, sort: `${index}`, children, count: 0 };
    });
    const scenarioList = data.scenario_list;
    for (const item of scenarioFather) {
      let count = 0;
      for (const set of item.children) {
        const res = scenarioList.find(child => child.id === set.id);
        count += res.count;
        // total += res.count;
        set.count = res.count;
      }
      item.count = count;
    }
    this.backDisplayMap.scenario.list = scenarioFather;
    this.handleUpdateScenarioListName();
    for (const item of tableData) {
      const nameArr = this.getScenarioName(scenarioFather, item.strategyType);
      item.scenarioDisplayName = nameArr.join('-');
    }
    // 列表total设置为监控对象筛选项count总和
    total = data.total;
    return total;
  }
  /** 更新监控对象搜索框回显 */
  handleUpdateScenarioListName() {
    const list = this.backDisplayMap.scenario.list.reduce((total, cur) => {
      cur.children.length && total.push(...cur.children);
      return total;
    }, []);
    const scenarioKeyword = this.header.keywordObj.find(item => item.id === 'scenario');
    scenarioKeyword &&
      (scenarioKeyword.values = scenarioKeyword.values.map(item => {
        const nameObj = list.find(li => li.id === item.id);
        const name = nameObj?.name || item.id;
        return {
          ...item,
          name,
        };
      }));
  }
  getScenarioName(treeData, id) {
    const name = [];
    let level = 0;
    let isFind = false;
    const fn = (data, isFirst = false) => {
      if (isFind) return;

      for (const item of data) {
        if (isFind) break;
        if (isFirst) level = 0;
        name[level] = item.name;
        if (item.id === id) {
          isFind = true;
          break;
        }
        if (item?.children?.length) {
          level += 1;
          if (!isFind) {
            level = 1;
            fn(item.children);
          }
        }
      }
    };
    fn(treeData, true);
    return name;
  }
  handlePageChange(page) {
    this.handleGetListData(false, page);
  }
  handleLimitChange(limit) {
    commonPageSizeSet(limit);
    this.handleGetListData(false, 1, limit);
  }
  handleHeadSelectChange(v) {
    // 导出 Yaml 文件
    if (v === 19) {
      const h = this.$createElement;
      const bkInfoInstance = this.$bkInfo({
        title: this.$t('请确认是否导出'),
        subHeader: h(
          'i18n',
          {
            attrs: {
              path: '导出Yaml功能用于 As Code，如需进行策略导入导出，请前往{0}进行操作',
            },
            class: 'i18n-as-code',
          },
          [
            h(
              'bk-button',
              {
                class: 'i18n-link',
                props: {
                  text: true,
                  theme: 'primary',
                },
                on: {
                  click: () => {
                    bkInfoInstance.close();
                    this.$router.push({
                      name: 'export-import',
                    });
                  },
                },
              },
              [this.$t('route-集成').toString(), ' - ', this.$t('route-导入导出').toString()]
            ),
          ]
        ),
        confirmLoading: true,
        confirmFn: async () => {
          await exportConfigFile({
            rule_ids: (this.table.select || []).map(item => item.id),
            with_related_config: true,
          })
            .then(data => {
              if (!data?.download_url?.length) return;
              downFile(data.download_url, this.$tc('策略导出'));
            })
            .catch(() => {
              this.$bkMessage({
                message: this.$t('导出出错了'),
                theme: 'error',
              });
            });
        },
      });
      return;
    }
    if (v === 22) {
      this.$router.push({
        name: 'export-import',
      });
      return;
    }
    if (v === 23) {
      let hasErr = false;
      const filters = [
        {
          key: 'strategy_id',
          value: [this.table.select.map(item => item.id).join(' | ')],
        },
      ];
      const columns = Object.keys(this.fieldSettingData).reduce((pre, cur) => {
        if (this.fieldSettingData[cur].checked) pre.push(cur);
        return pre;
      }, []);
      const url = location.href.replace(
        location.hash,
        `#/strategy-config?filters=${encodeURIComponent(JSON.stringify(filters))}&columns=${encodeURIComponent(JSON.stringify(columns))}`
      );
      copyText(url, errMsg => {
        this.$bkMessage({
          message: errMsg,
          theme: 'error',
        });
        hasErr = !!errMsg;
      });
      if (!hasErr)
        this.$bkMessage({
          theme: 'success',
          message: this.$t('链接已复制成功，可粘贴分享'),
        });

      return;
    }
    // 批量增删目标
    if (v === 8) {
      // 增删目标禁用状态
      if (!this.isSameObjectType) return;

      this.targetSet.show = true;
      this.targetSet.objectType = this.table.select[0].objectType;
      this.targetSet.nodeType = this.table.select[0].objectType;
      this.targetSet.title = this.$t('增删目标');
      this.targetSet.strategyIds = this.table.select.map(item => item.id);
    } else {
      this.header.value = v;
      this.dialog.show = true;
    }
  }
  /**
   * @description: 精简数据给到后端
   * @param {*} type
   * @param {*} data
   * @return {*}
   */
  handleSelectorData(type, data) {
    const mapper =
      type === 'INSTANCE'
        ? item => ({
            ip: item.ip,
            bk_cloud_id: item.bk_cloud_id,
            bk_supplier_id: item.bk_supplier_id,
          })
        : item => ({
            bk_inst_id: item.bk_inst_id,
            bk_obj_id: item.bk_obj_id,
          });

    return data.map(mapper);
  }
  handleOperatorOver(data, e, index) {
    if (this.popover.index === index) {
      return;
    }
    this.popover.hover = index;
    this.popover.edit = data.needUpdate;
    this.popover.status = data.status;
    this.popover.data = data;
    if (!this.popover.instance) {
      this.popover.instance = this.$bkPopover(e.target, {
        content: this.$refs.operatorGroup,
        arrow: false,
        trigger: 'manual',
        placement: 'bottom',
        theme: 'light common-monitor',
        maxWidth: 520,
        duration: [275, 0],
        onHidden: () => {
          this.popover.instance.destroy();
          this.popover.hover = -1;
          this.popover.instance = null;
        },
      });
    } else {
      this.popover.instance.reference = e.target;
    }
    this.popover.instance?.show(100);
  }
  handleDialogChange(v) {
    this.dialog.show = v;
  }
  handleMuchEdit(v) {
    this.loading = true;
    const { idList } = this;
    if (this.header.value === 7) {
      deleteStrategyV2({ ids: idList })
        .then(() => {
          this.$bkMessage({ theme: 'success', message: this.$t('批量删除成功') });
          this.handleGetListData(false, 1);
        })
        .catch(() => {
          this.loading = false;
        });
    } else {
      updatePartialStrategyV2({ ids: idList, edit_data: { ...v } })
        .then(() => {
          const msg = {
            0: this.$t('批量修改告警组成功'),
            1: this.$t('批量修改触发条件成功'),
            2: this.$t('批量修改通知间隔成功'),
            3: this.$t('批量修改无数据告警成功'),
            4: this.$t('批量修改告警恢复通知成功'),
            5: this.$t('批量修改恢复条件成功'),
            6: '',
            9: this.$t('批量修改告警模板成功'),
            10: this.$t('批量修改标签成功'),
            11: this.$t('批量修改处理套餐成功'),
            12: this.$t('批量修改生效时间段成功'),
            13: this.$t('批量修改处理套餐成功'),
            14: this.$t('批量修改告警组成功'),
            15: this.$t('批量修改通知场景成功'),
            16: this.$t('批量修改通知间隔成功'),
            17: this.$t('批量修改通知模板成功'),
            18: this.$t('批量修改告警风暴开关成功'),
            20: this.$t('批量修改通知升级成功'),
            21: this.$t('批量修改算法成功'),
          };
          this.handleGetListData();
          if (this.header.value === 6) {
            msg[6] = v.is_enabled ? `${this.$t('批量启用策略成功')}` : `${this.$t('批量停用策略成功')}`;
          }
          this.$bkMessage({ theme: 'success', message: msg[this.header.value], ellipsisLine: 0 });
        })
        .catch(() => {
          this.loading = false;
        });
    }
  }
  handlePreSwitchChange(v, type: 'enabled' | 'needPoll' | 'noDataEnabled') {
    const enable = v[type];
    const params = {
      enabled: { is_enabled: !enable },
      needPoll: { notice: { options: { converge_config: { need_biz_converge: !enable } } } },
      noDataEnabled: { no_data_config: { is_enabled: !enable } },
    };
    return new Promise((resolve, reject) => {
      if (!this.authority.MANAGE_AUTH) {
        this.handleShowAuthorityDetail();
        reject();
      }
      if (enable) {
        this.$bkInfo({
          title: this.$t('你确认要停用？'),
          confirmFn: () => {
            this.loading = true;
            this.$nextTick(() => {
              updatePartialStrategyV2({ ids: [v.id], edit_data: params[type] })
                .then(() => {
                  this.handleGetListData(true);
                  this.$bkMessage({ theme: 'success', message: this.$t('停用成功') });
                  resolve(true);
                })
                .catch(() => {
                  this.loading = false;
                  reject();
                });
            });
          },
          cancelFn: () => {
            reject();
          },
        });
      } else {
        this.loading = true;
        updatePartialStrategyV2({ ids: [v.id], edit_data: params[type] })
          .then(() => {
            this.handleGetListData(true);
            this.$bkMessage({ theme: 'success', message: this.$t('启用成功') });
            resolve(true);
          })
          .catch(() => {
            this.loading = false;
            reject();
          });
      }
    });
  }
  handleDeleteRow() {
    this.$bkInfo({
      type: 'warning',
      title: this.$t('你确认么？'),
      subHeader: this.$createElement(DeleteSubtitle, {
        props: {
          title: this.$tc('策略名'),
          name: this.popover.data.strategyName,
        },
      }),
      maskClose: true,
      escClose: true,
      confirmFn: () => {
        this.loading = true;
        deleteStrategyV2({ ids: [this.popover.data.id] })
          .then(() => {
            this.table.loading = false;
            this.$bkMessage({ theme: 'success', message: this.$t('删除成功') });
            this.handleGetListData(false, 1);
          })
          .catch(() => {
            this.loading = false;
          });
      },
    });
  }
  // 拷贝策略
  handleCopy() {
    const item = this.popover.data;
    this.$router.push({
      name: 'strategy-config-clone',
      params: {
        id: item.id,
      },
    });
  }
  handleAddStategyConfig() {
    this.$router.push({
      name: 'strategy-config-add',
      params: {
        objectId: '',
      },
    });
  }
  // 点击增删目标触发
  handleAddTarget(row) {
    if (row.addAllowed) {
      this.targetSet.show = true;
      this.targetSet.strategyIds = [row.id];
      this.targetSet.objectType = row.objectType;
      this.targetSet.nodeType = row.nodeType;
      this.targetSet.title = this.$t('监控目标');
    }
  }
  // 增删目标显示变化触发
  handleTargetShowChange(v) {
    this.targetSet.show = v;
  }
  handleTargetSaveChange() {
    this.handleGetListData(true);
  }
  handleOpenStategydetail(item) {
    this.$router.push({
      name: 'strategy-config-detail',
      params: {
        title: item.strategyName,
        id: item.id,
      },
    });
  }
  handleSelectionChange(selection) {
    this.table.select = selection;
  }
  /**
   * @description: 跳转编辑
   * @param {*} data
   * @return {*}
   */
  handleEditStrategy(data) {
    this.$router.push({
      name: 'strategy-config-edit',
      params: {
        id: data.id,
      },
    });
  }
  handleShowStrategy() {
    this.isShowStrategy = true;
    this.strategyId = this.popover.data.id;
  }
  /**
   * @description: 屏蔽
   * @param {*}
   * @return {*}
   */
  handleDeleteShield() {
    const { id } = this.popover.data.shieldInfo;
    this.$bkInfo({
      title: this.$t('是否解除该屏蔽?'),
      confirmFn: () => {
        this.loading = true;
        disableShield({ id })
          .then(() => {
            this.handleGetListData();
            this.$bkMessage({ theme: 'success', message: this.$t('解除屏蔽成功') });
          })
          .catch(() => {
            this.loading = false;
          });
      },
    });
  }
  /* 查看相关告警 */
  handleViewRelatedAlerts() {
    const { href } = this.$router.resolve({
      name: 'event-center',
      query: {
        queryString: isEn
          ? `告警名称 : "${this.popover.data.strategyName}"`
          : `alert_name : "${this.popover.data.strategyName}"`,
        from: 'now-7d',
        to: 'now',
      },
    });
    window.open(href, '_blank');
  }
  handleSelectedDataSource(v) {
    this.label.isSelected = Boolean(v.length);
  }
  setHeaderKeyword(value) {
    const displayMap = this.backDisplayMap;
    const mapKeys = Object.keys(displayMap);
    const keyMap = {
      [String(this.$t('数据来源'))]: () => mapKeys.find(key => displayMap[key].name === this.curFilterType),
      [String(this.$t('告警组'))]: () => mapKeys.find(key => displayMap[key].name === this.curFilterType),
    };
    const backDisplayMapKey = keyMap[String(this.curFilterType)]();
    const searchKey = displayMap[keyMap[String(this.curFilterType)]()].id;
    const hasKey = this.header.keywordObj.find(item => item.id === searchKey);
    const { list } = displayMap[backDisplayMapKey];
    const name = this.curFilterType;
    if (value) {
      const values = value.map(item => ({
        id: item,
        name: list ? list.find(set => set.id === item).name : item,
      }));
      const obj = {
        id: searchKey,
        multiple: true,
        name,
        values,
      };
      if (hasKey) {
        const index = this.header.keywordObj.findIndex(item => item.id === searchKey);
        this.header.keywordObj.splice(index, 1, obj);
      } else {
        this.header.keywordObj.push(obj);
      }
    } else {
      const index = this.header.keywordObj.findIndex(item => item.id === searchKey);
      this.header.keywordObj.splice(index, 1);
    }
  }
  handleFilterDataSourece(labels, needSetSearch = true) {
    // 更新搜索条件
    const listMap = {
      [String(this.$t('数据来源'))]: () => {
        this.label.selectedLabels = labels;
        return labels;
      },
      // [this.$t('分类')]: () => (this.label.serviceCategory = labels),
      [String(this.$t('告警组'))]: () => {
        this.label.noticeName = labels;
        return labels;
      },
    };
    const value = listMap[String(this.curFilterType)]();

    // 同步搜索框
    if (needSetSearch) {
      this.setHeaderKeyword(value);
      this.handleGetListData();
    }
  }
  handleResetSourceFilter(needSetSearch = true) {
    const listMap = {
      [String(this.$t('数据来源'))]: () => (this.label.selectedLabels = []),
      // [this.$t('分类')]: () => (this.label.serviceCategory = ''),
      [String(this.$t('告警组'))]: () => (this.label.noticeName = ''),
    };
    listMap[String(this.curFilterType)]();
    if (needSetSearch) {
      this.setHeaderKeyword(null);
      this.handleGetListData();
    }
  }
  /**
   * @description 显示数据来源的过滤面板
   */
  handleShowTableFilter(e, type, title) {
    this.filterType = type;
    const listMap = {
      [String(this.$t('数据来源'))]: {
        list: this.sourceList,
        value: this.label.selectedLabels,
      },
      // [this.$t('分类')]: this.typeList,
      [String(this.$t('告警组'))]: {
        list: this.groupList.map(item => ({
          id: item.name,
          name: item.name,
        })),
        value: this.label.noticeName,
      },
    };
    this.curFilterType = title;
    this.dataSourceList = listMap[title].list;
    this.label.target = e.target;
    this.isShowTableFilter = !this.isShowTableFilter;
    this.label.value = listMap[title].value;
  }
  handleChangeValue() {
    this.isShowTableFilter = false;
  }
  renderHeaderTemplate(title, type, active) {
    if (!this.typeList.length && title === this.$t('分类')) {
      return title;
    }
    const titleStr = this.$t(title);
    return (
      <span
        class={{ 'dropdown-trigger': true, 'plugin-label': true, selected: active }}
        slot='dropdown-trigger'
        onClick={e => this.handleShowTableFilter(e, type, title)}
      >
        {titleStr}
        <i class='icon-monitor icon-filter-fill' />
      </span>
    );
  }
  /**
   * @description: 获取告警组列表
   * @param {*}
   * @return {*}
   */
  async getGroupList() {
    // 有数据缓存则不请求数据
    if (this.groupList.length) return;
    this.dialogLoading = true;
    await noticeGroupList().then(data => {
      this.groupList = data
        .map(item => ({
          id: item.id,
          name: item.name,
          count: item.related_strategy,
        }))
        .sort((pre, next) => next.count - pre.count);
    });
    this.dialogLoading = false;
  }
  /* 跳转到事件中心 */
  handleToEventCenter(item, type = 'NOT_SHIELDED_ABNORMAL') {
    const { href } = this.$router.resolve({
      name: 'event-center',
      query: {
        queryString: isEn ? `strategy_id : ${item.id}` : `策略ID : ${item.id}`,
        activeFilterId: type,
        from: 'now-30d',
        to: 'now',
      },
    });
    window.open(href, '_blank');
  }
  /**
   * @description: 筛选面板勾选change事件
   * @param {*} data
   * @return {*}
   */
  handleSearchSelectChange(data = []) {
    for (const item of data) {
      const obj = this.header.keywordObj.find(obj => obj.id === item.id);
      const index = this.header.keywordObj.findIndex(obj => obj.id === item.id);
      if (obj) {
        const values = item.values || [];
        values.length === 0 ? this.header.keywordObj.splice(index, 1) : (obj.values = values);
        // values.forEach((value) => {
        //   const index = (obj.values || []).findIndex(objValue => objValue.id === value.id)
        //   index === -1 && obj.values && obj.values.push(value)
        // })
      } else {
        this.header.keywordObj.push(item);
      }
    }
    this.header.keywordObj = [...this.header.keywordObj];
    this.handleGetListData(false, 1);
  }
  handleShowFilterPanel() {
    this.dropWidth = 214;
    this.showFilterPanel = true;
  }
  handleMouseDown(e) {
    handleMouseDown(e, 'resizeTarget', 114, { min: 214, max: 500 }, width => {
      this.showFilterPanel = width !== 0;
      this.dropWidth = width;
    });
  }
  handleMouseMove(e) {
    handleMouseMove(e);
  }
  // 处理监控项tooltips
  handleDescTips(data) {
    const tips = data.map(item => `<div>${item.tip}</div>`).join('');
    const res = `<div class="item-description">${tips}</div>`;
    return res;
  }
  // 批量操作下的选项是否不可点击
  isBatchItemDisabled(option: any) {
    return (
      (option.id === 8 && (this.isFta || !this.isSameObjectType)) ||
      (option.id === 9 && this.isFta) ||
      (option.id === 21 && !this.hasEditDetection)
    );
  }
  batchItemDisabledTip(option: any) {
    const tipMap = {
      9: this.$t('无需修改告警模板'),
      8: this.isFta ? this.$t('无需设置监控目标') : this.$t('监控对象不一致'),
      21: this.$t('各数据源的可用算法不兼容'),
    };
    return tipMap[option.id];
  }
  /* 跳转到屏蔽页 */
  handleToAlarmShield(ids: number[]) {
    const queryString = encodeURIComponent(JSON.stringify([{ key: 'id', value: ids }]));
    const { href } = this.$router.resolve({
      name: 'alarm-shield',
      query: {
        queryString,
      },
    });
    window.open(href, '_blank');
  }
  handleIpChange(v) {
    this.ipCheckValue = v;
  }
  handleIpTargetTypeChange(v) {
    this.ipTargetType = v;
  }
  /** 空状态处理 */
  handleOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.header.keywordObj = [];
      this.handleGetListData();
      return;
    }

    if (type === 'refresh') {
      this.emptyType = 'empty';
      this.handleGetListData();
      return;
    }
  }

  handleAlarmGroupClick(groupId: number) {
    this.alarmGroupDialog.id = groupId;
    this.alarmGroupDialog.show = true;
  }

  /** 筛选面板设置 */
  handleFilterFieldsChange({ showFields = [], order = [] }) {
    this.showFilterPanelField = showFields;
    const fieldsOrder = order.reduce((acc, cur) => {
      acc.push(this.filterPanelFieldOrder[cur]);
      return acc;
    }, []);
    this.filterPanelFieldOrder = fieldsOrder;
    this.handleSetUserConfig(
      FILTER_PANEL_FIELD,
      JSON.stringify({
        fields: this.showFilterPanelField,
        order: this.filterPanelFieldOrder,
      })
    );
  }

  getTableComponent() {
    const idSlot = {
      default: props => props.row.id,
    };
    const strategyNameSlot = {
      /* 策略名称 */
      default: props => (
        <div class='col-name'>
          <div class='col-name-desc'>
            <span
              class='col-name-desc-text'
              v-bk-tooltips={{
                content: props.row.strategyName,
                boundary: 'window',
                delay: 200,
                allowHTML: false,
              }}
            >
              <router-link
                class='name-text-link'
                to={{
                  name: 'strategy-config-detail',
                  params: {
                    title: props.row.strategyName,
                    id: props.row.id,
                  },
                }}
              >
                {props.row.strategyName}
              </router-link>
            </span>
            {[
              props.row.isInvalid ? (
                <i
                  key={1}
                  class='icon-monitor icon-shixiao'
                  v-bk-tooltips={{
                    placements: ['right'],
                    boundary: 'window',
                    content: `${props.row.invalidType}`,
                    allowHTML: false,
                  }}
                />
              ) : undefined,
              props.row.abnormalAlertCount > 0 && !props.row.isInvalid ? (
                <span
                  key={2}
                  class='alert-tag red'
                  v-bk-tooltips={{
                    placements: ['right'],
                    boundary: 'window',
                    content: `${this.$t('当前有{n}个未恢复事件', { n: props.row.abnormalAlertCount })}`,
                    allowHTML: false,
                  }}
                  onClick={modifiers.stop(() => this.handleToEventCenter(props.row))}
                >
                  <i class='icon-monitor icon-mc-chart-alert' />
                  <span class='alert-count'>{props.row.abnormalAlertCount}</span>
                </span>
              ) : undefined,
              props.row.shieldAlertCount ? (
                <span
                  key={3}
                  class='alert-tag grey'
                  v-bk-tooltips={{
                    placements: ['right'],
                    boundary: 'window',
                    content: `${this.$t('当前有{n}个已屏蔽事件', { n: props.row.shieldAlertCount })}`,
                    allowHTML: false,
                  }}
                  onClick={modifiers.stop(() => this.handleToEventCenter(props.row, 'SHIELDED_ABNORMAL'))}
                >
                  <i class='icon-monitor icon-menu-shield' />
                  <span class='alert-count'>{props.row.shieldAlertCount}</span>
                </span>
              ) : undefined,
              props.row.shieldInfo?.shield_ids?.length ? (
                <span
                  key={4}
                  class='alert-tag wuxian'
                  v-bk-tooltips={{
                    placements: ['right'],
                    boundary: 'window',
                    content: `${this.$t('整个策略已被屏蔽')}`,
                  }}
                  onClick={() => this.handleToAlarmShield(props.row.shieldInfo.shield_ids)}
                >
                  <i class='icon-monitor icon-menu-shield' />
                  <SvgIcon
                    class='wu-xian-text'
                    iconName={'wuqiong'}
                  />
                </span>
              ) : undefined,
            ]}
          </div>
          <div class='col-name-type'>{props.row.scenarioDisplayName}</div>
        </div>
      ),
    };
    const itemDescriptionSlot = {
      default: props => (
        <span
          class='table-monitor-desc'
          v-bk-tooltips={{
            content: this.handleDescTips(props.row.itemDescription),
            delay: 200,
            boundary: 'window',
            allowHTML: true,
          }}
        >
          {props.row.itemDescription.map((item, index) => [
            <span
              key={index}
              class='table-monitor-desc-item'
            >
              {index < 2 ? (
                <span
                  style='white-space: nowrap;'
                  class='item-span'
                >
                  {item.val}
                  {props.row.itemDescription.length > 2 && index > 0 ? <span>&nbsp;...</span> : undefined}
                </span>
              ) : undefined}
            </span>,
            index === 0 ? <br key={`br-${index}`} /> : undefined,
          ])}
        </span>
      ),
    };
    const dataOriginSlot = {
      /* 数据来源 */ default: props => <span>{props.row.dataOrigin}</span>,
    };
    const targetSlot = {
      default: props => (
        <div class='col-name'>
          <div class='col-name-label'>{props.row.target || this.$t('默认全部')}</div>
        </div>
      ),
    };
    const overflowGroupDom = (props, type, customTip = '' /* 通用组样式 */) => (
      <div class='col-classifiy'>
        {props.row[type].length > 0 ? (
          <div
            ref={`table-${type}-${props.$index}`}
            class='col-classifiy-wrap'
            v-bk-tooltips={{
              placements: ['top-start'],
              boundary: 'window',
              content: () => customTip || props.row[type].join('、 '),
              delay: 200,
              allowHTML: false,
            }}
          >
            {props.row[type].map((item, index) => (
              <span
                key={`${item}-${index}`}
                class='classifiy-label gray'
              >
                <span class='text-overflow'>{item}</span>
              </span>
            ))}
            {props.row[`overflow${type}`] ? <span class='classifiy-overflow gray'>...</span> : undefined}
          </div>
        ) : (
          <div>--</div>
        )}
      </div>
    );
    const labelsSlot = {
      /* 标签 */
      default: props => (
        <div class='col-classifiy'>
          {props.row.labels.length > 0 ? (
            <div
              ref={`table-labels-${props.$index}`}
              class='col-classifiy-wrap'
            >
              {props.row.labels.map((item, index) => (
                <span
                  key={`${item}-${index}`}
                  class='classifiy-label gray'
                  v-bk-overflow-tips
                >
                  <span class='text-overflow'>{item}</span>
                </span>
              ))}
              {props.row.overflowLabel ? (
                <span
                  class='classifiy-overflow gray'
                  v-bk-tooltips={{
                    placements: ['top-start'],
                    boundary: 'window',
                    content: () => props.row.labels.join('、 '),
                    delay: 200,
                    allowHTML: false,
                    extCls: 'ext-cls',
                  }}
                >
                  +{props.row.overflowLabelCount}
                </span>
              ) : undefined}
            </div>
          ) : (
            <div>--</div>
          )}
        </div>
      ),
    };
    const noticeGroupListSlot = {
      /* 告警组 */
      default: props => (
        <div class='col-classifiy'>
          <div
            ref={`table-row-${props.$index}`}
            class='col-classifiy-wrap'
          >
            {props.row.noticeGroupNameList.map(item => (
              <span
                key={item.id}
                class='classifiy-label'
                onClick={() => this.handleAlarmGroupClick(item.id)}
              >
                <span
                  class='text-overflow'
                  v-bk-overflow-tips
                >
                  {item.name}
                </span>
              </span>
            ))}
            {props.row.overflow ? (
              <span
                class='classifiy-overflow'
                v-bk-tooltips={{
                  placements: ['top-start'],
                  boundary: 'window',
                  content: () => props.row.noticeGroupNameList.map(item => item.name).join('、'),
                  delay: 200,
                  allowHTML: false,
                  disabled: !props.row.overflow,
                  extCls: 'ext-cls',
                }}
              >
                +{props.row.overflowCount}
              </span>
            ) : undefined}
          </div>
        </div>
      ),
    };
    const signalsSlot = {
      /* 通知场景 */ default: props => overflowGroupDom(props, 'signals'),
    };
    const levelsSlot = {
      /* 级别 */ default: props => overflowGroupDom(props, 'levels'),
    };
    const detectionTypesSlot = {
      /* 检测规则类型 */ default: props => overflowGroupDom(props, 'detectionTypes'),
    };
    const mealNamesSlot = {
      /* 处理套餐 */
      default: props => {
        const tip = props.row.mealTips.length
          ? `<span>
          ${props.row.mealTips.map(item => `<div>${item}</div>`).join('')}
        </span>`
          : '';
        return overflowGroupDom(props, 'mealNames', tip);
      },
    };
    const updatorSlot = {
      /* 更新记录 */
      default: props => (
        <div class='col-name'>
          <div class='col-name-label'>
            {props.row.updator ? <bk-user-display-name user-id={props.row.updator} /> : '--'}
          </div>
          <div>{dayjs.tz(props.row.updateTime).format('YYYY-MM-DD HH:mm:ss') || '--'}</div>
        </div>
      ),
    };
    const enabledDom = (props, type: 'enabled' | 'needPoll' | 'noDataEnabled' /* 通用开关样式 */) => (
      <div class='switch-wrap'>
        <bk-switcher
          key={props.row.id}
          v-model={props.row[type]}
          pre-check={() => this.handlePreSwitchChange(props.row, type)}
          size='small'
          theme='primary'
        />
        {!this.authority.MANAGE_AUTH ? (
          <div
            class='switch-wrap-modal'
            v-authority={{ active: !this.authority.MANAGE_AUTH }}
            onClick={(e: Event) => {
              e.stopPropagation();
              e.preventDefault();
              !this.authority.MANAGE_AUTH && this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH);
            }}
          />
        ) : undefined}
      </div>
    );
    const enabledSlot = {
      /* 启停 */ default: props => enabledDom(props, 'enabled'),
    };
    const needPollSlot = {
      /* 告警风暴 */ default: props => enabledDom(props, 'needPoll'),
    };
    const noDataEnabledSlot = {
      /* 无数据启停 */ default: props => enabledDom(props, 'noDataEnabled'),
    };
    const recoverySlot = {
      /* 恢复条件 */
      default: props => (
        <span
          v-bk-tooltips={{
            placements: ['top-start'],
            boundary: 'boundary',
            content: () =>
              this.$t('连续{0}个周期内不满足触发条件{1}', [
                props.row.recovery,
                !isRecoveryDisable(props.row.queryConfigs) && isStatusSetterNoData(props.row.recoveryStatusSetter)
                  ? this.$t('或无数据')
                  : '',
              ]),
            disabled: props.row.recovery === '--' /* 兼容关联告警 */,
            delay: 200,
            allowHTML: false,
          }}
        >
          {props.row.recovery}
        </span>
      ),
    };
    const triggerSlot = {
      /* 触发条件 */
      default: props => (
        <span
          v-bk-tooltips={{
            placements: ['top-start'],
            boundary: 'boundary',
            content: () =>
              props.row.triggerConfig
                ? this.$t(/* 兼容关联告警 */ '在{0}个周期内{1}满足{2}次检测算法，触发告警通知', [
                    props.row.triggerConfig.check_window,
                    this.$t('累计'),
                    props.row.triggerConfig.count,
                  ])
                : '',
            disabled: !props.row.triggerConfig,
            delay: 200,
            allowHTML: false,
          }}
        >
          {props.row.trigger}
        </span>
      ),
    };
    const configSourceSlot = {
      /* 配置来源 */ default: props => props.row.configSource || '--',
    };
    const appSlot = {
      /* 配置分组 */ default: props => props.row.app || '--',
    };
    const operatorSlot = {
      /* 操作 */
      default: props => (
        <div class='col-operator'>
          <span
            class={['col-operator-btn', { 'col-operator-disabled': !props.row.editAllowed }]}
            v-authority={{ active: !this.authority.MANAGE_AUTH }}
            v-bk-tooltips={{
              placements: ['top'],
              content: this.$t('内置策略不允许修改'),
              disabled: props.row.editAllowed,
            }}
            onClick={() =>
              this.authority.MANAGE_AUTH
                ? props.row.editAllowed && this.handleEditStrategy(props.row)
                : this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH)
            }
          >
            {this.$t('button-编辑')}
          </span>
          <span
            class={['col-operator-btn', 'col-operator-adddel', { 'col-operator-disabled': !props.row.addAllowed }]}
            v-authority={{ active: !this.authority.MANAGE_AUTH }}
            onClick={() =>
              this.authority.MANAGE_AUTH
                ? this.handleAddTarget(props.row)
                : this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH)
            }
          >
            {this.$t('增删目标')}
          </span>
          <span
            class='col-operator-more'
            v-authority={{ active: !this.authority.MANAGE_AUTH }}
            data-popover='true'
            onClick={event =>
              this.authority.MANAGE_AUTH
                ? this.handleOperatorOver(props.row, event, props.$index)
                : this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH)
            }
          >
            <i
              class='bk-icon icon-more'
              data-popover='true'
            />
          </span>
        </div>
      ),
    };
    const {
      id,
      strategyName,
      itemDescription,
      dataOrigin,
      target,
      labels,
      noticeGroupList,
      updator,
      enabled,
      dataTypeLabelName,
      intervalNotifyMode,
      dataMode,
      notifyInterval,
      trigger,
      recovery,
      needPoll,
      noDataEnabled,
      signals,
      levels,
      detectionTypes,
      mealNames,
      operator,
      configSource,
      app,
    } = this.fieldSettingData;
    return (
      <bk-table
        ref='strategyTable'
        class='strategy-table'
        v-bkloading={{ isLoading: this.table.loading }}
        empty-text={this.$t('无数据')}
        on={{
          'hook:mounted': this.handleTableMountedOrActivated,
          'hook:activated': this.handleTableMountedOrActivated,
        }}
        on-header-dragend={this.handleHeaderDragend}
        on-selection-change={this.handleSelectionChange}
        {...{
          props: {
            data: this.table.data,
          },
        }}
      >
        <div slot='empty'>
          <EmptyStatus
            type={this.emptyType}
            onOperation={this.handleOperation}
          />
        </div>
        <bk-table-column
          width='50'
          align='center'
          type='selection'
        />
        {id.checked && (
          <bk-table-column
            key='id'
            width='75'
            label='ID'
            prop='id'
            scopedSlots={idSlot}
          />
        )}
        {strategyName.checked && (
          <bk-table-column
            key='strategyName'
            label={this.$t('策略名')}
            min-width='200'
            scopedSlots={strategyNameSlot}
          />
        )}
        {itemDescription.checked && (
          <bk-table-column
            key='itemDescription'
            label={this.$t('监控项')}
            min-width='200'
            scopedSlots={itemDescriptionSlot}
          />
        )}
        {dataOrigin.checked && (
          <bk-table-column
            key='dataOrigin'
            width='110'
            label={this.$t('数据来源')}
            scopedSlots={dataOriginSlot}
          />
        )}
        {target.checked && (
          <bk-table-column
            key='target'
            width='150'
            label={this.$t('监控目标')}
            scopedSlots={targetSlot}
          />
        )}
        {labels.checked && (
          <bk-table-column
            key='labels'
            label={this.$t('标签')}
            scopedSlots={labelsSlot}
          />
        )}
        {noticeGroupList.checked && (
          <bk-table-column
            key='noticeGroupList'
            label={this.$t('告警组')}
            scopedSlots={noticeGroupListSlot}
          />
        )}
        {updator.checked && (
          <bk-table-column
            key='updator'
            width='150'
            label={this.$t('更新记录')}
            scopedSlots={updatorSlot}
          />
        )}
        {enabled.checked && (
          <bk-table-column
            key='enabled'
            width='100'
            label={this.$t('启/停')}
            scopedSlots={enabledSlot}
          />
        )}
        {dataTypeLabelName.checked && (
          <bk-table-column
            key='dataTypeLabelName'
            width='80'
            label={this.$t('策略类型')}
            scopedSlots={{ default: props => props.row.dataTypeLabelName }}
          />
        )}
        {intervalNotifyMode.checked && (
          <bk-table-column
            key='intervalNotifyMode'
            width='105'
            label={this.$t('通知间隔类型')}
            scopedSlots={{ default: props => props.row.intervalNotifyMode }}
          />
        )}
        {dataMode.checked && (
          <bk-table-column
            key='dataMode'
            width='105'
            label={this.$t('查询类型')}
            scopedSlots={{ default: props => props.row.dataMode }}
          />
        )}
        {notifyInterval.checked && (
          <bk-table-column
            key='notifyInterval'
            width='105'
            label={this.$t('通知间隔')}
            scopedSlots={{ default: props => `${props.row.notifyInterval}${this.$t('分钟')}` }}
          />
        )}
        {trigger.checked && (
          <bk-table-column
            key='trigger'
            width='105'
            label={this.$t('触发条件')}
            scopedSlots={triggerSlot}
          />
        )}
        {recovery.checked && (
          <bk-table-column
            key='recovery'
            width='105'
            label={this.$t('恢复条件')}
            scopedSlots={recoverySlot}
          />
        )}
        {needPoll.checked && (
          <bk-table-column
            key='needPoll'
            width='80'
            label={this.$t('告警风暴')}
            scopedSlots={needPollSlot}
          />
        )}
        {noDataEnabled.checked && (
          <bk-table-column
            key='noDataEnabled'
            width='80'
            label={this.$t('无数据')}
            scopedSlots={noDataEnabledSlot}
          />
        )}
        {signals.checked && (
          <bk-table-column
            key='signals'
            width='150'
            label={this.$t('通知场景')}
            scopedSlots={signalsSlot}
          />
        )}
        {levels.checked && (
          <bk-table-column
            key='levels'
            width='150'
            label={this.$t('级别')}
            scopedSlots={levelsSlot}
          />
        )}
        {detectionTypes.checked && (
          <bk-table-column
            key='detectionTypes'
            width='150'
            label={this.$t('检测规则类型')}
            scopedSlots={detectionTypesSlot}
          />
        )}
        {mealNames.checked && (
          <bk-table-column
            key='mealNames'
            width='150'
            label={this.$t('处理套餐')}
            scopedSlots={mealNamesSlot}
          />
        )}
        {configSource.checked && (
          <bk-table-column
            key='configSource'
            width='100'
            label={this.$t('配置来源')}
            scopedSlots={configSourceSlot}
          />
        )}
        {app.checked && (
          <bk-table-column
            key='app'
            width='100'
            label={this.$t('配置分组')}
            scopedSlots={appSlot}
          />
        )}
        {operator.checked && (
          <bk-table-column
            key='operator'
            width={this.$store.getters.lang === 'en' ? 220 : 150}
            label={this.$t('操作')}
            scopedSlots={operatorSlot}
          />
        )}
      </bk-table>
    );
  }

  getDialogComponent() {
    return [
      <div
        key={1}
        style='display: none;'
      >
        <ul
          ref='operatorGroup'
          class='operator-group'
        >
          <li
            class='operator-group-btn'
            onClick={this.handleViewRelatedAlerts}
          >
            {this.$t('相关告警')}
          </li>
          {!this.popover.data.shieldInfo.is_shielded ? (
            <li
              class='operator-group-btn'
              v-authority={{ active: !this.authority.MANAGE_AUTH }}
              onClick={() =>
                this.authority.MANAGE_AUTH
                  ? this.handleShowStrategy()
                  : this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH)
              }
            >
              {this.$t('快捷屏蔽')}
            </li>
          ) : (
            <li
              class='operator-group-btn'
              v-authority={{ active: !this.authority.MANAGE_AUTH }}
              onClick={() =>
                this.authority.MANAGE_AUTH
                  ? this.handleDeleteShield()
                  : this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH)
              }
            >
              {this.$t('解除屏蔽')}
            </li>
          )}
          <li
            class={['operator-group-btn', { 'btn-disabled': !this.popover.data.editAllowed }]}
            v-authority={{ active: !this.authority.MANAGE_AUTH }}
            v-bk-tooltips={{
              placements: ['right', 'left'],
              content: this.$t('内置策略不允许修改'),
              disabled: this.popover.data.editAllowed,
            }}
            onClick={() =>
              this.authority.MANAGE_AUTH
                ? this.popover.data.editAllowed && this.handleDeleteRow()
                : this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH)
            }
          >
            {' '}
            {this.$t('删除')}{' '}
          </li>
          <li
            class='operator-group-btn'
            v-authority={{ active: !this.authority.MANAGE_AUTH }}
            onClick={() =>
              this.authority.MANAGE_AUTH
                ? this.handleCopy()
                : this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH)
            }
          >
            {' '}
            {this.$t('克隆')}{' '}
          </li>
        </ul>
      </div>,
      <StrategyConfigDialog
        key={2}
        checked-list={this.idList}
        dialog-show={this.dialog.show}
        group-list={this.groupList}
        loading={this.dialogLoading}
        set-type={this.header.value}
        onConfirm={this.handleMuchEdit}
        onGetGroupList={this.getGroupList}
        onHideDialog={this.handleDialogChange}
      />,
      <AlarmShieldStrategy
        key={3}
        is-show-strategy={this.isShowStrategy}
        {...{
          on: {
            'update:isShowStrategy': val => {
              this.isShowStrategy = val;
            },
          },
        }}
        strategy-id={this.strategyId}
      />,
      <TableFilter
        key={4}
        filter-type={this.filterType}
        menu-list={this.dataSourceList}
        radio-list={this.dataSourceList}
        show={this.isShowTableFilter}
        target={this.label.target}
        value={this.label.value}
        on-confirm={this.handleFilterDataSourece}
        on-hide={this.handleChangeValue}
        on-reset={() => this.handleResetSourceFilter(true)}
        on-selected={this.handleSelectedDataSource}
      />,
      // this.targetSet.show ? (
      //   <StrategySetTarget
      //     dialog-show={this.targetSet.show}
      //     {...{ on: { 'update: dialogShow': val => (this.targetSet.show = val) } }}
      //     biz-id={this.targetSet.bizId}
      //     strategy-id={this.targetSet.strategyId}
      //     object-type={this.targetSet.objectType}
      //     title={this.targetSet.title.toString()}
      //     canSaveEmpty={true}
      //     on-show-change={this.handleTargetShowChange}
      //     on-targets-change={this.handleTargetsChange}
      //     on-target-type-change={this.handleTargetTypeChange}
      //     on-save-change={this.handleTargetSaveChange}
      //   ></StrategySetTarget>
      // ) : undefined,
      <StrategyIpv6
        key={5}
        bizId={this.targetSet.bizId}
        nodeType={this.targetSet.nodeType as INodeType}
        objectType={this.targetSet.objectType as TargetObjectType}
        showDialog={this.targetSet.show}
        strategyIds={this.targetSet.strategyIds}
        onCloseDialog={this.handleTargetShowChange}
        onSave={this.handleTargetSaveChange}
      />,
      <AlarmGroupDetail
        id={this.alarmGroupDialog.id}
        key={6}
        v-model={this.alarmGroupDialog.show}
        hasEditBtn={false}
      />,
    ];
  }

  render() {
    if (!this.authLoading && !this.hasPageViewAuth && this.isQueryAuthDone) {
      return <AuthComponent actionId={strategyAuth.VIEW_AUTH} />;
    }
    return (
      <div class='strategy-config'>
        <div class='content'>
          <div
            style={{ flexBasis: `${this.dropWidth}px`, width: `${this.dropWidth}px` }}
            class={['content-left', { hidden: !this.showFilterPanel }]}
            v-show='showFilterPanel'
            data-tag='resizeTarget'
          >
            <FilterPanel
              class='content-left-filter'
              show={this.showFilterPanel}
              {...{
                on: {
                  'update:show': val => {
                    this.showFilterPanel = val;
                  },
                },
              }}
              checkedData={this.header.keywordObj}
              data={this.showFilterPanelData}
              showSkeleton={this.authLoading || this.loading}
              on-change={this.handleSearchSelectChange}
            >
              <div
                class='filter-panel-header mb20'
                slot='header'
              >
                <span class='title'>{this.$t('筛选')}</span>
                <FilterPanelPopover
                  list={this.filterPanelData}
                  showFields={this.showFilterPanelField}
                  onFilterFieldChange={this.handleFilterFieldsChange}
                />
              </div>
            </FilterPanel>
            <div
              class={['content-left-drag', { hidden: !this.showFilterPanel }]}
              onMousedown={this.handleMouseDown}
              onMousemove={this.handleMouseMove}
            />
          </div>
          <div
            id='content-for-watch-resize'
            class='content-right'
          >
            <div class='strategy-config-header'>
              <bk-badge
                class='badge'
                v-show={!this.showFilterPanel}
                theme='success'
                visible={this.header.keywordObj.length !== 0}
                dot
              >
                <span
                  class='folding'
                  onClick={this.handleShowFilterPanel}
                >
                  <i class='icon-monitor icon-double-up' />
                </span>
              </bk-badge>
              <bk-button
                class='header-btn mc-btn-add'
                v-authority={{ active: !this.authority.MANAGE_AUTH }}
                theme='primary'
                onClick={() =>
                  this.authority.MANAGE_AUTH
                    ? this.handleAddStategyConfig()
                    : this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH)
                }
              >
                <span class='icon-monitor icon-plus-line mr-6' />
                {this.$t('新建')}
              </bk-button>
              <bk-dropdown-menu
                class='header-select'
                disabled={!this.table.select.length}
                trigger='click'
                on-hide={() => (this.header.dropdownShow = false)}
                on-show={() => (this.header.dropdownShow = true)}
              >
                <div
                  class={['header-select-btn', { 'btn-disabled': !this.table.select.length }]}
                  slot='dropdown-trigger'
                >
                  <span class='btn-name'> {this.$t('批量操作')} </span>
                  <i class={['icon-monitor', this.header.dropdownShow ? 'icon-arrow-up' : 'icon-arrow-down']} />
                </div>
                <ul
                  class='header-select-list'
                  slot='dropdown-content'
                  v-authority={{
                    active: !this.authority.MANAGE_AUTH,
                  }}
                  onClick={() =>
                    !this.authority.MANAGE_AUTH && this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH)
                  }
                >
                  {/* 批量操作监控目标需要选择相同类型的监控对象 */}
                  {this.header.list.map((option, index) => (
                    <li
                      key={index}
                      class={['list-item', { disabled: this.isBatchItemDisabled(option) }]}
                      v-bk-tooltips={{
                        placement: 'right',
                        boundary: 'window',
                        disabled: !this.isBatchItemDisabled(option),
                        content: () => this.batchItemDisabledTip(option),
                        delay: 200,
                        allowHTML: false,
                      }}
                      onClick={() =>
                        this.authority.MANAGE_AUTH &&
                        !this.isBatchItemDisabled(option) &&
                        this.handleHeadSelectChange(option.id)
                      }
                    >
                      {option.name}
                    </li>
                  ))}
                </ul>
              </bk-dropdown-menu>
              <SearchSelect
                key={this.selectKey}
                class='header-search'
                data={this.conditionList}
                modelValue={this.header.keywordObj}
                placeholder={this.$t('任务ID / 告警组名称 / IP / 指标ID')}
                uniqueSelect={true}
                clearable
                onChange={this.handleSearchChange}
              />
            </div>
            <div class='strategy-config-wrap'>
              <div class='config-wrap-setting'>
                <bk-popover
                  width='515'
                  ext-cls='strategy-table-setting'
                  offset='0, 20'
                  placement='bottom'
                  theme='light strategy-setting'
                  trigger='click'
                >
                  <div class='setting-btn'>
                    <i class='icon-monitor icon-menu-set' />
                  </div>
                  <div
                    class='tool-popover'
                    slot='content'
                  >
                    <div class='tool-popover-title'>
                      {this.$t('字段显示设置')}
                      <bk-checkbox
                        class='all-selection'
                        value={this.fieldAllSelected}
                        onChange={this.handleFieldAllSelected}
                      >
                        {this.$t('全选')}
                      </bk-checkbox>
                    </div>
                    <ul class='tool-popover-content'>
                      {Object.keys(this.fieldSettingData).map(key => (
                        <li
                          key={this.fieldSettingData[key].id}
                          class='tool-popover-content-item'
                        >
                          <bk-checkbox
                            disabled={this.fieldSettingData[key].disable}
                            value={this.fieldSettingData[key].checked}
                            onChange={() => this.handleCheckColChange(this.fieldSettingData[key])}
                          >
                            {this.fieldSettingData[key].name}
                          </bk-checkbox>
                        </li>
                      ))}
                    </ul>
                  </div>
                </bk-popover>
              </div>
              {this.authLoading || this.table.loading || this.loading ? (
                <TableSkeleton type={2} />
              ) : (
                [
                  this.getTableComponent(),
                  this.table.data?.length ? (
                    <bk-pagination
                      key='table-pagination'
                      class='strategy-pagination list-pagination'
                      v-show={this.tableInstance.total}
                      align='right'
                      count={this.pageCount}
                      current={this.tableInstance.page}
                      limit={this.tableInstance.pageSize}
                      limit-list={this.tableInstance.pageList}
                      size='small'
                      pagination-able
                      show-total-count
                      on-change={this.handlePageChange}
                      on-limit-change={this.handleLimitChange}
                    />
                  ) : undefined,
                ]
              )}
            </div>
          </div>
        </div>
        {this.getDialogComponent()}
      </div>
    );
  }
}

export default ofType<IStrategyConfigProps>().convert(StrategyConfig);
