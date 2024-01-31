/* eslint-disable no-param-reassign */
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
import { Component, Inject, Mixins, Prop, Watch } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';
import { addListener, removeListener } from '@blueking/fork-resize-detector';
import dayjs from 'dayjs';
import { debounce } from 'throttle-debounce';

import { CancelToken } from '../../../../monitor-api/index';
import { exportConfigFile } from '../../../../monitor-api/modules/as_code';
import { noticeGroupList } from '../../../../monitor-api/modules/notice_group';
import { disableShield } from '../../../../monitor-api/modules/shield';
import {
  deleteStrategyV2,
  getScenarioList,
  getStrategyListV2,
  getTargetDetail,
  updatePartialStrategyV2
} from '../../../../monitor-api/modules/strategies';
import { xssFilter } from '../../../../monitor-common/utils/xss';
import EmptyStatus from '../../../components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../../components/empty-status/types';
import { INodeType, TargetObjectType } from '../../../components/monitor-ip-selector/typing';
import SvgIcon from '../../../components/svg-icon/svg-icon.vue';
import TableFilter from '../../../components/table-filter/table-filter.vue';
// import StrategySetTarget from '../strategy-config-set/strategy-set-target/strategy-set-target.vue';
import commonPageSizeMixin from '../../../mixins/commonPageSizeMixin';
import { downFile } from '../../../utils';
import AlarmShieldStrategy from '../../alarm-shield/quick-alarm-shield/quick-alarm-shield-strategy.vue';
import TableStore, { invalidTypeMap } from '../store';
import StrategyConfigDialog from '../strategy-config-dialog/strategy-config-dialog';
import FilterPanel from '../strategy-config-list/filter-panel';
import { IGroupData } from '../strategy-config-list/group';
import StrategyIpv6 from '../strategy-ipv6/strategy-ipv6';
import { handleMouseDown, handleMouseMove } from '../util';

import DeleteSubtitle from './delete-subtitle';
import { IHeader, ILabel, IPopover, IStrategyConfigProps } from './type';

import './strategy-config.scss';

const { i18n } = window;
const UN_SET_ACTION = 'UN_SET_ACTION';
const STRATEGY_CONFIG_SETTING = 'strategy_config_setting';

@Component({
  name: 'StrategyConfig'
})
class StrategyConfig extends Mixins(commonPageSizeMixin) {
  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('authorityMap') authorityMap;
  @Inject('strategyType') strategyType;
  @Prop({ type: String, default: '' }) fromRouteName: IStrategyConfigProps['fromRouteName'];
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
  @Prop({ type: [String, Array] }) scenario: string;
  @Prop({ type: [String, Array] }) strategyState: string;
  @Prop({ type: Array }) keywords: IStrategyConfigProps['keywords']; /** 支持传入自定义搜索关键词 */
  @Prop({ type: String, default: '' }) resultTableId: IStrategyConfigProps['resultTableId']; /** 结果表搜索条件 */

  showFilterPanel = true;
  header: IHeader = {
    value: 0,
    dropdownShow: false,
    list: [
      // { id: 0, name: i18n.t('修改告警组') },
      { id: 1, name: i18n.t('修改触发条件') },
      { id: 5, name: i18n.t('修改恢复条件') },
      // { id: 2, name: i18n.t('修改通知间隔') },
      { id: 3, name: i18n.t('修改无数据告警') },
      // { id: 4, name: i18n.t('修改告警恢复通知') },
      { id: 6, name: i18n.t('启/停策略') },
      { id: 7, name: i18n.t('删除策略') },
      // { id: 9, name: i18n.t('修改告警模版') },
      { id: 8, name: i18n.t('增删目标') },
      { id: 10, name: i18n.t('修改标签') },
      // { id: 11, name: i18n.t('修改处理套餐') }
      { id: 12, name: i18n.t('修改生效时间段') },
      { id: 13, name: i18n.t('修改处理套餐') },
      { id: 14, name: i18n.t('修改告警组') },
      { id: 15, name: i18n.t('修改通知场景') },
      { id: 16, name: i18n.t('修改通知间隔') },
      { id: 17, name: i18n.t('修改通知模板') },
      { id: 18, name: i18n.t('修改告警风暴开关') },
      { id: 19, name: i18n.t('导出Yaml') }
    ],
    keyword: '',
    keywordObj: [], // 搜索框绑定值
    condition: [], // 搜索条件接口参数
    conditionList: [], // 搜索可选项
    handleSearch: () => {}
  };
  dataSourceList = [
    {
      value: '',
      id: 'bk_monitor',
      checked: 'bk_monitor',
      cancel: '',
      name: i18n.t('监控采集')
    },
    {
      value: '',
      id: 'log',
      checked: 'bk_monitor',
      cancel: '',
      name: i18n.t('日志采集')
    }
  ];
  label: ILabel = {
    target: null,
    isSelected: false,
    selectedLabels: '',
    serviceCategory: '',
    noticeName: ''
  };
  popover: IPopover = {
    instance: null,
    hover: -1,
    edit: false,
    status: '',
    data: {
      shieldInfo: {
        is_shielded: true
      },
      strategyName: ''
    }
  };
  table = {
    data: [],
    loading: false,
    select: []
  };
  pageCount = 0;
  dialog = {
    show: false,
    selectList: []
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
    getItemDescription: () => []
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
    title: i18n.t('监控目标'),
    nodeType: ''
  };
  strategyLabelList = []; // 标签筛选俩表
  actionNameList = []; // 自愈套餐列表
  sourceList = []; // 数据来源筛选列表
  typeList = []; // 分类可筛选列表
  filterType = 'checkbox'; // 筛选列表类型
  curFilterType = i18n.t('数据来源'); // 当前筛选类型
  dialogLoading = false;
  groupList = []; // 告警组数据列表
  scenarioList = []; // 监控对象
  fieldSettingData: any = {};
  fieldAllSelected = false; // 是否全选
  drapWidth = 214;
  noticeGroupList = [];
  conditionList = [];
  /** 策略状态数据 */
  strategyStatusOptions = [
    {
      id: 'ALERT',
      name: window.i18n.tc('告警中'),
      count: 0
    },
    {
      id: 'INVALID',
      name: window.i18n.tc('已失效'),
      count: 0
    },
    {
      name: window.i18n.tc('已停用'),
      id: 'OFF',
      count: 0
    },
    {
      name: window.i18n.tc('已启用'),
      id: 'ON',
      count: 0
    },
    {
      name: window.i18n.tc('屏蔽中'),
      id: 'SHIELDED',
      count: 0
    }
  ];
  ipCheckValue = {};
  ipSelectorPanels = [];
  ipTargetType = 'TOPO';
  ipSelectorShow = false;
  emptyType: EmptyStatusType = 'empty'; // 空状态
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
  get filterPanelData(): IGroupData[] {
    // 筛选面板数据
    // 过滤需要展示的分组（监控对象、数据来源、告警组）
    const displayKeys = ['scenario', 'dataSource', 'noticeName', 'strategyLabels', 'actionName'];
    const iconMap = {
      ALERT: 'icon-mc-chart-alert',
      INVALID: 'icon-shixiao',
      OFF: 'icon-zanting1',
      ON: 'icon-kaishi1',
      SHIELDED: 'icon-menu-shield'
    };
    const strategyStatusFilter = {
      id: 'strategy_status',
      name: this.$t('状态'),
      data: this.strategyStatusOptions.map(item => ({
        ...item,
        count: item.count || 0,
        icon: iconMap[item.id]
      }))
    };
    return [
      strategyStatusFilter,
      ...displayKeys.map(key => {
        const { id, name, list } = this.backDisplayMap[key];
        return {
          id,
          name,
          data: key === 'noticeName' ? this.groupList.map(({ name, count }) => ({ id: name, name, count })) : list
        };
      })
    ];
  }

