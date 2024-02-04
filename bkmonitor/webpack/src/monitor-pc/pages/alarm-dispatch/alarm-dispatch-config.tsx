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
import { Component, Inject, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { listActionConfig, listAssignGroup, listAssignRule, listUserGroup } from '../../../monitor-api/modules/model';
import { getCookie, random, transformDataKey } from '../../../monitor-common/utils';
import { deepClone } from '../../../monitor-common/utils/utils';
import MonitorImport from '../../../monitor-pc/components/monitor-import/monitor-import.vue';
import { Debounce } from '../../components/ip-selector/common/util';
import { getEventPaths } from '../../utils';
import AlarmGroupDetail from '../alarm-group/alarm-group-detail/alarm-group-detail';
import { csvToArr } from '../custom-escalation/utils';
import { downCsvFile } from '../view-detail/utils';

import AlarmBatchEdit from './components/alarm-batch-edit';
import AlarmGroupSelect from './components/alarm-group-select';
import CommonCondition from './components/common-condition-new';
import DebuggingResult, { IRuleGroupsDataItem } from './components/debugging-result';
import {
  allKVOptions,
  GROUP_KEYS,
  ISpecialOptions,
  setDimensionsOfStrategy,
  statisticsSameConditions,
  TGroupKeys,
  TValueMap
} from './typing/condition';
import { ActionType, deepCompare, EColumn, ICondtionItem, LEVELLIST, RuleData } from './typing';

import './alarm-dispatch-config.scss';

/* 流程展示 */
const processList = [
  { index: 1, colspan: 2, text: window.i18n.tc('分派给谁'), bg: '#CCDEFA' },
  { index: 2, colspan: 1, text: window.i18n.tc('匹配哪些告警规则'), bg: '#D9E6FA', arrow: '#BCD6FD' },
  {
    index: 3,
    colspan: 2,
    text: window.i18n.tc('如何执行分派'),
    bg: '#E1E9FB',
    arrow: '#CADCFA',
    merge: 'noticeProgress'
  },
  { index: 4, colspan: 2, text: window.i18n.tc('修改原告警内容'), bg: '#F0F5FF', arrow: '#D7E6FE', merge: 'levelTag' },
  { colspan: 2, bg: '#F6FAFF', arrow: '#E7EEFD' }
];

/* 包含批量操作的列 */
const hasBatchColumn = [
  EColumn.userGroups,
  EColumn.conditions,
  EColumn.actionId,
  EColumn.upgradeConfig,
  EColumn.alertSeverity,
  EColumn.additionalTags,
  EColumn.isEnabled
];

interface ITableColumn {
  id: EColumn;
  content?: any;
  class?: string;
  width?: number;
  show?: boolean;
}

type FiledType = EColumn | 'priority' | 'name' | 'notice' | 'alertSeveritySingle';
type MergeColumn = 'noticeProgress' | 'levelTag';

@Component
export default class AlarmDispatchConfig extends tsc<{}> {
  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;

  @Ref('unifiedSettings') unifiedSettingsRef: HTMLDivElement;
  @Ref('unifiedSettingBtn') unifiedSettingBtnRef: HTMLDivElement;
  /* 表格字段 */
  tableColumns: ITableColumn[] = [];
  /* 表格数据 */
  tableData: RuleData[] = [];
  cacheTableData: RuleData[] = [];
  ruleGroupData = {
    name: '',
    priority: 0,
    bk_biz_id: 0,
    id: 0,
    settings: {}
  };

  /* 全选/半选 */
  isCheckAll = false;
  indeterminate = false;
  loading = false;
  processLoading = false;

  filed: FiledType = null;
  showSideliner = false;
  dataSource = null;
  popoverInstance = null;
  currentFiledElement = null;
  secondPopover = null;
  tableScrollTop = 0;

  /** 优先级列表 */
  priorityList: number[] = [];

  /** 禁用高级组列表 */
  alarmDisabledList: number[] = [];

  /** 空组状态 */
  isInitialRule = false;

  /** 生效 */
  isEffect = false;
  /** 告警组信息弹窗 */
  alarmGroupDetail = {
    id: 0,
    show: false
  };

  /** 告警组 */
  currentIndex = 0;
  alarmGroupList = [];
  /* 告警组列表loading */
  alarmGroupListLoading = false;
  /* 流程套餐*/
  processPackage = [];
  /* 流程展示 */
  processList = deepClone(processList);

  /* kv 选项数据 */
  kvOptionsData: {
    keys: { id: string; name: string }[];
    valueMap: TValueMap;
    groupKeys: TGroupKeys;
    specialOptions: ISpecialOptions;
  } = {
    keys: [],
    valueMap: new Map(),
    groupKeys: new Map(),
    specialOptions: {}
  };

  /* 调试数据，此数据传与后台用于调试与保存 */
  debugData: IRuleGroupsDataItem[] = [];

  /* 统一设置数据 */
  unifiedSettings = {
    conditions: [], // 以匹配的条件
    targetConditions: [], // 统一设置面板的编辑数据
    popInstance: null,
    conditionsSelectorKey: random(8),
    isConditionChange: false // 弹出层是否有condition变更触发
  };

  conditionsLoading = false;

  /* 撤回配置 */
  resetConfig = {};

  /* 列合并配置 */
  mergeConfig = {
    noticeProgress: false, // 通知流程是否合并
    levelTag: false // 等级追加标签是否合并
  };

  /* 批量删除、撤回tips disabled */
  batchTipsDisabled = false;

  editAllowed = true;

  /* 是否可调试 */
  get canDebug() {
    return (
      this.tableData.every(item => item.isVerifySuccess) &&
      !(this.tableData.length <= 1 && !!this.tableData[0]?.isNullData)
    );
  }

  /* 判断规则是否发生变化 */
  get isRuleChange() {
    if (this.tableData.length !== this.cacheTableData.length) return true;
    return Object.values(this.resetConfig).some((item: { disabled: boolean; cacheData: RuleData }) => !item.disabled);
  }

  created() {
    this.init();
    this.getKVOptionsData();
    this.getAlarmGroupList();
    this.getProcessPackage();
    this.getAlarmDispatchGroupData();
    this.getAlarmAssignGroupsRules();
    this.$store.commit('app/SET_NAV_ROUTE_LIST', [{ name: this.$t('route-配置规则'), id: '' }]);
  }

  init() {
    this.tableColumnsInit();
  }

  beforeDestroy() {
    this.popoverInstance && this.removePopoverInstance();
    this.handleCancelUnifiedSettings();
  }

  @Watch('tableData', { deep: true })
  handleTableDataChange(value: RuleData[]) {
    value.forEach((item, index) => {
      // DB现有的规则
      const ruleData = this.cacheTableData.find(config => config.id === item.id && item.id !== 0);
      if (ruleData) {
        this.handleDiffRuleData(ruleData, item, index);
      } else {
        // 新增的规则
        const addRuleData = this.cacheTableData.find(config => config.addId === item.addId);
        if (addRuleData) {
          this.handleDiffRuleData(addRuleData, item, index);
        } else {
          // 复制的规则
          const copyRuleData = this.cacheTableData.find(config => config.copyId === item.copyId);
          if (copyRuleData) {
            this.handleDiffRuleData(copyRuleData, item, index);
          }
        }
      }
    });
  }

  /** 规则对比 */
  handleDiffRuleData(data1: RuleData, data2: RuleData, index: number) {
    const fieldList = ['userGroups', 'conditions', 'actions', 'alertSeverity', 'additionalTags', 'isEnabled'];
    const newRleData = {};
    const newItem = {};
    fieldList.forEach(field => {
      if (field === 'additionalTags') {
        newRleData[field] = data1[field].map(tag => ({ key: tag.key, value: tag.value }));
        newItem[field] = data2[field].map(tag => ({ key: tag.key, value: tag.value }));
      } else if (field === 'actions') {
        newRleData[field] = data1[field].filter(item => {
          if (item.actionType === 'itsm') {
            return item.actionId;
          }
          return !!item.upgradeConfig?.isEnabled;
        });

        newItem[field] = data2[field].filter(item => {
          if (item.actionType === 'itsm') {
            return item.actionId;
          }
          return !!item.upgradeConfig?.isEnabled;
        });
      } else {
        newRleData[field] = data1[field];
        newItem[field] = data2[field];
      }
    });
    const result = deepCompare(newRleData, newItem);

    if (result) {
      this.resetConfig[index] = { disabled: true, cacheData: deepClone(data1) };
    } else {
      this.resetConfig[index] = { disabled: false, cacheData: deepClone(data1) };
    }
  }

  /**
   * 获取告警分派分组数据
   */
  async getAlarmDispatchGroupData() {
    this.loading = true;
    const { id } = this.$route.params;
    const list = await listAssignGroup().catch(() => {
      this.loading = false;
      return [];
    });
    this.loading = false;
    const targetRuleGroup = list.find(item => item.id === Number(id));
    this.priorityList = list.map(item => item.priority);
    if (targetRuleGroup) {
      this.ruleGroupData = targetRuleGroup;
      this.editAllowed = !!targetRuleGroup?.edit_allowed;
    }
  }

  /**
   *  获取规则
   * @param ruleGroup
   */
  async getAlarmAssignGroupsRules() {
    const { id } = this.$route.params;
    const list = await listAssignRule({ assign_group_id: id }).catch(() => []);
    this.loading = false;
    this.tableData =
      list.length > 0
        ? list.map(item => new RuleData({ ...transformDataKey(item, false) }))
        : [new RuleData({ addId: random(8), isEnabled: true })];
    if (!list.length) {
      this.mergeConfig = {
        noticeProgress: true,
        levelTag: true
      };
      this.$set(this.processList[2], 'colspan', 1);
      this.$set(this.processList[3], 'colspan', 1);
      this.tableColumnsInit();
    }

    this.cacheTableData = deepClone(this.tableData);
    this.isInitialRule = !list.length;
    /* 根据策略获取维度选项 */
    const strategyIdSet = new Set();
    const strategyIdKey = 'alert.strategy_id';
    this.tableData.forEach(item => {
      this.validateAlarmGroup(item);
      item.conditions.forEach(c => {
        if (c.field === strategyIdKey) {
          c.value.forEach(v => {
            if (!!v) {
              strategyIdSet.add(v);
            }
          });
        }
      });
    });
    this.unifiedSettingInit();
    this.setDimensionsInfo(strategyIdSet);
  }

  // 获取流程套餐
  async getProcessPackage() {
    this.processLoading = true;
    const data = await listActionConfig().catch(() => []);
    this.processPackage = data.filter(item => item.plugin_type === 'itsm');
    this.processLoading = false;
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

  /* 刷新告警组列表 */
  async handleRefreshAlarmGroup() {
    this.alarmGroupListLoading = true;
    await this.getAlarmGroupList();
    this.alarmGroupListLoading = false;
  }

  /* 初始化表头 */
  tableColumnsInit() {
    const selectDom = () => (
      <div class='table-column-item select-all'>
        <bk-checkbox
          v-model={this.isCheckAll}
          indeterminate={this.indeterminate}
          onChange={this.handleCheckAllChange}
        ></bk-checkbox>
      </div>
    );
    const alarmGroupDom = () => <div class='table-column-item'>{this.$t('告警组')}</div>;
    const matchRuleDom = () => (
      <div class='table-column-item'>
        <span>{this.$t('匹配规则')}</span>
        {
          <span
            class='unified-setting'
            ref='unifiedSettingBtn'
            onClick={() => this.handleClickUnifiedSetting()}
          >
            {/* <span class="icon-monitor "></span> */}
            {!!this.unifiedSettings.conditions.filter(item => !!item.field).length ? (
              <i18n path='已设置{0}个条件'>
                <span>{this.unifiedSettings.conditions.length}</span>
              </i18n>
            ) : (
              <span>{this.$t('统一设置')}</span>
            )}
          </span>
        }
      </div>
    );
    const noticeDom = () => <div class='table-column-item'>{this.$t('通知升级')}</div>;
    const actionConfigDom = () => <div class='table-column-item'>{this.$t('流程')}</div>;
    const levelDom = () => <div class='table-column-item'>{this.$t('等级调整')}</div>;
    const tagDom = () => <div class='table-column-item'>{this.$t('追加标签')}</div>;
    const enableDom = () => <div class='table-column-item'>{this.$t('状态')}</div>;
    const operateDom = () => <div class='table-column-item'></div>;
    const noticeProgress = () => <div class='table-column-item'>{this.$t('通知 & 流程')}</div>;
    const levelTag = () => <div class='table-column-item'>{this.$t('等级 & 标签')}</div>;

    this.tableColumns = [
      { id: EColumn.select, content: selectDom, class: 'select-all-th', width: 52, show: true },
      { id: EColumn.userGroups, content: alarmGroupDom, class: 'alarm-group-th', width: 180, show: true },
      { id: EColumn.conditions, content: matchRuleDom, class: 'match-rule-th', show: true },
      {
        id: EColumn.noticeProgress,
        content: noticeProgress,
        class: 'notice-config-th',
        width: 120,
        show: this.mergeConfig.noticeProgress
      },
      {
        id: EColumn.upgradeConfig,
        content: noticeDom,
        class: 'notice-config-th',
        width: 180,
        show: !this.mergeConfig.noticeProgress
      },
      {
        id: EColumn.actionId,
        content: actionConfigDom,
        class: 'progress-action-th',
        width: 120,
        show: !this.mergeConfig.noticeProgress
      },
      {
        id: EColumn.levelTag,
        content: levelTag,
        class: 'notice-config-th',
        width: 130,
        show: this.mergeConfig.levelTag
      },
      {
        id: EColumn.alertSeverity,
        content: levelDom,
        class: 'select-level-th',
        width: 88,
        show: !this.mergeConfig.levelTag
      },
      {
        id: EColumn.additionalTags,
        content: tagDom,
        class: 'additional-tag-th',
        width: 200,
        show: !this.mergeConfig.levelTag
      },
      { id: EColumn.isEnabled, content: enableDom, class: 'enable-th', width: 64, show: true },
      { id: EColumn.operate, content: operateDom, class: 'operate-th', width: 144, show: true }
    ];
  }

  handleSelcetAlarmGroup(id: number) {
    this.alarmGroupDetail.id = id;
    this.alarmGroupDetail.show = true;
  }

  /**
   * 全选处理
   * @param value
   */
  handleCheckAllChange(value: boolean) {
    this.isCheckAll = value;
    this.indeterminate = false;
    this.tableData.forEach(item => item.setCheck(value));
    this.batchTipsDisabled = false;
  }

  /**
   * 单选处理
   */
  handleCheckChange() {
    if (this.tableData.every(item => item.isCheck)) {
      this.isCheckAll = true;
      this.indeterminate = false;
    } else if (this.tableData.some(item => item.isCheck)) {
      this.isCheckAll = false;
      this.indeterminate = true;
    } else {
      this.isCheckAll = false;
      this.indeterminate = false;
    }
    this.batchTipsDisabled = false;
    this.init();
  }

  /**
   * 操作处理
   * @param index 下标
   * @param action
   */
  handleOperateAction(action: ActionType, index?: number) {
    const cacheRule = index ? this.resetConfig[index].cacheData : new RuleData(null);
    switch (action) {
      case 'copy':
        this.tableData.splice(index, 0, deepClone(this.tableData[index]));
        this.tableData[index + 1].id = undefined;
        this.tableData[index + 1].setCopyID();
        break;
      case 'add':
        this.tableData.splice(
          index + 1,
          0,
          new RuleData({
            addId: random(8),
            conditions: deepClone(this.unifiedSettings.conditions),
            isEnabled: true
          })
        );
        break;
      case 'delete':
        // 当剩一个规则时, 也支持删除 这里删除的意思 回到空组时的初始状态
        if (this.tableData.length === 1) {
          this.tableData.splice(index, 1, new RuleData({ addId: random(8), isEnabled: true }));
          this.isInitialRule = true;
        } else {
          this.tableData.splice(index, 1);
        }
        break;
      case 'reset':
        this.tableData.splice(index, 1, cacheRule ? cacheRule : new RuleData(null));
        break;
      case 'batchDelete':
        this.tableData = this.tableData.filter(item => !item.isCheck);
        // 如果全部删除 回到空组时的初始状态
        if (!this.tableData.length) {
          this.tableData.splice(index, 1, new RuleData({ addId: random(8), isEnabled: true }));
        }
        // 重新计算全选状态
        this.handleCheckChange();
        break;
      case 'batchReset':
        this.tableData = this.tableData.map((item, num) => {
          if (item.isCheck) {
            return this.resetConfig[num].cacheData;
          }
          return item;
        });
        break;
      default:
        break;
    }
  }

  /**
   * 批量编辑 popover
   * @param e
   * @param id
   */
  handleBatchEdit(e: Event, id: FiledType) {
    // const path = getEventPaths(e, 'td');
    this.removePopoverInstance();
    this.filed = id;
    this.currentFiledElement = e.target;
    // path.length && !['name', 'priority'].includes(id) ? path[0] :
    this.popoverInstance = this.$bkPopover(e.target, {
      content: (this.$refs.alarmBatchEdit as any).$el,
      trigger: 'click',
      arrow: true,
      hideOnClick: false,
      boundary: 'window',
      placement: 'bottom-start',
      theme: 'light common-monitor',
      zIndex: 2000,
      // distance: ['name', 'priority'].includes(id) ? 10 : 15,
      offset: ['name', 'priority'].includes(id) ? '0, 0' : '-15, 7',
      onShow: () => {
        document.addEventListener('click', this.handleClickOutSide, false);
      },
      onHide: () => {
        document.removeEventListener('click', this.handleClickOutSide, false);
      }
    });
    this.popoverInstance?.show(100);
  }

  handleClickOutSide(e: Event) {
    const targetEl = e.target as HTMLBaseElement;
    if (targetEl === this.currentFiledElement) return;
    // 点击区域在当前一层弹层内
    if (this.popoverInstance) {
      const result = this.popoverInstance.popper.contains(targetEl);
      if (result) {
        this.secondPopover = null;
        return;
      }
      // 判断点击区域是否在二次弹层内
      const path = getEventPaths(e);
      const tippyPopper = path.find(item => item.className === 'tippy-popper');
      if (tippyPopper) {
        setTimeout(() => {
          // 判断二次弹层是单选还是多选操作
          const list = document.getElementsByClassName('tippy-popper');
          // eslint-disable-next-line @typescript-eslint/prefer-for-of
          for (let i = 0; i < list.length; i++) {
            // 多选 保存二次弹层
            if (list[i] === tippyPopper) {
              this.secondPopover = tippyPopper;
              return;
            }
            this.secondPopover = null;
          }
        }, 350);
        return;
      }
      if (this.secondPopover) {
        this.secondPopover = null;
        return;
      }
      /* 侧栏关闭不能影响弹层 */
      const classNameList = getEventPaths(e).map(item => item.className);
      if (classNameList.some(c => c?.indexOf?.('bk-sideslider') >= 0)) {
        return;
      }
      const list1 = document.getElementsByClassName('tippy-popper');

      list1.length <= 1 && this.removePopoverInstance();
    }
  }

  handleShowChange(value: boolean) {
    this.showSideliner = value;
  }

  /* 清空pop */
  removePopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
    this.currentFiledElement = null;
    this.dataSource = null;
    this.alarmDisabledList = [];
    this.secondPopover = null;
    this.filed = null;
  }

  /**
   *  批量编辑确认
   * @param value
   */
  async handleBatchEditSubmit(value) {
    switch (this.filed) {
      case 'name':
      case 'priority':
        this.ruleGroupData[this.filed as string] = value;
        this.handleStartDebug();
        break;
      case 'actionId':
      case 'userGroups':
      case 'alertSeverity':
      case 'upgradeConfig':
        this.tableData = this.tableData.map((item, index) => {
          if (item.isCheck) {
            item[this.filed] = value;
            if (['upgradeConfig', 'alertSeverity'].includes(this.filed)) {
              if (this.filed === 'upgradeConfig') {
                item.setActions(value, 'notice');
                this.validateAlarmGroup(item);
              }
              this.handleDiffRuleItemChange(item, this.filed, index);
            }
            if (this.filed === 'userGroups') this.validateAlarmGroup(item);
          }
          return item;
        });
        break;
      case 'alertSeveritySingle':
        this.tableData[this.currentIndex].alertSeverity = value;
        this.handleDiffRuleItemChange(this.tableData[this.currentIndex], 'alertSeverity', this.currentIndex);
        this.filed = null;
        break;
      case 'additionalTags':
        this.tableData = this.tableData.map((item, index) => {
          if (item.isCheck) {
            item.tag = value;
            item.setAdditionalTags(value);
            this.handleDiffRuleItemChange(item, 'additionalTags', index);
          }
          return item;
        });
        break;
      case 'notice':
        this.tableData[this.currentIndex].setActions(value, 'notice');
        this.handleDiffRuleItemChange(this.tableData[this.currentIndex], 'upgradeConfig', this.currentIndex);
        this.validateAlarmGroup(this.tableData[this.currentIndex]);
        this.filed = null;
        break;

      case 'isEnabled':
        this.tableData = this.tableData.map((item, index) => {
          if (item.isCheck) {
            item.setIsEnabled(value);
            this.handleDiffRuleItemChange(item, 'isEnabled', index);
          }
          return item;
        });
      default:
        break;
    }
    this.filed = null;
    this.dataSource = null;
  }

  getAlarmGroupNames(id: number) {
    return this.alarmGroupList.find(item => item.id === id)?.name || id;
  }

  /** 编辑通知 */
  handleNoticeEdit(e: Event, filed: FiledType, index: number, groups: number[], config?: any) {
    this.handleBatchEdit(e, filed);
    // 回填
    this.dataSource = config
      ? deepClone(config)
      : {
          isEnabled: false,
          userGroups: [],
          upgradeInterval: 30
        };
    this.currentIndex = index;
    // 升级的告警组应不允许和原告警组相同
    this.alarmDisabledList = groups;
  }

  /* 匹配规则key对应的value值获取 */
  async getKVOptionsData() {
    this.conditionsLoading = true;
    allKVOptions(
      [this.$store.getters.bizId],
      (type: string, key: string, values: any) => {
        if (!!key) {
          (this.kvOptionsData[type] as Map<string, any>).set(key, values);
        } else {
          this.kvOptionsData[type] = values;
        }
      },
      () => {
        this.tableData.forEach(item => {
          if (item.conditions.length) {
            item.conditionsRefresh();
          }
        });
        this.conditionsLoading = false;
      }
    );
  }
  handleConditionChange(v, index: number) {
    this.tableData[index].setConditions(v);
    this.handleDiffRuleItemChange(this.tableData[index], 'conditions', index);
    this.getStrategyDimensionsAndValues(v);
    this.handleClickUnifiedSetting(true);
  }
  /* 查找是否选择策略并且根据策略id获取维度及维度值 */
  @Debounce(300)
  getStrategyDimensionsAndValues(conditions: ICondtionItem[]) {
    const strategyIdKey = 'alert.strategy_id';
    const strategyIdSet = new Set();
    conditions.forEach(item => {
      if (item.field === strategyIdKey) {
        item.value.forEach(v => {
          if (!!v) {
            strategyIdSet.add(v);
          }
        });
      }
    });
    // specialOptions
    this.setDimensionsInfo(strategyIdSet);
  }
  /**
   *
   * @param strategyIdSet 策略id集合
   */
  setDimensionsInfo(strategyIdSet: Set<any>) {
    const strategyIdKey = 'alert.strategy_id';
    const curDimension = this.kvOptionsData.groupKeys.get('dimensions') || [];
    const keySet = new Set();
    curDimension.forEach((d: any) => {
      keySet.add(d.id);
    });
    Array.from(strategyIdSet).forEach(id => {
      const key = `${strategyIdKey}=${id}`;
      if (!this.kvOptionsData.specialOptions[key]) {
        setDimensionsOfStrategy(id, valuesMap => {
          this.kvOptionsData.specialOptions[key] = valuesMap;
          for (const [tempKey, tempValue] of valuesMap) {
            this.kvOptionsData.valueMap.set(tempKey, tempValue);
            if (!keySet.has(tempKey)) {
              keySet.add(tempKey);
            }
          }
          this.kvOptionsData.groupKeys.set(
            'dimensions',
            [...keySet].map(k => ({ id: k, name: k }))
          );
        });
      }
    });
  }

  /* 调试并生效 */
  async handleStartDebug() {
    const result = this.tableData.every((item, index) => {
      const tag = item.additionalTags.map(item => (item.value ? `${item.key}:${item.value}` : item.key));
      const verify = !item.debugVerificatory();
      return this.handleAdditionalTagsChange(tag, item, index) && verify;
    });
    if (!result) return;
    this.debugData = [
      {
        bk_biz_id: this.ruleGroupData.bk_biz_id,
        assign_group_id: this.ruleGroupData.id,
        priority: this.ruleGroupData.priority,
        group_name: this.ruleGroupData.name,
        rules: this.tableData.filter(item => !item.isNullData).map(item => item.getSubmitParams()),
        settings: {
          public_conditions: !!this.unifiedSettings.conditions?.length
        }
      }
    ];
    this.showSideliner = true;
  }

  /** 导出 */
  handleExportChange() {
    const transformTableDataToCsvStr = (tableThArr: string[], tableTdArr: Array<string[]>): string => {
      const csvList: string[] = [tableThArr.join(',')];
      tableTdArr.forEach(row => {
        const rowString = row.reduce((str, item, index) => str + (!!index ? ',' : '') + item, '');
        csvList.push(rowString);
      });
      const csvString = csvList.join('\n');
      return csvString;
    };
    const thArr = [
      window.i18n.tc('告警组'),
      window.i18n.tc('匹配规则'),
      window.i18n.tc('通知升级'),
      window.i18n.tc('流程'),
      window.i18n.tc('等级调整'),
      window.i18n.tc('追加标签'),
      window.i18n.tc('状态')
    ];
    const tdArr = [];
    this.tableData.forEach(item => {
      // const severity = LEVELLIST.find(lev => lev.value === item.alertSeverity)?.name || '';

      const row = [
        item.userGroups.join(';'),
        JSON.stringify(item.conditions).replace(/,/g, '，'),
        JSON.stringify({
          is_enabled: item.upgradeConfig.noticeIsEnabled,
          upgrade_config: {
            is_enabled: item.upgradeConfig.isEnabled,
            user_groups: item.upgradeConfig.userGroups,
            upgrade_interval: item.upgradeConfig.upgradeInterval
          }
        }).replace(/,/g, '，'),
        item.actionId || '',
        item.alertSeverity,
        // 补充 规则 通知
        item.additionalTags.map(tag => `${tag.key}:${tag.value}`).join(';'),
        item.isEnabled
      ];
      tdArr.push(row);
    });
    const csvStr = transformTableDataToCsvStr(thArr, tdArr);
    downCsvFile(csvStr, `${this.ruleGroupData.name}-${dayjs.tz().format('YYYY-MM-DD HH-mm-ss')}.csv`);
  }

  /** 导入 */
  handleImportChange(data: string) {
    const importData = csvToArr(data);
    const header = importData.shift();

    // to do 校验
    const thArr = [
      window.i18n.tc('告警组'),
      window.i18n.tc('匹配规则'),
      window.i18n.tc('通知升级'),
      window.i18n.tc('流程'),
      window.i18n.tc('等级调整'),
      window.i18n.tc('追加标签'),
      window.i18n.tc('状态')
    ];
    if (header.toString() !== thArr.toString()) {
      return;
    }

    try {
      const targetImportData = importData.map(
        item =>
          new RuleData(
            transformDataKey(
              {
                user_groups: item[0].split(';').map(item => Number(item)),
                conditions: JSON.parse(item[1].replace(/，/g, ',')),
                actions: [
                  {
                    action_type: 'notice',
                    ...JSON.parse(item[2].replace(/，/g, ','))
                  },
                  {
                    action_type: 'itsm',
                    action_id: Number(item[3])
                  }
                ],
                alert_severity: Number(item[4]),
                // actionId: Number(item[4]),
                additional_tags: item[5]
                  .split(';')
                  .map(item => ({ key: item.split(':')[0], value: item.split(':')[1] })),
                is_enabled: item[6] === 'true'
              },
              false
            )
          )
      );
      // new RuleData({ ...transformDataKey(item, false) }))
      this.tableData = [...this.tableData, ...targetImportData];
    } catch (error) {
      console.log(error);
    }
  }

  /* 查找替换 */
  handleFindReplace(value) {
    const { findData, replaceData } = value;
    this.tableData.forEach((item, index) => {
      if (item.isCheck) {
        item.setFindReplace(findData, replaceData);
        this.handleDiffRuleItemChange(item, 'conditions', index);
      }
    });
    this.removePopoverInstance();
  }

  /* 统一设置初始化 */
  unifiedSettingInit() {
    const setConidtions = conditions => {
      this.unifiedSettings.conditions = conditions;
      this.unifiedSettings.targetConditions = conditions;
    };
    if (!!(this.ruleGroupData.settings as any)?.public_conditions) {
      const allConditions = this.tableData.map(item => item.conditions);
      const statisticsConditions = statisticsSameConditions(allConditions);
      setConidtions(statisticsConditions);
    }
  }

  /* 点击统一设置 */
  handleClickUnifiedSetting(isConditionChange = false) {
    if (!!this.unifiedSettings.popInstance?.show) {
      this.handleCancelUnifiedSettings();
      return;
    }
    this.unifiedSettings.isConditionChange = isConditionChange;
    let show = false;
    if (isConditionChange) {
      /* 获取相同条件 */
      const getStatisticsConditions = () => {
        const allConditions = this.tableData.map(item => item.conditions);
        return statisticsSameConditions(allConditions);
      };
      /* 判断是否输入了相同的条件 */
      const judgeSame = (conditions?) => {
        const statisticsConditions = conditions || getStatisticsConditions();
        const statisticsConditionsSort = JSON.parse(JSON.stringify(statisticsConditions))?.sort?.();
        const conditionsSort = JSON.parse(JSON.stringify(this.unifiedSettings.conditions))?.sort?.();
        return JSON.stringify(statisticsConditionsSort) === JSON.stringify(conditionsSort);
      };
      if (this.tableData.length >= 3) {
        const statisticsConditions = getStatisticsConditions();
        if (!judgeSame(statisticsConditions) && !!statisticsConditions.length) {
          this.unifiedSettings.targetConditions = JSON.parse(JSON.stringify(statisticsConditions));
          show = true;
        }
      }
    } else {
      this.unifiedSettings.targetConditions = JSON.parse(JSON.stringify(this.unifiedSettings.conditions));
      show = true;
    }
    if (show) {
      this.unifiedSettings.conditionsSelectorKey = random(8);
      this.$nextTick(() => {
        this.unifiedSettings.popInstance = this.$bkPopover(this.unifiedSettingBtnRef, {
          content: this.unifiedSettingsRef,
          trigger: 'manual',
          interactive: true,
          theme: 'light common-monitor',
          arrow: true,
          placement: 'bottom-start',
          boundary: 'window',
          hideOnClick: false,
          zIndex: 2000
        });
        this.unifiedSettings.popInstance?.show?.();
      });
    }
  }

  handleAddUnifiedSettings() {
    this.unifiedSettings.targetConditions = JSON.parse(JSON.stringify(this.unifiedSettings.conditions));
    // this.unifiedSettings.isAdd = true;
  }
  handleCancelUnifiedSettings() {
    // if (!this.unifiedSettings.isAdd) {
    //   this.unifiedSettings.conditions = [];
    //   this.unifiedSettings.targetConditions = [];
    // }
    this.unifiedSettings.popInstance?.hide?.(0);
    this.unifiedSettings.popInstance?.destroy?.();
    this.unifiedSettings.popInstance = null;
  }
  /* 统一设置确定 */
  handleConfirmUnifiedSettings() {
    const findData = this.unifiedSettings.conditions;
    const replaceData = this.unifiedSettings.targetConditions;
    if (this.unifiedSettings.isConditionChange || !findData.length) {
      const addConditions = deepClone(this.unifiedSettings.targetConditions);
      this.tableData.forEach((item, index) => {
        item.unshiftConditions(addConditions);
        this.handleDiffRuleItemChange(item, 'conditions', index);
      });
    } else {
      this.tableData.forEach((item, index) => {
        // item.setFindReplace(findData, replaceData, true);
        item.setUnifiedSettings(findData, replaceData, item.conditions);
        this.handleDiffRuleItemChange(item, 'conditions', index);
      });
    }
    this.unifiedSettings.conditions = JSON.parse(JSON.stringify(this.unifiedSettings.targetConditions));
    this.handleCancelUnifiedSettings();
  }
  handleUnifiedSettingsConditionsChange(conditions) {
    this.unifiedSettings.targetConditions = conditions;
  }
  /** 取消 */
  handleCancel() {
    this.$router.back();
  }

  /** 校验追加标签格式 */
  handleAdditionalTagsChange(value: string[], row: RuleData, index: number) {
    // 兼容key:value 和key=value两种模式
    let errorIndex = null;
    let result = true;
    result = value.every((item, index) => {
      // 开头和结尾不能是:或=, 中间必须含有一个:或=
      const reg = /^[^:=]+[:=][^:=]+$/;
      const isTargetTag = reg.test(item);
      if (!isTargetTag) errorIndex = index;
      return isTargetTag;
    });

    const validateErrorTag = (msg: string) => {
      row.setVerificatory('additionalTags', true, this.$t(msg));
      this.$nextTick(() => {
        const tagList = (this.$refs[`additionalTags${index}`] as any).$el.getElementsByClassName('key-node');
        tagList[errorIndex].style = 'border: 1px solid red;';
        (this.$refs[`additionalTags${index}`] as any).$el.getElementsByTagName('input')[0].disabled = true;
      });
    };

    if (!result) {
      validateErrorTag('标签格式不正确,格式为key:value 或 key=value');
      return result;
    }

    const keyList = row.additionalTags.map(item => item.key);
    const setArr = [...new Set(keyList)];

    if (keyList.length !== setArr.length) {
      result = false;
      errorIndex = keyList.length - 1;
      validateErrorTag('注意: 名字冲突');
    } else {
      row.setVerificatory('additionalTags', false, '');
      (this.$refs[`additionalTags${index}`] as any).$el.getElementsByTagName('input')[0].disabled = false;
    }

    return result;
  }

  /* 清空统一设置 */
  handleSettingsClear() {
    this.unifiedSettings.conditions = [];
    this.unifiedSettings.targetConditions = [];
    this.unifiedSettings.conditionsSelectorKey = random(8);
  }

  handleSaveSuccess() {
    this.isEffect = true;
    this.$router.push({ name: 'alarm-dispatch' });
  }

  /** 判断rule-item是否发生变化 */
  handleDiffRuleItemChange(row: RuleData, field: string, index: number) {
    const diffRuleItem = (data1: RuleData, row) => {
      const newRleData = {};
      const newItem = {};

      if (field === 'additionalTags') {
        newRleData[field] = data1[field].map(tag => ({ key: tag.key, value: tag.value }));
        newItem[field] = row[field].map(tag => ({ key: tag.key, value: tag.value }));
      } else if (field === 'actionId') {
        newRleData[field] = data1[field] ? data1[field] : undefined;
        newItem[field] = row[field] ? row[field] : undefined;
      } else if (field === 'upgradeConfig') {
        newRleData[field] = data1[field].isEnabled ? data1[field] : data1[field].isEnabled;
        newItem[field] = row[field].isEnabled ? row[field] : row[field].isEnabled;
      } else {
        newRleData[field] = data1[field];
        newItem[field] = row[field];
      }

      this.tableData[index].setConfig(field, !deepCompare(newRleData[field], newItem[field]));
    };
    // DB现有的规则
    const ruleData = this.cacheTableData.find(config => config.id === row.id && row.id !== 0);
    if (ruleData) {
      diffRuleItem(ruleData, row);
    } else {
      // 新增的规则
      const addRuleData = this.cacheTableData.find(config => config.addId === row.addId);
      if (addRuleData) {
        diffRuleItem(addRuleData, row);
      } else {
        // 复制的规则
        const copyRuleData = this.cacheTableData.find(config => config.copyId === row.copyId);
        if (copyRuleData) {
          diffRuleItem(copyRuleData, row);
        }
      }
    }
  }

  getAlertSeverityName(level: number) {
    return LEVELLIST.find(item => item.value === level)?.name || level;
  }

  getRuleItemType(row, column) {
    if (row.verificatory[column.id]) {
      return 'rule-verification';
    }
    if (this.isInitialRule) {
      return 'rule-initial';
    }
    if (row.addId || row.copyId) {
      return 'rule-add';
    }
    if (row.config[column.id]) {
      return 'rule-change';
    }
    return 'rule-common';
  }

  /** 通知、流程、等级、标签列合并 */
  handleColumnsMerge(column: MergeColumn, index: number) {
    this.mergeConfig[column] = !this.mergeConfig[column];
    this.$set(this.processList[index], 'colspan', this.mergeConfig[column] ? 1 : 2);
    this.tableColumnsInit();
  }

  /** 判断是合并列是否有内容 */
  judgeHasContent(row: RuleData, column: MergeColumn) {
    // 通知升级和流程合并列
    if (column === 'noticeProgress') {
      return row.actionId || row.upgradeConfig.isEnabled;
    }
    // 等级和标签合并列
    if (column === 'levelTag') {
      return row.alertSeverity || row.additionalTags.length;
    }
  }

  /** 校验告警组 */
  validateAlarmGroup(row: RuleData) {
    if (!row.userGroups.length && !row.isNullData) {
      row.setVerificatory('userGroups', true, this.$t('告警组不能为空'));
      return;
    }

    // 告警组不能和通知升级里的告警组有交集
    const intersectionSet = [...new Set(row.userGroups)].filter(item =>
      new Set(row.upgradeConfig.userGroups).has(item)
    );

    if (intersectionSet.length && row.upgradeConfig.noticeIsEnabled && row.upgradeConfig.isEnabled) {
      row.setVerificatory('userGroups', true, this.$t('通知升级的告警组不能和原告警组相同'));
      return;
    }

    row.setVerificatory('userGroups', false);
  }

  /** 跳转创建流程套餐 */
  handleAddProcess() {
    const url = `${location.origin}${location.pathname}?bizId=${this.$store.getters.bizId}#/set-meal-add`;
    window.open(url);
  }

  /** 跳转创建流程套餐 */
  handleRefreshProcess() {
    if (this.processLoading) {
      return;
    }
    this.getProcessPackage();
  }

  handleTableScroll(e) {
    this.tableScrollTop = e.target.scrollTop;
  }

  render() {
    return (
      <div
        class='alarm-dispatch-config-page'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='config-content'>
          <div
            class={['table-wrap', { 'is-scroll': this.tableScrollTop }]}
            onScroll={this.handleTableScroll}
          >
            <table
              class='table-wrap-content'
              border='1'
              cellspacing='0'
              cellpadding='0'
            >
              <tr class='table-wrap-header-tr'>
                <td
                  class='table-wrap-header-td'
                  colspan={15}
                >
                  <div class='table-wrap-header'>
                    <div class='title-wrap'>
                      <span
                        class='title'
                        v-bk-overflow-tips
                      >
                        {this.ruleGroupData.name || ''}
                      </span>
                      <span class='rule-count'>{`(${this.tableData.length})`}</span>
                      <span
                        class='icon-monitor icon-bianji'
                        onClick={e => {
                          this.handleBatchEdit(e, 'name');
                          this.dataSource = this.ruleGroupData.name;
                        }}
                      ></span>
                    </div>
                    <div class='priority-wrap'>
                      <span class='title'>{this.$t('优先级')}:</span>
                      <span class='count'>{this.ruleGroupData.priority || 0}</span>
                      <span
                        class='icon-monitor icon-bianji'
                        onClick={e => {
                          this.handleBatchEdit(e, 'priority');
                          this.dataSource = this.ruleGroupData.priority;
                        }}
                      ></span>
                    </div>
                    <div class='file-wrap'>
                      <MonitorImport
                        accept={'.csv'}
                        return-text={true}
                        base64={false}
                        onChange={this.handleImportChange}
                      >
                        <bk-button
                          size='small'
                          class='mr10'
                        >
                          {this.$t('导入')}
                        </bk-button>
                      </MonitorImport>
                      <bk-button
                        size='small'
                        onClick={this.handleExportChange}
                      >
                        {this.$t('导出')}
                      </bk-button>
                    </div>
                  </div>
                </td>
              </tr>
              {/* 流程表头 */}
              <tr class='process-list'>
                {this.processList.map((item, index) => (
                  <td
                    colspan={item.colspan}
                    style={{
                      'border-color': item.bg
                    }}
                  >
                    <div
                      class='process-list-item'
                      style={{
                        background: item.bg
                      }}
                    >
                      {!!item.arrow && (
                        <div
                          class='process-arrow'
                          style={{
                            'border-color': item.arrow
                          }}
                        ></div>
                      )}
                      {item.index && <div class='index'>{item.index}</div>}
                      {item.text && (
                        <div
                          class={[
                            'text',
                            { 'text-en': getCookie('blueking_language') === 'en' && this.mergeConfig[item.merge] }
                          ]}
                          v-bk-overflow-tips
                        >
                          {item.text}
                        </div>
                      )}
                      {item.merge && (
                        <div
                          class={['merge', this.mergeConfig[item.merge] ? 'icon-expand' : 'icon-reduce']}
                          v-bk-tooltips={{
                            content: this.$t(this.mergeConfig[item.merge] ? '展开' : '收起')
                          }}
                          onClick={() => {
                            this.handleColumnsMerge(item.merge as MergeColumn, index);
                          }}
                        ></div>
                      )}
                    </div>
                  </td>
                ))}
              </tr>
              {/* 表头 */}
              <tr class='table-column'>
                {this.tableColumns.map(item => (
                  <th
                    key={item.id}
                    v-show={item.show}
                    class={item.class || ''}
                    style={{ width: `${item.width}px` }}
                  >
                    {item.content?.()}
                  </th>
                ))}
              </tr>
              {/* 批量行 */}
              {this.tableData.some(item => item.isCheck) && (
                <tr class={['batch-list', { 'is-scroll': this.tableScrollTop }]}>
                  {this.tableColumns.map(item => (
                    <td v-show={item.show}>
                      <div class='batch-list-item'>
                        {hasBatchColumn.includes(item.id) && (
                          <span
                            class='icon-monitor icon-mc-edit'
                            onClick={e => {
                              this.handleBatchEdit(e, item.id);
                            }}
                          ></span>
                        )}
                        {/* 批量删除、批量撤回 */}
                        {item.id === 'operate' && (
                          <div class='batch-operate-warp'>
                            <bk-popconfirm
                              content={this.$t('是否批量删除勾选规则？')}
                              ext-popover-cls='alarm-dispatch-rule-operate'
                              onConfirm={() => this.handleOperateAction('batchDelete')}
                              onCancel={() => (this.batchTipsDisabled = false)}
                              tippy-options={{
                                onHide: () => {
                                  this.batchTipsDisabled = false;
                                }
                              }}
                              trigger='click'
                            >
                              <span
                                class='icon-monitor icon-jian'
                                onClick={() => (this.batchTipsDisabled = true)}
                                v-bk-tooltips={{ content: this.$t('批量删除'), disabled: this.batchTipsDisabled }}
                              ></span>
                            </bk-popconfirm>
                            <bk-popconfirm
                              content={this.$t('是否批量撤回勾选规则上一次生效的配置？')}
                              ext-popover-cls='alarm-dispatch-rule-operate'
                              onConfirm={() => this.handleOperateAction('batchReset')}
                              onCancel={() => (this.batchTipsDisabled = false)}
                              tippy-options={{
                                onHide: () => {
                                  this.batchTipsDisabled = false;
                                }
                              }}
                              trigger='click'
                            >
                              <span
                                class='icon-monitor icon-chehui1'
                                onClick={() => (this.batchTipsDisabled = true)}
                                v-bk-tooltips={{ content: this.$t('批量撤回'), disabled: this.batchTipsDisabled }}
                              ></span>
                            </bk-popconfirm>
                            <span class='icon-monitor icon-jian icon-hidden'></span>
                            <span class='icon-monitor icon-jian icon-hidden'></span>
                          </div>
                        )}
                      </div>
                    </td>
                  ))}
                </tr>
              )}
              {/* 表格数据 */}
              {this.tableData.map((row, index) => (
                <tr
                  class='table-data-row'
                  key={index}
                >
                  {this.tableColumns.map(column => (
                    <td
                      class='rule-td'
                      style={{ width: `${column.width}px`, minWidth: `${column.width}px` }}
                      v-show={column.show}
                    >
                      <div
                        class={[
                          'rule-td-item',
                          this.getRuleItemType(row, column),
                          { 'is-active': !['select', 'operate'].includes(column.id) },
                          { 'condition-wrap': column.id === EColumn.conditions },
                          { 'alarm-group-wrap': column.id === EColumn.userGroups }
                        ]}
                      >
                        {this.getRowContent(row, column.id, index)}
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
            </table>

            <div class='opreate-warp'></div>
          </div>
          <div class='config-footer'>
            <span
              v-bk-tooltips={{
                placements: ['top'],
                content: this.$t('内置的分派规则组不允许修改'),
                disabled: this.editAllowed
              }}
            >
              <bk-button
                theme='primary'
                onClick={() => this.handleStartDebug()}
                class='mr10'
                disabled={!this.editAllowed}
              >
                {this.$t('调试并生效')}
              </bk-button>
            </span>
            <bk-button onClick={this.handleCancel}>{this.$t('取消')}</bk-button>
          </div>
        </div>
        <AlarmGroupDetail
          id={this.alarmGroupDetail.id as any}
          v-model={this.alarmGroupDetail.show}
          customEdit={false}
        />
        <div style='display: none'>
          <AlarmBatchEdit
            ref='alarmBatchEdit'
            filed={this.filed}
            priorityList={this.priorityList}
            alarmDisabledList={this.alarmDisabledList}
            processPackage={this.processPackage}
            alarmGroupList={this.alarmGroupList}
            processLoading={this.processLoading}
            alarmGroupListLoading={this.alarmGroupListLoading}
            dataSource={this.dataSource}
            conditionProps={{
              keyList: this.kvOptionsData.keys,
              valueMap: this.kvOptionsData.valueMap,
              groupKey: GROUP_KEYS,
              groupKeys: this.kvOptionsData.groupKeys
            }}
            canDebug={this.canDebug}
            addProcess={this.handleAddProcess}
            showAlarmGroupDetail={this.handleSelcetAlarmGroup}
            refreshProcess={this.handleRefreshProcess}
            refreshAlarm={this.handleRefreshAlarmGroup}
            onSubmit={this.handleBatchEditSubmit}
            close={this.removePopoverInstance}
            onFindReplace={this.handleFindReplace}
          />
        </div>
        {/* 调试结果 */}
        {this.showSideliner && (
          <DebuggingResult
            isShow={this.showSideliner}
            alarmGroupList={this.alarmGroupList}
            ruleGroupsData={this.debugData}
            conditionProps={{
              keys: this.kvOptionsData.keys,
              valueMap: this.kvOptionsData.valueMap,
              groupKey: GROUP_KEYS,
              groupKeys: this.kvOptionsData.groupKeys
            }}
            onShowChange={this.handleShowChange}
            onSaveSuccess={this.handleSaveSuccess}
          />
        )}
        {/* 统一设置 */}
        <div style={'display: none'}>
          <div
            class='alarm-dispatch-config-unified-setting'
            ref='unifiedSettings'
          >
            <div class='setting-content-wrap'>
              <div class='setting-title ml16'>
                {this.unifiedSettings.isConditionChange
                  ? `${this.$t('是否将以下条件添加到')} ${this.$t('统一设置')}`
                  : this.$t('统一设置条件')}
                <span
                  class='icon-monitor icon-tishi'
                  v-bk-tooltips={{
                    content: this.$t('添加统一设置后，所有规则会默认添加上所设置的条件'),
                    placements: ['top'],
                    delay: [100, 0]
                  }}
                ></span>
              </div>
              <div class='ml16 mr16'>
                <CommonCondition
                  key={this.unifiedSettings.conditionsSelectorKey}
                  value={this.unifiedSettings.targetConditions}
                  keyList={this.kvOptionsData.keys as any}
                  groupKey={GROUP_KEYS}
                  groupKeys={this.kvOptionsData.groupKeys}
                  valueMap={this.kvOptionsData.valueMap}
                  specialOptions={this.kvOptionsData.specialOptions}
                  loading={this.conditionsLoading}
                  needValidate={false}
                  isFormMode={false}
                  onChange={this.handleUnifiedSettingsConditionsChange}
                ></CommonCondition>
              </div>
              <div class='bottom-opreate'>
                <bk-button
                  size='small'
                  class='mr8'
                  theme='primary'
                  onClick={this.handleConfirmUnifiedSettings}
                >
                  {this.$t('确定')}
                </bk-button>
                <bk-button
                  size='small'
                  onClick={this.handleCancelUnifiedSettings}
                >
                  {this.$t('取消')}
                </bk-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  getRowContent(row: RuleData, id: EColumn, index: number) {
    switch (id) {
      // 选择框
      case EColumn.select:
        return (
          <div class='table-data-row-item'>
            <bk-checkbox
              v-model={row.isCheck}
              onChange={this.handleCheckChange}
            ></bk-checkbox>
          </div>
        );

      case EColumn.conditions:
        return (
          <CommonCondition
            key={row.conditionsRenderKey}
            value={row.conditions}
            keyList={this.kvOptionsData.keys as any}
            groupKey={GROUP_KEYS}
            groupKeys={this.kvOptionsData.groupKeys}
            valueMap={this.kvOptionsData.valueMap}
            replaceData={row.replaceData}
            specialOptions={this.kvOptionsData.specialOptions}
            settingsValue={this.unifiedSettings.conditions}
            loading={this.conditionsLoading}
            needValidate={!row.isNullData}
            onChange={v => this.handleConditionChange(v, index)}
            onSettingsChange={this.handleSettingsClear}
            onValidate={v => row.setVerificatory('conditions', v)}
            onRepeat={v => row.setConditionsRepeat(v)}
          ></CommonCondition>
        );
      // 告警组
      case EColumn.userGroups:
        return (
          <div
            class={[
              'table-data-row-item',
              'alarm-gourp-contaier',
              { 'is-change': row.config[id] },
              { 'is-err': row.verificatory[id] }
            ]}
          >
            <AlarmGroupSelect
              value={row.userGroups}
              options={this.alarmGroupList}
              loading={this.alarmGroupListLoading}
              onTagclick={this.handleSelcetAlarmGroup}
              onRefresh={this.handleRefreshAlarmGroup}
              onChange={value => {
                row.userGroups = value;
                this.handleDiffRuleItemChange(row, id, index);
                this.validateAlarmGroup(row);
              }}
            ></AlarmGroupSelect>
            <i
              class='icon-monitor icon-mind-fill'
              v-bk-tooltips={{
                content: row.validateTips[id],
                placements: ['top'],
                allowHTML: false
              }}
            ></i>
          </div>
        );

      case EColumn.actionId:
        return (
          <div
            class={[
              'table-data-row-item',
              'alarm-group-select-wrap',
              'action-id-wrap',
              { 'is-change': row.config[id] }
            ]}
          >
            <bk-select
              v-model={row.actionId}
              class='alarm-group-select'
              ext-popover-cls={'alarm-group-select-process-component-pop'}
              onChange={value => {
                row.setActions(value, 'itsm');
                this.handleDiffRuleItemChange(row, id, index);
              }}
            >
              {this.processPackage.map(option => (
                <bk-option
                  key={option.id}
                  id={option.id}
                  name={option.name}
                />
              ))}
              <div
                slot='extension'
                class='extension-wrap'
              >
                <div
                  class='add-wrap'
                  onClick={this.handleAddProcess}
                >
                  <span class='icon-monitor icon-jia'></span>
                  <span>{this.$t('创建流程')}</span>
                </div>
                <div
                  class='loading-wrap'
                  onClick={this.handleRefreshProcess}
                >
                  {this.processLoading ? (
                    <img
                      alt=''
                      // eslint-disable-next-line @typescript-eslint/no-require-imports
                      src={require('../../static/images/svg/spinner.svg')}
                      class='status-loading'
                    ></img>
                  ) : (
                    <span class='icon-monitor icon-mc-retry'></span>
                  )}
                </div>
              </div>
            </bk-select>
          </div>
        );
      // 通知升级
      case EColumn.upgradeConfig:
        return (
          <div
            class={['table-data-row-item', 'notify-upgrade', { 'is-change': row.config[id] }]}
            onClick={e => this.handleNoticeEdit(e, 'notice', index, row.userGroups, row.upgradeConfig)}
          >
            {row.upgradeConfig?.noticeIsEnabled ? (
              <div>
                {row.upgradeConfig?.isEnabled ? (
                  <div class='notice-content'>
                    <div> {this.$t('间隔{0}分钟，逐个通知', { 0: row.upgradeConfig?.upgradeInterval })}</div>
                    {row.upgradeConfig.userGroups.map((item, num) => (
                      <span>
                        <span
                          class='alarm-group'
                          onClick={e => {
                            e.stopPropagation();
                            this.handleSelcetAlarmGroup(item);
                          }}
                        >
                          {this.getAlarmGroupNames(item)}
                        </span>
                        {row.upgradeConfig.userGroups.length - 1 !== num && <span> , </span>}
                      </span>
                    ))}
                  </div>
                ) : (
                  this.$t('直接通知')
                )}
              </div>
            ) : (
              this.$t('关闭通知')
            )}
          </div>
        );
      // 等级调整
      case EColumn.alertSeverity:
        return (
          <div
            class={['table-data-row-item', 'alarm-group-select-wrap', { 'is-change': row.config[id] }]}
            onClick={e => {
              this.handleBatchEdit(e, 'alertSeveritySingle');
              this.dataSource = row.alertSeverity;
              this.currentIndex = index;
            }}
          >
            <span>{this.getAlertSeverityName(row.alertSeverity)}</span>
          </div>
        );
      // 状态
      case EColumn.isEnabled:
        return (
          <div class={['table-data-row-item', { 'is-change': row.config[id] }]}>
            <bk-switcher
              v-model={row.isEnabled}
              theme='primary'
              size='small'
              onChange={() => {
                this.handleDiffRuleItemChange(row, id, index);
              }}
            />
          </div>
        );
      // 追加标签
      case EColumn.additionalTags:
        return (
          <div
            class={[
              'table-data-row-item',
              'alarm-group-select-wrap',
              'additional-tags',
              { 'is-change': row.config[id] }
            ]}
          >
            <bk-tag-input
              class='alarm-group-select'
              ref={`additionalTags${index}`}
              v-model={row.tag}
              onChange={value => {
                row.setAdditionalTags(value);
                this.handleAdditionalTagsChange(value, row, index);
                this.handleDiffRuleItemChange(row, id, index);
              }}
              tooltip-key='name'
              clearable={false}
              disabled={false}
              allow-auto-match={true}
              placeholder={this.$t('填写标签，格式key:value')}
              allow-create={true}
              has-delete-icon={true}
            ></bk-tag-input>
            {row.validateTips[id] && (
              <i
                class='icon-monitor icon-mind-fill'
                v-bk-tooltips={{
                  content: row.validateTips[id],
                  allowHTML: false
                }}
              ></i>
            )}
          </div>
        );

      // 复制 | 添加 | 删除 | 撤销
      case EColumn.operate:
        return (
          <div class='table-data-row-item operate-wrap'>
            <span
              class='icon-monitor icon-mc-copy'
              onClick={() => this.handleOperateAction('copy', index)}
              v-bk-tooltips={{ content: this.$t('复制'), disabled: row.tooltipsDisabled }}
            ></span>
            <span
              class='icon-monitor icon-jia'
              onClick={() => this.handleOperateAction('add', index)}
              v-bk-tooltips={{ content: this.$t('增加'), disabled: row.tooltipsDisabled }}
            ></span>
            <bk-popconfirm
              content={this.$t('是否删除当前规则?')}
              ext-popover-cls='alarm-dispatch-rule-operate'
              onConfirm={() => {
                this.handleOperateAction('delete', index);
              }}
              tippy-options={{
                onHide: () => {
                  row.setTooltipsDisabled(false);
                }
              }}
              trigger='click'
            >
              <span
                class='icon-monitor icon-jian'
                onClick={() => row.setTooltipsDisabled(true)}
                v-bk-tooltips={{ content: this.$t('删除'), disabled: row.tooltipsDisabled }}
              />
            </bk-popconfirm>
            {/* 复制和新增的规则不支持撤回 */}
            {!this.resetConfig[index]?.disabled && !row.addId && !row.copyId ? (
              <bk-popconfirm
                content={this.$t('是否撤销当前编辑内容？')}
                ext-popover-cls='alarm-dispatch-rule-operate'
                onConfirm={() => this.handleOperateAction('reset', index)}
                tippy-options={{
                  onHide: () => {
                    row.setTooltipsDisabled(false);
                  }
                }}
                trigger='click'
              >
                <span
                  class='icon-monitor icon-chehui1'
                  onClick={() => row.setTooltipsDisabled(true)}
                  v-bk-tooltips={{
                    content: this.$t('撤销回上一次生效的配置'),
                    disabled: row.tooltipsDisabled
                  }}
                />
              </bk-popconfirm>
            ) : (
              <span
                class='icon-monitor icon-chehui1 disabled'
                v-bk-tooltips={{
                  content:
                    row.addId || row.copyId ? this.$t('新建规则不能撤回, 可以删除') : this.$t('未编辑, 不需要撤销'),
                  disabled: row.tooltipsDisabled
                }}
              />
            )}
          </div>
        );
      case 'noticeProgress':
      case 'levelTag':
        return (
          <div class='table-data-row-item colspan-item'>
            <div class={{ content: this.judgeHasContent(row, id) }}>{this.$t('展开后编辑')}</div>
          </div>
        );

      default:
        return <div class='table-data-row-item'></div>;
    }
  }
}