  get isFta() {
    return this.strategyType === 'fta';
  }

  @Watch('table.data')
  handleTableDataChange(v) {
    // 用于数据样式自适应
    setTimeout(() => {
      v.forEach((item, index) => {
        const ref: any = this.$refs[`table-row-${index}`]; /* 告警组 */
        item.overflow = ref && ref.clientHeight > 32;
        const refLabel: any = this.$refs[`table-labels-${index}`];
        // 这里计算整个 label 容器内是否会出现 换行 的可能，若换行就显示省略号。
        item.overflowLabel = refLabel && refLabel.clientHeight > 32; /* 标签组样式 */
        // if (item.overflowLabel) {
        //   let overflowIndex = 0;
        //   const classifyList = refLabel.getElementsByClassName('classifiy-label');
        //   // eslint-disable-next-line @typescript-eslint/prefer-for-of
        //   for (let i = 0; i < classifyList.length; i++) {
        //     if (classifyList[i].offsetTop > 24) {
        //       overflowIndex = i;
        //       break;
        //     }
        //   }
        //   item.extraLabel = item.labels.slice(overflowIndex, item.labels.length);
        // }
        const overflowMap = ['signals', 'levels', 'detectionTypes', 'mealNames'];
        overflowMap.forEach(key => {
          // 通用数据样式
          const refDom: any = this.$refs[`table-${key}-${index}`];
          item[`overflow${key}`] = refDom && refDom.clientHeight > 32;
        });
      });
    }, 50);
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
  @Watch('strategyLabelList')
  handleStrategyLabelList(v) {
    if (v) {
      this.backDisplayMap.strategyLabels.list = v;
      this.createdConditionList();
    }
  }
  @Watch('actionNameList')
  handleActionNameList(v) {
    if (v) {
      this.backDisplayMap.actionName.list = v;
      this.createdConditionList();
    }
  }
  @Watch('sourceList')
  handleSourceList(v) {
    if (v) {
      this.backDisplayMap.dataSource.list = v;
      this.createdConditionList();
    }
  }
  @Watch('groupList')
  handleGroupList(v) {
    if (v) {
      this.backDisplayMap.noticeName.list = v.map(item => ({
        id: item.name,
        name: item.name
      }));
      this.createdConditionList();
    }
  }

  created() {
    this.backDisplayMap = {
      bkStrategyId: {
        name: this.$t('策略ID'),
        value: [],
        id: 'strategy_id'
      },
      bkStrategyName: {
        name: this.$t('策略名'),
        value: [],
        id: 'strategy_name'
      },
      // 告警组
      noticeName: {
        name: this.$t('告警组'), // 输入框回显的名称
        value: this.noticeName, // 回显的值
        id: 'user_group_name' // 传给后端的字段名
      },
      // 服务分类
      serviceCategory: {
        name: this.$t('服务分类'),
        value: this.serviceCategory,
        id: 'service_category'
      },
      // 拨测任务
      taskId: {
        name: this.$t('拨测任务ID'),
        value: this.taskId,
        id: 'task_id'
      },
      // 主机监控
      ip: {
        name: 'IP',
        value: this.ip,
        id: 'IP'
      },
      // 管控区域ID
      bkCloudId: {
        name: this.$t('管控区域ID'),
        value: this.bkCloudId,
        id: 'bk_cloud_id'
      },
      // 自定义事件
      bkEventGroupId: {
        name: this.$t('自定义事件分组ID'),
        value: this.bkEventGroupId,
        id: 'bk_event_group_id'
      },
      // 自定义指标分组ID
      timeSeriesGroupId: {
        name: this.$t('分组ID'),
        value: this.timeSeriesGroupId,
        id: 'time_series_group_id'
      },
      // 插件ID
      pluginId: {
        name: this.$t('插件ID'),
        value: this.pluginId,
        id: 'plugin_id'
      },
      // 仪表盘
      metricId: {
        name: this.$t('指标ID'),
        value: this.metricId,
        id: 'metric_id'
      },
      metricAlias: {
        name: this.$t('指标别名'),
        value: '',
        id: 'metric_alias'
      },
      metricName: {
        name: this.$t('指标名'),
        value: '',
        id: 'metric_name'
      },
      creators: {
        name: this.$t('创建人'),
        value: '',
        id: 'creators'
      },
      updaters: {
        name: this.$t('最近更新人'),
        value: '',
        id: 'updaters'
      },
      strategyState: {
        name: this.$t('状态'),
        value: '',
        id: 'strategy_status',
        list: this.strategyStatusOptions
      },
      dataSource: {
        name: this.$t('数据来源'),
        value: '',
        id: 'data_source_list',
        list: []
      },
      scenario: {
        name: this.$t('监控对象'),
        value: '',
        id: 'scenario',
        list: []
      },
      strategyLabels: {
        name: this.$t('标签'),
        value: '',
        id: 'label_name',
        list: []
      },
      actionName: {
        name: this.$t('套餐名'),
        value: '',
        id: 'action_name',
        list: []
      },
      resultTableId: {
        name: this.$t('结果表'),
        value: '',
        id: 'result_table_id',
        list: []
      },
      level: {
        name: this.$t('告警级别'),
        value: '',
        id: 'level',
        list: [
          { id: 1, name: this.$t('致命') },
          { id: 2, name: this.$t('预警') },
          { id: 3, name: this.$t('提醒') }
        ]
      },
      algorithmType: {
        name: this.$t('算法类型'),
        value: '',
        id: 'algorithm_type',
        list: [
          {
            id: 'Threshold',
            name: window.i18n.tc('静态阈值')
          },
          {
            id: 'SimpleRingRatio',
            name: window.i18n.tc('简易环比')
          },
          {
            id: 'AdvancedRingRatio',
            name: window.i18n.tc('高级环比')
          },
          {
            id: 'SimpleYearRound',
            name: window.i18n.tc('简易同比')
          },
          {
            id: 'AdvancedYearRound',
            name: window.i18n.tc('高级同比')
          },
          {
            id: 'PartialNodes',
            name: window.i18n.tc('部分节点数算法')
          },
          {
            id: 'OsRestart',
            name: window.i18n.tc('主机重启')
          },
          {
            id: 'ProcPort',
            name: window.i18n.tc('进程端口')
          },
          {
            id: 'PingUnreachable',
            name: window.i18n.tc('Ping不可达算法')
          },
          {
            id: 'YearRoundAmplitude',
            name: window.i18n.tc('同比振幅')
          },
          {
            id: 'YearRoundRange',
            name: window.i18n.tc('同比区间')
          },
          {
            id: 'RingRatioAmplitude',
            name: window.i18n.tc('环比振幅')
          },
          {
            id: 'IntelligentDetect',
            name: window.i18n.tc('智能异常检测算法')
          },
          {
            id: 'TimeSeriesForecasting',
            name: window.i18n.tc('时序预测')
          },
          {
            id: 'AbnormalCluster',
            name: window.i18n.tc('离群检测')
          }
        ]
      },
      invalidType: {
        name: this.$t('失效类型'),
        value: '',
        id: 'invalid_type',
        list: Object.entries(invalidTypeMap).map(item => ({
          id: item[0],
          name: item[1]
        }))
      }
    };
    this.fieldSettingData = {
      id: {
        checked: true,
        disable: true,
        name: 'ID',
        id: 'id'
      },
      strategyName: {
        checked: true,
        disable: true,
        name: this.$t('策略名'),
        id: 'strategyName'
      },
      itemDescription: {
        checked: true,
        disable: false,
        name: this.$t('监控项'),
        id: 'itemDescription'
      },
      dataOrigin: {
        checked: false,
        disable: false,
        name: this.$t('数据来源'),
        id: 'dataOrigin'
      },
      target: {
        checked: !this.isFta,
        disable: this.isFta,
        name: this.$t('监控目标'),
        id: 'target'
      },
      labels: {
        checked: true,
        disable: false,
        name: this.$t('标签'),
        id: 'labels'
      },
      noticeGroupList: {
        checked: true,
        disable: false,
        name: this.$t('告警组'),
        id: 'noticeGroupList'
      },
      updator: {
        checked: false,
        disable: false,
        name: this.$t('更新记录'),
        id: 'updator'
      },
      enabled: {
        checked: true,
        disable: true,
        name: this.$t('启/停'),
        id: 'enabled'
      },
      dataTypeLabelName: {
        checked: false,
        disable: false,
        name: this.$t('策略类型'),
        id: 'dataTypeLabelName'
      },
      intervalNotifyMode: {
        checked: false,
        disable: false,
        name: this.$t('通知间隔类型'),
        id: 'intervalNotifyMode'
      },
      dataMode: {
        checked: false,
        disable: false,
        name: this.$t('查询类型'),
        id: 'dataMode'
      },
      notifyInterval: {
        checked: false,
        disable: false,
        name: this.$t('通知间隔'),
        id: 'notifyInterval'
      },
      trigger: {
        checked: false,
        disable: false,
        name: this.$t('触发条件'),
        id: 'trigger'
      },
      recovery: {
        checked: false,
        disable: false,
        name: this.$t('恢复条件'),
        id: 'recovery'
      },
      needPoll: {
        checked: false,
        disable: false,
        name: this.$t('告警风暴'),
        id: 'needPoll'
      },
      noDataEnabled: {
        checked: false,
        disable: false,
        name: this.$t('无数据'),
        id: 'noDataEnabled'
      },
      signals: {
        checked: false,
        disable: false,
        name: this.$t('通知场景'),
        id: 'signals'
      },
      levels: {
        checked: false,
        disable: false,
        name: this.$t('级别'),
        id: 'levels'
      },
      detectionTypes: {
        checked: false,
        disable: false,
        name: this.$t('检测规则类型'),
        id: 'detectionTypes'
      },
      mealNames: {
        checked: false,
        disable: false,
        name: this.$t('处理套餐'),
        id: 'mealNames'
      },
      configSource: {
        checked: false,
        disable: false,
        name: this.$t('配置来源'),
        id: 'configSource'
      },
      app: {
        checked: false,
        disable: false,
        name: this.$t('配置分组'),
        id: 'app'
      },
      operator: {
        checked: true,
        disable: true,
        name: this.$t('操作'),
        id: 'operator'
      }
    };
    this.header.handleSearch = debounce(300, false, () => {
      this.handleGetListData(false, 1);
    });
    this.createdConditionList();
  }

  activated() {
    if (
      !['strategy-config-edit', 'strategy-config-add', 'strategy-config-detail', 'strategy-config-target'].includes(
        this.fromRouteName
      )
    ) {
      if (this.tableInstance.setDefaultStore) {
        this.tableInstance.setDefaultStore();
      }
      this.header.keyword = '';
    }
    this.checkColInit();
    this.handleSetDashboard();
    this.handleSearchBackDisplay();
    this.handleGetListData(true, 1);
    this.getGroupList();
  }

  /**
   * @description: 表格设置
   * @param {*}
   * @return {*}
   */
  checkColInit() {
    let fieldSettingData: any = localStorage.getItem(STRATEGY_CONFIG_SETTING);
    if (fieldSettingData) {
      fieldSettingData = JSON.parse(fieldSettingData);
      fieldSettingData.forEach(item => {
        if (this.fieldSettingData[item.id]) {
          this.fieldSettingData[item.id].checked = item.checked;
        }
      });
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
      checked: this.fieldSettingData[key].checked
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
    Object.keys(this.fieldSettingData).forEach(key => {
      if (v) {
        this.fieldSettingData[key].checked = true;
      }
      if (!this.fieldSettingData[key].disable && !v) {
        this.fieldSettingData[key].checked = false;
      }
    });
    const result = Object.keys(this.fieldSettingData).map(key => ({
      id: key,
      checked: this.fieldSettingData[key].checked
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
      this.$t('处理套餐')
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
    Object.keys(map).forEach(key => {
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
          values
        });
      }
    });
    if (!!this.keywords?.length) {
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
    data.forEach(item => {
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
        value
      };
      res.push(temp);
    });
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
    Object.keys(map).forEach(key => {
      const { name, id, list } = map[key];
      if (id === 'scenario') {
        const resChildren = [];
        list.forEach(listItem => {
          if (listItem.children) {
            listItem.children.forEach(item => {
              resChildren.push(item);
            });
          }
        });
        res.push({
          name,
          id,
          multiable: true,
          children: resChildren ? resChildren : []
        });
      } else {
        res.push({
          name,
          id,
          multiable: true,
          children: list ? list : []
        });
      }
    });
    this.conditionList = res;
  }
  /**
   * 初始化查询参数
   * @param {String} metricId（指标ID有可能从sessionStorage中来）
   */
  handleInitQueryParams(metricId) {
    Object.keys(this.backDisplayMap).forEach(key => {
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
            values
          });
        }
      }
    });
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
      SET_TEMPLATE: '{0}个集群模板'
    };
    tableData.forEach(item => {
      const target = targetMap[item.id];
      item.objectType = item.objectType || target.instance_type;
      item.targetNodeType = item.node_type;
      if (target.instance_type === 'HOST') {
        if (['SERVICE_TEMPLATE', 'SET_TEMPLATE', 'TOPO'].includes(target.node_type)) {
          // eslint-disable-next-line
          item.target = `${this.$t(textMap[target.node_type],[target.node_count])} （${this.$t('共{0}台主机', [target.instance_count])}）`;
        } else if (target.node_type === 'INSTANCE') {
          item.target = this.$t('{0}台主机', [target.node_count]);
        }
      } else if (target.instance_type === 'SERVICE') {
        if (['SERVICE_TEMPLATE', 'SET_TEMPLATE', 'TOPO'].includes(target.node_type)) {
          // eslint-disable-next-line vue/max-len
          item.target = `${this.$t(textMap[target.node_type], [target.node_count])} （${this.$t('共{0}个实例', [
            target.instance_count
          ])}）`;
        }
      } else {
        item.target = '';
      }
    });
    return tableData;
  }
  setTableFilterSelect(filterType) {
    this.curFilterType = filterType;
    const displayMap = this.backDisplayMap;
    const mapKeys = Object.keys(displayMap);
    const keyMap = {
      [String(this.$t('数据来源'))]: () => mapKeys.find(key => displayMap[key].name === filterType),
      [String(this.$t('告警组'))]: () => mapKeys.find(key => displayMap[key].name === filterType)
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
    const pageSize = defPageSize || this.tableInstance.pageSize || this.handleGetCommonPageSize();
    const params = {
      type: this.strategyType,
      page,
      page_size: pageSize,
      // search: this.header.keyword,
      conditions: this.header.condition,
      // data_source_list: this.label.selectedLabels || [],
      order_by: '-update_time',
      with_user_group: true
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
        const total = await this.handelScenarioList(data, this.table.data);
        // todo
        this.pageCount = total;
        // this.pageCount = this.tab.active > 0 ? this.tab.list[this.tab.active].count : total
        this.strategyStatusOptions = data.strategy_status_list || [];
        this.sourceList = data.data_source_list
          .map(item => {
            const { type, name, count } = item;
            return { id: type, name, count: count ? count : 0 };
          })
          .sort((pre, next) => next.count - pre.count);
        this.strategyLabelList = data.strategy_label_list
          .map(item => {
            const { id, count } = item;
            return { id, count, name: item.label_name };
          })
          .sort((pre, next) => next.count - pre.count);
        this.actionNameList = data.action_config_list
          .map(item => {
            const { name, count, id } = item;
            return { id: id !== 0 ? name : UN_SET_ACTION, count, name };
          })
          .sort((pre, next) => next.count - pre.count);
        const noticeGroupList = data.user_group_list;
        this.groupList = noticeGroupList
          .map(item => {
            const { count } = item;
            return {
              count,
              name: item.user_group_name,
              id: item.user_group_id
            };
          })
          .sort((pre, next) => next.count - pre.count);
        // magic code  reflesh bk table
        this.$refs.strategyTable?.doLayout?.();
      })
      .catch(() => {
        this.emptyType = '500';
      })
      .finally(() => {
        this.loading = false;
        this.table.loading = false;
      });
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
    scenarioFather.forEach(item => {
      let count = 0;
      item.children.forEach(set => {
        const res = scenarioList.find(child => child.id === set.id);
        count += res.count;
        // total += res.count;
        set.count = res.count;
      });
      item.count = count;
    });
    this.backDisplayMap.scenario.list = scenarioFather;
    this.handleUpdateScenarioListName();
    tableData.forEach(item => {
      const nameArr = this.getScenarioName(scenarioFather, item.strategyType);
      item.scenarioDisplayName = nameArr.join('-');
    });
    // 列表total设置为数据来源筛选项count总和
    total = data.data_source_list.reduce((total, item) => total + item.count, 0);
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
          name
        };
      }));
  }
  getScenarioName(treeData, id) {
    const name = [];
    let level = 0;
    let isFind = false;
    const fn = (data, isFirst = false) => {
      if (isFind) return;
      // eslint-disable-next-line no-restricted-syntax
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
    this.handleSetCommonPageSize(limit);
    this.handleGetListData(false, 1, limit);
  }
  handleHeadSelectChange(v) {
    // 导出 Yaml 文件
    if (v === 19) {
      exportConfigFile({
        rule_ids: (this.table.select || []).map(item => item.id),
        with_related_config: true
      })
        .then(data => {
          if (!data?.download_url?.length) return;
          downFile(data.download_url, this.$tc('策略导出'));
        })
        .catch(() => {
          this.$bkMessage({
            message: this.$t('导出出错了'),
            theme: 'error'
          });
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
    const checkedData = [];
    if (type === 'INSTANCE') {
      data.forEach(item => {
        checkedData.push({
          ip: item.ip,
          bk_cloud_id: item.bk_cloud_id,
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
        }
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
            18: this.$t('批量修改告警风暴开关成功')
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
      noDataEnabled: { no_data_config: { is_enabled: !enable } }
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
          }
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
          name: this.popover.data.strategyName
        }
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
      }
    });
  }
  // 拷贝策略
  handleCopy() {
    const item = this.popover.data;
    this.$router.push({
      name: 'strategy-config-clone',
      params: {
        id: item.id
      }
    });
  }
  handleAddStategyConfig() {
    this.$router.push({
      name: 'strategy-config-add',
      params: {
        objectId: ''
      }
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
        id: item.id
      }
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
        id: data.id
      }
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
      }
    });
  }
  /* 查看相关告警 */
  handleViewRelatedAlerts() {
    const query = `queryString=${
      ['zh', 'zhCN', 'zh-cn'].includes(window.i18n.locale)
        ? `告警名称 : "${this.popover.data.strategyName}"`
        : `alert_name : "${this.popover.data.strategyName}"`
    }`;
    const timeRange = 'from=now-7d&to=now';
    window.open(`${location.origin}${location.pathname}${location.search}#/event-center?${query}&${timeRange}`);
  }
  handleSelectedDataSource(v) {
    this.label.isSelected = Boolean(v.length);
  }
  setHeaderKeyword(value) {
    const displayMap = this.backDisplayMap;
    const mapKeys = Object.keys(displayMap);
    const keyMap = {
      [String(this.$t('数据来源'))]: () => mapKeys.find(key => displayMap[key].name === this.curFilterType),
      [String(this.$t('告警组'))]: () => mapKeys.find(key => displayMap[key].name === this.curFilterType)
    };
    const backDisplayMapKey = keyMap[String(this.curFilterType)]();
    const searchKey = displayMap[keyMap[String(this.curFilterType)]()].id;
    const hasKey = this.header.keywordObj.find(item => item.id === searchKey);
    const { list } = displayMap[backDisplayMapKey];
    const name = this.curFilterType;
    if (value) {
      const values = value.map(item => ({
        id: item,
        name: list ? list.find(set => set.id === item).name : item
      }));
      const obj = {
        id: searchKey,
        multiable: true,
        name,
        values
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
      }
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
      [String(this.$t('告警组'))]: () => (this.label.noticeName = '')
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
        value: this.label.selectedLabels
      },
      // [this.$t('分类')]: this.typeList,
      [String(this.$t('告警组'))]: {
        list: this.groupList.map(item => ({
          id: item.name,
          name: item.name
        })),
        value: this.label.noticeName
      }
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
        onClick={e => this.handleShowTableFilter(e, type, title)}
        class={{ 'dropdown-trigger': true, ' plugin-label': true, selected: active }}
        slot='dropdown-trigger'
      >
        {titleStr}
        <i class='icon-monitor icon-filter-fill'></i>
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
          count: item.related_strategy
        }))
        .sort((pre, next) => next.count - pre.count);
    });
    this.dialogLoading = false;
  }
  /* 跳转到事件中心 */
  handleToEventCenter(item, type = 'NOT_SHIELDED_ABNORMAL') {
    const url = `${location.origin}${location.pathname}${location.search}#/event-center?queryString=${
      ['zh', 'zhCN', 'zh-cn'].includes(window.i18n.locale) ? `策略ID : ${item.id}` : `strategy_id : ${item.id}`
    }&activeFilterId=${type}&from=now-30d&to=now`;
    window.open(url);
  }
  /**
   * @description: 筛选面板勾选change事件
   * @param {*} data
   * @return {*}
   */
  handleSearchSelectChange(data = []) {
    data.forEach(item => {
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
    });
    this.handleGetListData(false, 1);
  }
  handleShowFilterPanel() {
    this.drapWidth = 214;
    this.showFilterPanel = true;
  }
  handleMouseDown(e) {
    handleMouseDown(e, 'resizeTarget', 114, { min: 214, max: 500 }, width => {
      this.showFilterPanel = width !== 0;
      this.drapWidth = width;
    });
  }
  handleMouseMove(e) {
    handleMouseMove(e);
  }
  // 处理监控项tooltips
  handleDescTips(data) {
    const tips = data.map(item => `<div>${xssFilter(item.tip)}</div>`).join('');
    const res = `<div class="item-description">${tips}</div>`;
    return res;
  }
  // 批量操作下的选项是否不可点击
  isBatchItemDisabled(option: any) {
    return (option.id === 8 && (this.isFta || !this.isSameObjectType)) || (option.id === 9 && this.isFta);
  }
  batchItemDisabledTip(option: any) {
    const tipMap = {
      9: this.$t('无需修改告警模板'),
      8: this.isFta ? this.$t('无需设置监控目标') : this.$t('监控对象不一致')
    };
    return tipMap[option.id];
  }

  /* 候选搜索列表过滤 */
  conditionListFilter() {
    const allKey = this.header.keywordObj.map(item => item.id);
    return this.conditionList.filter(item => !allKey.includes(item.id));
  }
  /* 跳转到屏蔽页 */
  handleToAlarmShield(ids: number[]) {
    const queryString = encodeURIComponent(JSON.stringify([{ key: 'id', value: ids }]));
    window.open(`${location.origin}${location.pathname}${location.search}#/alarm-shield?queryString=${queryString}`);
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

  getTableComponent() {
    const idSlot = {
      default: props => props.row.id
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
                allowHTML: false
              }}
            >
              <router-link
                class='name-text-link'
                to={{
                  name: 'strategy-config-detail',
                  params: {
                    title: props.row.strategyName,
                    id: props.row.id
                  }
                }}
              >
                {props.row.strategyName}
              </router-link>
            </span>
            {[
              props.row.isInvalid ? (
                <i
                  v-bk-tooltips={{
                    placements: ['right'],
                    boundary: 'window',
                    content: `${props.row.invalidType}`,
                    allowHTML: false
                  }}
                  class='icon-monitor icon-shixiao'
                ></i>
              ) : undefined,
              props.row.abnormalAlertCount > 0 && !props.row.isInvalid ? (
                <span
                  class='alert-tag red'
                  v-bk-tooltips={{
                    placements: ['right'],
                    boundary: 'window',
                    content: `${this.$t('当前有{n}个未恢复事件', { n: props.row.abnormalAlertCount })}`,
                    allowHTML: false
                  }}
                  onClick={tsx.modifiers.stop(() => this.handleToEventCenter(props.row))}
                >
                  <i class='icon-monitor icon-mc-chart-alert'></i>
                  <span class='alert-count'>{props.row.abnormalAlertCount}</span>
                </span>
              ) : undefined,
              props.row.shieldAlertCount ? (
                <span
                  class='alert-tag grey'
                  v-bk-tooltips={{
                    placements: ['right'],
                    boundary: 'window',
                    content: `${this.$t('当前有{n}个已屏蔽事件', { n: props.row.shieldAlertCount })}`,
                    allowHTML: false
                  }}
                  onClick={tsx.modifiers.stop(() => this.handleToEventCenter(props.row, 'SHIELDED_ABNORMAL'))}
                >
                  <i class='icon-monitor icon-menu-shield'></i>
                  <span class='alert-count'>{props.row.shieldAlertCount}</span>
                </span>
              ) : undefined,
              props.row.shieldInfo?.shield_ids?.length ? (
                <span
                  class='alert-tag wuxian'
                  v-bk-tooltips={{
                    placements: ['right'],
                    boundary: 'window',
                    content: `${this.$t('整个策略已被屏蔽')}`
                  }}
                  onClick={() => this.handleToAlarmShield(props.row.shieldInfo.shield_ids)}
                >
                  <i class='icon-monitor icon-menu-shield'></i>
                  <SvgIcon
                    iconName={'wuqiong'}
                    class='wu-xian-text'
                  ></SvgIcon>
                </span>
              ) : undefined
            ]}
          </div>
          <div class='col-name-type'>{props.row.scenarioDisplayName}</div>
        </div>
      )
    };
    const itemDescriptionSlot = {
      default: props => (
        <span
          class='table-monitor-desc'
          v-bk-tooltips={{
            content: this.handleDescTips(props.row.itemDescription),
            delay: 200,
            boundary: 'window',
            allowHTML: true
          }}
        >
          {props.row.itemDescription.map((item, index) => [
            <span
              key={index}
              class='table-monitor-desc-item'
            >
              {index < 2 ? (
                <span
                  class='item-span'
                  style='white-space: nowrap;'
                >
                  {item.val}
                  {props.row.itemDescription.length > 2 && index > 0 ? <span>&nbsp;...</span> : undefined}
                </span>
              ) : undefined}
            </span>,
            index === 0 ? <br key={`br-${index}`}></br> : undefined
          ])}
        </span>
      )
    };
    const dataOriginSlot = {
      /* 数据来源 */ default: props => <span>{props.row.dataOrigin}</span>
    };
    const targetSlot = {
      default: props => (
        <div class='col-name'>
          <div class='col-name-label'>{props.row.target || this.$t('默认全部')}</div>
        </div>
      )
    };
    const overflowGroupDom = (props, type, customTip = '' /* 通用组样式 */) => (
      <div class='col-classifiy'>
        {props.row[type].length > 0 ? (
          <div
            class='col-classifiy-wrap'
            ref={`table-${type}-${props.$index}`}
            v-bk-tooltips={{
              placements: ['top-start'],
              boundary: 'window',
              content: () => customTip || props.row[type].join('、 '),
              delay: 200,
              allowHTML: false
            }}
          >
            {props.row[type].map((item, index) => (
              <span
                class='classifiy-label gray'
                key={`${item}-${index}`}
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
              class='col-classifiy-wrap'
              ref={`table-labels-${props.$index}`}
            >
              {props.row.labels.map((item, index) => (
                <span
                  class='classifiy-label gray'
                  v-bk-overflow-tips
                  key={`${item}-${index}`}
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
                    allowHTML: false
                  }}
                >
                  ...
                </span>
              ) : undefined}
            </div>
          ) : (
            <div>--</div>
          )}
        </div>
      )
    };
    const noticeGroupListSlot = {
      /* 告警组 */
      default: props => (
        <div class='col-classifiy'>
          <div
            class='col-classifiy-wrap'
            ref={`table-row-${props.$index}`}
            v-bk-tooltips={{
              placements: ['top-start'],
              boundary: 'window',
              content: () => props.row.noticeGroupNameList.join('、'),
              delay: 200,
              allowHTML: false
            }}
          >
            {props.row.noticeGroupNameList.map(item => (
              <span
                class='classifiy-label'
                key={item}
              >
                <span class='text-overflow'>{item}</span>
              </span>
            ))}
            {props.row.overflow ? <span class='classifiy-overflow'>...</span> : undefined}
          </div>
        </div>
      )
    };
    const signalsSlot = {
      /* 通知场景 */ default: props => overflowGroupDom(props, 'signals')
    };
    const levelsSlot = {
      /* 级别 */ default: props => overflowGroupDom(props, 'levels')
    };
    const detectionTypesSlot = {
      /* 检测规则类型 */ default: props => overflowGroupDom(props, 'detectionTypes')
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
      }
    };
    const updatorSlot = {
      /* 更新记录 */
      default: props => (
        <div class='col-name'>
          <div class='col-name-label'>{props.row.updator || '--'}</div>
          <div>{dayjs.tz(props.row.updateTime).format('YYYY-MM-DD HH:mm:ss') || '--'}</div>
        </div>
      )
    };
    const enabledDom = (props, type: 'enabled' | 'needPoll' | 'noDataEnabled' /* 通用开关样式 */) => (
      <div class='switch-wrap'>
        <bk-switcher
          key={props.row.id}
          v-model={props.row[type]}
          size='small'
          theme='primary'
          pre-check={() => this.handlePreSwitchChange(props.row, type)}
        ></bk-switcher>
        {!this.authority.MANAGE_AUTH ? (
          <div
            v-authority={{ active: !this.authority.MANAGE_AUTH }}
            class='switch-wrap-modal'
            onClick={(e: Event) => {
              e.stopPropagation();
              e.preventDefault();
              !this.authority.MANAGE_AUTH && this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH);
            }}
          ></div>
        ) : undefined}
      </div>
    );
    const enabledSlot = {
      /* 启停 */ default: props => enabledDom(props, 'enabled')
    };
    const needPollSlot = {
      /* 告警风暴 */ default: props => enabledDom(props, 'needPoll')
    };
    const noDataEnabledSlot = {
      /* 无数据启停 */ default: props => enabledDom(props, 'noDataEnabled')
    };
    const recoverySlot = {
      /* 恢复条件 */
      default: props => (
        <span
          v-bk-tooltips={{
            placements: ['top-start'],
            boundary: 'boundary',
            content: () => this.$t('连续{0}个周期内不满足条件表示恢复', [props.row.recovery]),
            disabled: props.row.recovery === '--' /* 兼容关联告警 */,
            delay: 200,
            allowHTML: false
          }}
        >
          {props.row.recovery}
        </span>
      )
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
                    props.row.triggerConfig.count
                  ])
                : '',
            disabled: !props.row.triggerConfig,
            delay: 200,
            allowHTML: false
          }}
        >
          {props.row.trigger}
        </span>
      )
    };
    const configSourceSlot = {
      /* 配置来源 */ default: props => props.row.configSource || '--'
    };
    const appSlot = {
      /* 配置分组 */ default: props => props.row.app || '--'
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
              disabled: props.row.editAllowed
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
            onClick={event =>
              this.authority.MANAGE_AUTH
                ? this.handleOperatorOver(props.row, event, props.$index)
                : this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH)
            }
            v-authority={{ active: !this.authority.MANAGE_AUTH }}
            data-popover='true'
          >
            <i
              data-popover='true'
              class='bk-icon icon-more'
            ></i>
          </span>
        </div>
      )
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
      app
    } = this.fieldSettingData;
    return (
      <bk-table
        class='strategy-table'
        empty-text={this.$t('无数据')}
        v-bkloading={{ isLoading: this.table.loading }}
        on-selection-change={this.handleSelectionChange}
        on-header-dragend={this.handleHeaderDragend}
        ref='strategyTable'
        on={{
          'hook:mounted': this.handleTableMountedOrActivated,
          'hook:activated': this.handleTableMountedOrActivated
        }}
        {...{
          props: {
            data: this.table.data
          }
        }}
      >
        <div slot='empty'>
          <EmptyStatus
            type={this.emptyType}
            onOperation={this.handleOperation}
          />
        </div>
        <bk-table-column
          type='selection'
          align='center'
          width='50'
        ></bk-table-column>
        {id.checked && (
          <bk-table-column
            label='ID'
            prop='id'
            width='75'
            scopedSlots={idSlot}
            key='id'
          ></bk-table-column>
        )}
        {strategyName.checked && (
          <bk-table-column
            label={this.$t('策略名')}
            min-width='200'
            scopedSlots={strategyNameSlot}
            key='strategyName'
          ></bk-table-column>
        )}
        {itemDescription.checked && (
          <bk-table-column
            label={this.$t('监控项')}
            min-width='200'
            scopedSlots={itemDescriptionSlot}
            key='itemDescription'
          ></bk-table-column>
        )}
        {dataOrigin.checked && (
          <bk-table-column
            label={this.$t('数据来源')}
            width='110'
            scopedSlots={dataOriginSlot}
            key='dataOrigin'
          ></bk-table-column>
        )}
        {target.checked && (
          <bk-table-column
            label={this.$t('监控目标')}
            width='150'
            scopedSlots={targetSlot}
            key='target'
          ></bk-table-column>
        )}
        {labels.checked && (
          <bk-table-column
            label={this.$t('标签')}
            scopedSlots={labelsSlot}
            key='labels'
          ></bk-table-column>
        )}
        {noticeGroupList.checked && (
          <bk-table-column
            label={this.$t('告警组')}
            scopedSlots={noticeGroupListSlot}
            key='noticeGroupList'
          ></bk-table-column>
        )}
        {updator.checked && (
          <bk-table-column
            label={this.$t('更新记录')}
            width='150'
            scopedSlots={updatorSlot}
            key='updator'
          ></bk-table-column>
        )}
        {enabled.checked && (
          <bk-table-column
            label={this.$t('启/停')}
            width='100'
            scopedSlots={enabledSlot}
            key='enabled'
          ></bk-table-column>
        )}
        {dataTypeLabelName.checked && (
          <bk-table-column
            label={this.$t('策略类型')}
            width='80'
            scopedSlots={{ default: props => props.row.dataTypeLabelName }}
            key='dataTypeLabelName'
          ></bk-table-column>
        )}
        {intervalNotifyMode.checked && (
          <bk-table-column
            label={this.$t('通知间隔类型')}
            width='105'
            scopedSlots={{ default: props => props.row.intervalNotifyMode }}
            key='intervalNotifyMode'
          ></bk-table-column>
        )}
        {dataMode.checked && (
          <bk-table-column
            label={this.$t('查询类型')}
            width='105'
            scopedSlots={{ default: props => props.row.dataMode }}
            key='dataMode'
          ></bk-table-column>
        )}
        {notifyInterval.checked && (
          <bk-table-column
            label={this.$t('通知间隔')}
            width='105'
            scopedSlots={{ default: props => `${props.row.notifyInterval}${this.$t('分钟')}` }}
            key='notifyInterval'
          ></bk-table-column>
        )}
        {trigger.checked && (
          <bk-table-column
            label={this.$t('触发条件')}
            width='105'
            scopedSlots={triggerSlot}
            key='trigger'
          ></bk-table-column>
        )}
        {recovery.checked && (
          <bk-table-column
            label={this.$t('恢复条件')}
            width='105'
            scopedSlots={recoverySlot}
            key='recovery'
          ></bk-table-column>
        )}
        {needPoll.checked && (
          <bk-table-column
            label={this.$t('告警风暴')}
            width='80'
            scopedSlots={needPollSlot}
            key='needPoll'
          ></bk-table-column>
        )}
        {noDataEnabled.checked && (
          <bk-table-column
            label={this.$t('无数据')}
            width='80'
            scopedSlots={noDataEnabledSlot}
            key='noDataEnabled'
          ></bk-table-column>
        )}
        {signals.checked && (
          <bk-table-column
            label={this.$t('通知场景')}
            width='150'
            scopedSlots={signalsSlot}
            key='signals'
          ></bk-table-column>
        )}
        {levels.checked && (
          <bk-table-column
            label={this.$t('级别')}
            width='150'
            scopedSlots={levelsSlot}
            key='levels'
          ></bk-table-column>
        )}
        {detectionTypes.checked && (
          <bk-table-column
            label={this.$t('检测规则类型')}
            width='150'
            scopedSlots={detectionTypesSlot}
            key='detectionTypes'
          ></bk-table-column>
        )}
        {mealNames.checked && (
          <bk-table-column
            label={this.$t('处理套餐')}
            width='150'
            scopedSlots={mealNamesSlot}
            key='mealNames'
          ></bk-table-column>
        )}
        {configSource.checked && (
          <bk-table-column
            label={this.$t('配置来源')}
            width='100'
            scopedSlots={configSourceSlot}
            key='configSource'
          ></bk-table-column>
        )}
        {app.checked && (
          <bk-table-column
            label={this.$t('配置分组')}
            width='100'
            scopedSlots={appSlot}
            key='app'
          ></bk-table-column>
        )}
        {operator.checked && (
          <bk-table-column
            label={this.$t('操作')}
            width={this.$store.getters.lang === 'en' ? 220 : 150}
            scopedSlots={operatorSlot}
            key='operator'
          ></bk-table-column>
        )}
      </bk-table>
    );
  }

  getDialogComponent() {
    return [
      <div style='display: none;'>
        <ul
          class='operator-group'
          ref='operatorGroup'
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
              disabled: this.popover.data.editAllowed
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
        loading={this.dialogLoading}
        checked-list={this.idList}
        group-list={this.groupList}
        dialog-show={this.dialog.show}
        set-type={this.header.value}
        onGetGroupList={this.getGroupList}
        onConfirm={this.handleMuchEdit}
        onHideDialog={this.handleDialogChange}
      ></StrategyConfigDialog>,
      <AlarmShieldStrategy
        is-show-strategy={this.isShowStrategy}
        {...{ on: { 'update:isShowStrategy': val => (this.isShowStrategy = val) } }}
        strategy-id={this.strategyId}
      ></AlarmShieldStrategy>,
      <TableFilter
        filter-type={this.filterType}
        show={this.isShowTableFilter}
        target={this.label.target}
        menu-list={this.dataSourceList}
        radio-list={this.dataSourceList}
        value={this.label.value}
        on-selected={this.handleSelectedDataSource}
        on-hide={this.handleChangeValue}
        on-confirm={this.handleFilterDataSourece}
        on-reset={() => this.handleResetSourceFilter(true)}
      ></TableFilter>,
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
        showDialog={this.targetSet.show}
        strategyIds={this.targetSet.strategyIds}
        objectType={this.targetSet.objectType as TargetObjectType}
        nodeType={this.targetSet.nodeType as INodeType}
        bizId={this.targetSet.bizId}
        onSave={this.handleTargetSaveChange}
        onCloseDialog={this.handleTargetShowChange}
      />
    ];
  }

  render() {
    return (
      <div
        class='strategy-config'
        v-monitor-loading={{ isLoading: this.loading }}
      >
        <div class='content'>
          <div
            class={['content-left', { displaynone: !this.showFilterPanel }]}
            style={{ flexBasis: `${this.drapWidth}px`, width: `${this.drapWidth}px` }}
            data-tag='resizeTarget'
            v-show='showFilterPanel'
          >
            <FilterPanel
              class='content-left-filter'
              show={this.showFilterPanel}
              {...{ on: { 'update:show': val => (this.showFilterPanel = val) } }}
              data={this.filterPanelData}
              checkedData={this.header.keywordObj}
              on-change={this.handleSearchSelectChange}
            ></FilterPanel>
            <div
              class={['content-left-drag', { displaynone: !this.showFilterPanel }]}
              onMousedown={this.handleMouseDown}
              onMousemove={this.handleMouseMove}
            ></div>
          </div>
          <div
            id='content-for-watch-resize'
            class='content-right'
          >
            <div class='strategy-config-header'>
              <bk-badge
                class='badge'
                dot
                theme='success'
                visible={this.header.keywordObj.length !== 0}
                v-show={!this.showFilterPanel}
              >
                <span
                  class='folding'
                  onClick={this.handleShowFilterPanel}
                >
                  <i class='icon-monitor icon-double-up'></i>
                </span>
              </bk-badge>
              <bk-button
                class='header-btn mc-btn-add'
                theme='primary'
                v-authority={{ active: !this.authority.MANAGE_AUTH }}
                onClick={() =>
                  this.authority.MANAGE_AUTH
                    ? this.handleAddStategyConfig()
                    : this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH)
                }
              >
                <span class='icon-monitor icon-plus-line mr-6'></span>
                {this.$t('新建')}
              </bk-button>
              <bk-dropdown-menu
                class='header-select'
                on-show={() => (this.header.dropdownShow = true)}
                on-hide={() => (this.header.dropdownShow = false)}
                disabled={!this.table.select.length}
                trigger='click'
              >
                <div
                  slot='dropdown-trigger'
                  class={['header-select-btn', { 'btn-disabled': !this.table.select.length }]}
                >
                  <span class='btn-name'> {this.$t('批量操作')} </span>
                  <i class={['icon-monitor', this.header.dropdownShow ? 'icon-arrow-up' : 'icon-arrow-down']}></i>
                </div>
                <ul
                  v-authority={{
                    active: !this.authority.MANAGE_AUTH
                  }}
                  class='header-select-list'
                  slot='dropdown-content'
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
                        allowHTML: false
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
              <bk-search-select
                class='header-search'
                v-model={this.header.keywordObj}
                show-condition={false}
                data={this.conditionListFilter()}
                filter={true}
                placeholder={this.$t('任务ID / 告警组名称 / IP / 指标ID')}
                on-change={this.header.handleSearch}
                on-clear={this.header.handleSearch}
                clearable
              ></bk-search-select>
            </div>
            <div class='strategy-config-wrap'>
              <div class='config-wrap-setting'>
                <bk-popover
                  placement='bottom'
                  width='515'
                  theme='light strategy-setting'
                  trigger='click'
                  offset='0, 20'
                  ext-cls='strategy-table-setting'
                >
                  <div class='setting-btn'>
                    <i class='icon-monitor icon-menu-set'></i>
                  </div>
                  <div
                    slot='content'
                    class='tool-popover'
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
                            value={this.fieldSettingData[key].checked}
                            onChange={() => this.handleCheckColChange(this.fieldSettingData[key])}
                            disabled={this.fieldSettingData[key].disable}
                          >
                            {this.fieldSettingData[key].name}
                          </bk-checkbox>
                        </li>
                      ))}
                    </ul>
                  </div>
                </bk-popover>
              </div>
              {this.getTableComponent()}
              {this.table.data?.length ? (
                <bk-pagination
                  v-show={this.tableInstance.total}
                  class='strategy-pagination list-pagination'
                  align='right'
                  size='small'
                  pagination-able
                  current={this.tableInstance.page}
                  limit={this.tableInstance.pageSize}
                  count={this.pageCount}
                  limit-list={this.tableInstance.pageList}
                  on-change={this.handlePageChange}
                  on-limit-change={this.handleLimitChange}
                  show-total-count
                ></bk-pagination>
              ) : undefined}
            </div>
          </div>
        </div>
        {this.getDialogComponent()}
      </div>
    );
  }
}

export default tsx.ofType<IStrategyConfigProps>().convert(StrategyConfig);
