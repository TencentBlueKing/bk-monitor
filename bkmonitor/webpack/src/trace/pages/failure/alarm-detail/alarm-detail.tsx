/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import {
  type Ref,
  computed,
  defineComponent,
  inject,
  nextTick,
  onBeforeMount,
  onMounted,
  onUnmounted,
  reactive,
  shallowRef,
  triggerRef,
  watch,
} from 'vue';

import { useResizeObserver } from '@vueuse/core';
import { Loading, Message } from 'bkui-vue';
import {
  feedbackIncidentRoot,
  incidentAlertList,
  incidentRecordOperation,
  incidentValidateQueryString,
} from 'monitor-api/modules/incident';
import { random } from 'monitor-common/utils/utils.js';
import { useI18n } from 'vue-i18n';

import ExceptionComp from '../../../components/exception';
import SetMealAdd from '../../../store/modules/set-meal-add';
import AlertContentDetail, {
  type AlertSavePromiseEvent,
} from '../../alarm-center/components/alarm-table/components/alert-content-detail/alert-content-detail';
import AlertSelectionToolbar from '../../alarm-center/components/alarm-table/components/alert-selection-toolbar/alert-selection-toolbar';
import CommonTable from '../../alarm-center/components/alarm-table/components/common-table/common-table';
import { usePopover } from '../../alarm-center/components/alarm-table/hooks/use-popover';
import { saveAlertContentName } from '../../alarm-center/services/alert-services';
import {
  type AlertContentItem,
  type AlertContentNameEditInfo,
  type AlertSelectBatchAction,
  AlertAllActionEnum,
} from '../../alarm-center/typings';
import { incidentAlarmDetailInject } from '../composables/use-alarm-detail';
import FeedbackCauseDialog from '../failure-topo/feedback-cause-dialog';
import { replaceSpecialCondition, useIncidentInject } from '../utils';
import AlarmConfirm from './alarm-confirm';
import AlarmDispatch from './alarm-dispatch';
import ChatGroup from './chat-group/chat-group';
import Collapse from './collapse';
import { type IncidentAlertAction, IncidentAlertScenario } from './incident-alert-scenario';
import ManualProcess from './manual-process';
import QuickShield from './quick-shield';
import { useIncidentAlertColumns } from './use-incident-alert-columns';

import type { AlertTableItem, TableColumnItem } from '../../alarm-center/typings';
import type { IFilterSearch, IIncident } from '../types';
import type { BkUiSettings } from '@blueking/tdesign-ui';
import type { SelectOptions, SlotReturnValue } from 'tdesign-vue-next';

import '../../alarm-center/components/alarm-table/alarm-table.scss';
import '../../alarm-center/components/alarm-table/components/common-table/common-table.scss';
import './alarm-detail.scss';

export default defineComponent({
  props: {
    filterSearch: {
      type: Object as () => IFilterSearch,
      default: () => ({}),
    },
    alertIdsObject: {
      type: [Object, String],
      default: () => ({}),
    },
    searchValidate: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['refresh'],
  setup(props, { emit }) {
    const { t } = useI18n();

    // ==================== 通用状态 ====================
    const exceptionData = shallowRef({
      isError: false,
      errorMsg: '',
    });
    const bkzIds = inject<Ref<string[]>>('bkzIds');
    const setMealAddModule = SetMealAdd();
    onBeforeMount(async () => await setMealAddModule.getVariableDataList());
    const incidentId = useIncidentInject();
    const tableLoading = shallowRef(false);
    const alertData = shallowRef([]);
    const currentData = shallowRef({});
    const currentIds = shallowRef([]);
    const currentBizIds = shallowRef([]);
    const dialog = reactive({
      quickShield: {
        show: false,
        details: [
          {
            severity: 1,
            dimension: [],
            trigger: '',
            alertId: '',
            strategy: {
              id: '',
              name: '',
            },
          },
        ],
        ids: [],
        bizIds: [],
      },
      alarmConfirm: {
        show: false,
        ids: [],
        bizIds: [],
      },
      rootCauseConfirm: {
        show: false,
        ids: [],
        data: {},
        bizIds: [],
      },
      alarmDispatch: {
        show: false,
        bizIds: [],
        alertIds: [],
        data: {},
      },
      manualProcess: {
        show: false,
        alertIds: [],
        bizIds: [],
        debugKey: random(8),
        actionIds: [],
        mealInfo: null,
      },
    });
    const incidentDetail = inject<Ref<IIncident>>('incidentDetail');
    const incidentDetailData = computed(() => incidentDetail.value);

    /** 一键拉群弹窗  */
    const chatGroupDialog = reactive({
      show: false,
      alertName: '',
      bizId: [],
      assignee: [],
      alertIds: [],
    });

    const collapseId = shallowRef('');
    const alertIdsData = shallowRef(props.alertIdsObject);
    const alarmDetailRef = shallowRef<HTMLElement | null>(null);

    // ==================== 排序状态 ====================
    /** 每个 collapse 表格独立的排序，key 为 collapse item id，格式：'-field' 降序 / 'field' 升序 */
    const tableSortMap = shallowRef<Record<string, string>>({});

    /** 获取指定 collapse 的排序 */
    const getTableSort = (collapseItemId: number | string): string => {
      return tableSortMap.value[collapseItemId] || '';
    };

    /** 排序变化回调（按 collapse 分组独立） */
    const handleSortChange = (collapseItemId: number | string, sort: string | string[]) => {
      const sortValue = typeof sort === 'string' ? sort : sort[0] || '';
      tableSortMap.value = { ...tableSortMap.value, [collapseItemId]: sortValue };
    };

    /** 前端排序工具函数 */
    const sortAlerts = (alerts: AlertTableItem[], sortStr: string): AlertTableItem[] => {
      if (!sortStr || !alerts?.length) return alerts;

      const isDescending = sortStr.startsWith('-');
      const sortField = isDescending ? sortStr.slice(1) : sortStr;

      return [...alerts].sort((a, b) => {
        const valA = a[sortField];
        const valB = b[sortField];
        if (valA == null && valB == null) return 0;
        if (valA == null) return 1;
        if (valB == null) return -1;
        let result = 0;
        if (typeof valA === 'number' && typeof valB === 'number') {
          result = valA - valB;
        } else {
          result = String(valA).localeCompare(String(valB));
        }
        return isDescending ? -result : result;
      });
    };

    /** 每个 collapse 的排序后数据（computed 缓存，避免 render 中每次生成新数组） */
    const sortedAlertsMap = computed<Record<string, AlertTableItem[]>>(() => {
      const result: Record<string, AlertTableItem[]> = {};
      for (const item of alertData.value) {
        const sortStr = tableSortMap.value[item.id];
        result[item.id] = sortStr ? sortAlerts(item.alerts, sortStr) : item.alerts;
      }
      return result;
    });

    /** 获取指定 collapse 的排序后数据 */
    const getSortedAlerts = (collapseItemId: number | string): AlertTableItem[] => {
      return sortedAlertsMap.value[collapseItemId] || [];
    };

    // ==================== 行选择状态 ====================
    /** 每个 collapse 表格独立的选中行 keys，key 为 collapse item id */
    const selectedRowKeysMap = shallowRef<Record<string, (number | string)[]>>({});

    /** 获取指定 collapse 的选中行 keys */
    const getSelectedRowKeys = (collapseItemId: number | string): (number | string)[] => {
      return selectedRowKeysMap.value[collapseItemId] || [];
    };

    /** 判断指定 collapse 选中行是否均为关注人 */
    const isSelectedFollower = (collapseItemId: number | string): boolean => {
      const keys = getSelectedRowKeys(collapseItemId);
      if (!keys?.length) return false;
      const groupData = alertData.value.find(item => item.id === collapseItemId);
      if (!groupData) return false;
      return keys.every(key => {
        const row = (groupData.alerts || []).find(r => r.id === key);
        return row?.followerDisabled;
      });
    };

    // 表格容器 ref（用于单个折叠项时精确测量可用高度）
    const tableWrapperRef = shallowRef<HTMLElement | null>(null);
    // 表格最大高度（响应式）
    const tableMaxHeight = shallowRef<number | string | undefined>(undefined);

    /** 重新计算表格最大高度 */
    const recalcTableMaxHeight = () => {
      if (!alarmDetailRef.value) {
        tableMaxHeight.value = undefined;
        return;
      }
      const nonEmptyCount = alertData.value.filter(f => f.alerts.length > 0).length;
      if (nonEmptyCount > 1) {
        // 多个折叠项时使用 calc
        const staticHeight = 273;
        const itemHeight = 162;
        tableMaxHeight.value = `calc(100vh - ${staticHeight}px - ${(nonEmptyCount - 1) * itemHeight}px)`;
      } else {
        // 单个折叠项时：通过容器底边界精确计算表格可用高度
        const tableEl = tableWrapperRef.value;
        if (tableEl) {
          const containerRect = alarmDetailRef.value.getBoundingClientRect();
          const tableRect = tableEl.getBoundingClientRect();
          // 容器底边界(含 padding-bottom 20px 已在 contentRect 内) 减去表格顶部位置
          // containerRect.bottom 就是 .alarm-detail 的 border-box 底边
          // 但实际可用底边需要减去 padding-bottom(20px)
          const availableHeight = containerRect.bottom - 20 - tableRect.top;
          tableMaxHeight.value = Math.max(Math.floor(availableHeight), 200);
        } else {
          tableMaxHeight.value = undefined;
        }
      }
    };

    useResizeObserver(alarmDetailRef, () => {
      recalcTableMaxHeight();
    });

    // 是否只有一个折叠项（非空告警的分组数量）
    const isSingleCollapse = computed(() => {
      return alertData.value.filter(f => f.alerts.length > 0).length <= 1;
    });

    const { updateAlarmDetailData } = incidentAlarmDetailInject();

    // ==================== Popover 工具 ====================
    /** hover 场景使用的 popover 工具函数 */
    const hoverPopoverTools = usePopover();
    /** click 场景使用的 popover 工具函数 */
    const clickPopoverTools = usePopover({
      showDelay: 100,
      tippyOptions: {
        trigger: 'click',
        placement: 'bottom',
        theme: 'light alarm-center-popover max-width-50vw text-wrap padding-0',
      },
    });

    // ==================== 表格列配置 ====================
    const {
      tableColumns,
      allFields,
      displayFields,
      lockedFields,
      handleColumnResizeChange,
      handleDisplayColumnsChange,
    } = useIncidentAlertColumns();

    // ==================== 操作回调 ====================
    /** 显示告警详情抽屉 */
    const handleShowDetail = data => {
      data.id &&
        updateAlarmDetailData({
          bk_biz_id: data.bk_biz_id,
          id: data.id,
        });
    };

    const handleAlertSliderShowDetail = (row: AlertTableItem) => {
      handleShowDetail(row);
    };

    /** 告警内容详情 popover 相关状态 */
    const alertContentDetailRef = shallowRef(null);
    const activeBizId = shallowRef();
    const activeAlertId = shallowRef<string>('');
    const activeAlertContentDetail = shallowRef<AlertContentItem>(null);
    const isSaveContentNameActive = shallowRef(false);

    /** 打开告警内容详情 popover */
    const handleAlertContentDetailShow = (e: MouseEvent, row: AlertTableItem, colKey: string) => {
      if (isSaveContentNameActive.value) return;
      activeAlertContentDetail.value = row?.items?.[0];
      activeBizId.value = row.bk_biz_id;
      activeAlertId.value = row.id;
      clickPopoverTools.showPopover(e, () => alertContentDetailRef.value?.$el, `${row.id}-${colKey}`, {
        onHide: () => (isSaveContentNameActive.value ? false : void 0),
        onHidden: () => {
          activeBizId.value = void 0;
          activeAlertId.value = '';
          activeAlertContentDetail.value = null;
        },
      });
    };

    /** 保存告警内容数据含义 */
    const handleSaveContentName = (saveInfo: AlertContentNameEditInfo, savePromiseEvent: AlertSavePromiseEvent) => {
      isSaveContentNameActive.value = true;
      savePromiseEvent?.promiseEvent
        ?.then(() => {
          isSaveContentNameActive.value = false;
        })
        .catch(() => {
          isSaveContentNameActive.value = false;
        });
      saveAlertContentName(saveInfo)
        .then(() => {
          savePromiseEvent?.successCallback?.();
        })
        .catch(() => {
          savePromiseEvent?.errorCallback?.();
        });
    };

    /** 告警行操作按钮点击回调 - 分发到对应弹窗 */
    const handleAlertOperationClick = (actionType: IncidentAlertAction, row: AlertTableItem) => {
      clickPopoverTools.hidePopover();
      switch (actionType) {
        case AlertAllActionEnum.CHAT:
          handleChatGroup(row);
          break;
        case AlertAllActionEnum.CONFIRM:
          handleAlertConfirm(row);
          break;
        case AlertAllActionEnum.MANUAL_HANDLING:
          handleManualProcess(row);
          break;
        case AlertAllActionEnum.SHIELD:
          handleQuickShield(row);
          break;
        case AlertAllActionEnum.DISPATCH:
          handleAlarmDispatch(row);
          break;
        default:
          break;
      }
    };

    /** 反馈根因确认 */
    const handleRootCauseConfirm = (row: AlertTableItem) => {
      const entity = (row as any)?.entity;
      if (entity?.is_root) return;
      if ((row as any).is_feedback_root) {
        feedbackIncidentRootApi(true, row);
        return;
      }
      setDialogData(row);
      dialog.rootCauseConfirm.show = true;
    };

    // ==================== 场景渲染器 ====================
    const scenarioInstance = new IncidentAlertScenario({
      clickPopoverTools,
      handleAlertContentDetailShow,
      handleAlertOperationClick,
      handleAlertSliderShowDetail,
      hoverPopoverTools,
      handleRootCauseConfirm,
    });

    /** 转换后的列配置（合并 Scenario 渲染配置） */
    const transformedColumns = computed<TableColumnItem[]>(() => {
      const scenarioColumns = scenarioInstance.getMergedColumnsConfig();
      return tableColumns.value.map(column => {
        const scenarioConfig = scenarioColumns[column.colKey];
        return scenarioConfig ? { ...column, ...scenarioConfig } : column;
      });
    });

    /** 表格 settings 配置 */
    const settings = computed<BkUiSettings>(() => ({
      checked: displayFields.value,
      fields: allFields.value,
      disabled: lockedFields.value,
      hasCheckAll: true,
      showRowSize: false,
    }));

    /** 表格空状态配置 */
    const tableEmpty = computed(() => scenarioInstance.getEmptyConfig());

    /** 表格场景类名 */
    const tableScenarioClassName = computed(() => scenarioInstance.privateClassName || '');

    // ==================== 弹窗操作方法 ====================
    const setDialogData = data => {
      currentData.value = { ...data, ...{ incident_id: incidentDetailData.value?.incident_id } };
      currentIds.value = [data.id];
      currentBizIds.value = [data.bk_biz_id];
    };

    const handleQuickShield = v => {
      setDialogData(v);
      dialog.quickShield.show = true;
      dialog.quickShield.details = [
        {
          severity: v.severity,
          dimension: v.dimensions,
          trigger: v.description,
          alertId: v.id,
          strategy: {
            id: v?.strategy_id as unknown as string,
            name: v?.strategy_name,
          },
        },
      ];
    };

    const handleManualProcess = v => {
      setDialogData(v);
      manualProcessShowChange(true);
    };

    const manualProcessShowChange = (v: boolean) => {
      dialog.manualProcess.show = v;
    };

    const handleChatGroup = v => {
      const { id, assignee, alert_name, bk_biz_id } = v;
      setDialogData(v);
      chatGroupDialog.assignee = assignee || [];
      chatGroupDialog.alertName = alert_name;
      chatGroupDialog.bizId = [bk_biz_id];
      chatGroupDialog.alertIds.splice(0, chatGroupDialog.alertIds.length, id);
      chatGroupShowChange(true);
    };

    const chatGroupShowChange = (show: boolean) => {
      chatGroupDialog.show = show;
    };

    const feedbackIncidentRootApi = (isCancel, data) => {
      const { bk_biz_id } = data;
      const params = {
        id: incidentId.value,
        incident_id: incidentDetailData.value?.incident_id,
        bk_biz_id,
        feedback: {
          incident_root: data.entity.entity_id,
          content: '',
        },
        is_cancel: false,
      };
      if (isCancel) {
        params.is_cancel = true;
      }
      feedbackIncidentRoot(params).then(() => {
        Message({
          theme: 'success',
          message: t('取消反馈成功'),
        });
        incidentRecordOperation({
          incident_id: incidentDetailData.value?.incident_id,
          bk_biz_id,
          operation_type: 'feedback',
          extra_info: {
            feedback_incident_root: '',
            is_cancel: isCancel,
          },
        }).then(res => {
          res && setTimeout(() => emit('refresh'), 2000);
        });
        handleGetTable();
      });
    };

    const handleAlertConfirm = v => {
      setDialogData(v);
      dialog.alarmConfirm.show = true;
    };

    const handleAlarmDispatch = v => {
      setDialogData(v);
      handleAlarmDispatchShowChange(true);
    };

    const handleConfirmAfter = () => {};

    const alarmConfirmChange = v => {
      dialog.alarmConfirm.show = v;
      handleGetTable();
    };

    const handleAlarmDispatchShowChange = v => {
      dialog.alarmDispatch.show = v;
    };

    const handleDebugStatus = (actionIds: number[]) => {
      dialog.manualProcess.actionIds = actionIds;
      dialog.manualProcess.debugKey = random(8);
    };

    const handleMealInfo = (mealInfo: { name: string }) => {
      dialog.manualProcess.mealInfo = mealInfo;
    };

    const quickShieldSuccess = (_v: boolean) => {
      // 快捷屏蔽成功后更新对应行的 is_shielded 和 shield_operator 状态
      const ids = currentIds.value;
      if (!ids?.length) return;
      for (const group of alertData.value) {
        if (!group.alerts?.length) continue;
        for (const alert of group.alerts) {
          if (ids.includes(alert.id)) {
            alert.is_shielded = true;
            alert.shield_operator = [window.username || window.user_name];
          }
        }
      }
      triggerRef(alertData);
    };

    const quickShieldChange = (v: boolean) => {
      dialog.quickShield.show = v;
    };

    // ==================== 数据加载 ====================
    const handleGetTable = () => {
      if (!bkzIds.value || bkzIds.value.length === 0) return;

      tableLoading.value = true;
      exceptionData.value.isError = false;
      exceptionData.value.errorMsg = '';

      const queryString =
        typeof alertIdsData.value === 'object'
          ? (alertIdsData.value as Record<string, any>)?.ids || ''
          : alertIdsData.value;
      const params = {
        bk_biz_ids: bkzIds.value,
        id: incidentId.value,
        query_string: queryString,
      };
      incidentAlertList(params, { needMessage: false })
        .then(res => {
          tableLoading.value = false;
          alertData.value = res;
          nextTick(() => recalcTableMaxHeight());
        })
        .catch(err => {
          tableLoading.value = false;
          alertData.value = [];
          exceptionData.value.isError = true;
          exceptionData.value.errorMsg = err.message || '';
        });
    };

    // ==================== 折叠面板 ====================
    const handleChangeCollapse = ({ id, isCollapse }) => {
      if (isCollapse) {
        collapseId.value = null;
        return;
      }
      collapseId.value = id;
    };

    const handleFeedbackChange = (val: boolean) => {
      dialog.rootCauseConfirm.show = val;
    };

    const refresh = () => {
      emit('refresh');
    };

    // ==================== 列显隐变化回调 ====================
    const onDisplayColFieldsChange = (displayColFields: string[]) => {
      handleDisplayColumnsChange(displayColFields);
    };

    // ==================== 行选择回调 ====================
    /** 行选择变化回调（按 collapse 分组独立） */
    const handleSelectChange = (
      collapseItemId: number | string,
      keys: (number | string)[],
      _options: SelectOptions<unknown>
    ) => {
      selectedRowKeysMap.value = { ...selectedRowKeysMap.value, [collapseItemId]: keys };
    };

    /** 批量操作回调（操作指定 collapse 的选中行） */
    const handleAlertBatchSet = (collapseItemId: number | string, actionType: AlertSelectBatchAction) => {
      const keys = getSelectedRowKeys(collapseItemId);
      if (actionType === AlertAllActionEnum.CANCEL) {
        selectedRowKeysMap.value = { ...selectedRowKeysMap.value, [collapseItemId]: [] };
        return;
      }
      const groupData = alertData.value.find(item => item.id === collapseItemId);
      if (!groupData) return;
      const selectedRows = (groupData.alerts || []).filter(r => keys.includes(r.id));
      if (!selectedRows.length) return;
      const ids = selectedRows.map(r => r.id);
      const bizIds = selectedRows.map(r => r.bk_biz_id);
      const firstRow = selectedRows[0];

      // 除一键拉群外，不允许跨业务批量操作
      if (actionType !== AlertAllActionEnum.CHAT && new Set(bizIds).size > 1) {
        Message({
          message: t('当前不能跨业务批量操作'),
          theme: 'warning',
        });
        return;
      }

      switch (actionType) {
        case AlertAllActionEnum.CONFIRM:
          currentIds.value = ids;
          currentBizIds.value = bizIds;
          currentData.value = { ...firstRow, ...{ incident_id: incidentDetailData.value?.incident_id } };
          dialog.alarmConfirm.show = true;
          break;
        case AlertAllActionEnum.SHIELD:
          currentIds.value = ids;
          currentBizIds.value = bizIds;
          currentData.value = { ...firstRow, ...{ incident_id: incidentDetailData.value?.incident_id } };
          dialog.quickShield.show = true;
          dialog.quickShield.details = selectedRows.map(r => ({
            severity: r.severity,
            dimension: r.dimensions,
            trigger: r.description,
            alertId: r.id,
            strategy: { id: r?.strategy_id as unknown as string, name: r?.strategy_name },
          }));
          break;
        case AlertAllActionEnum.DISPATCH:
          currentIds.value = ids;
          currentBizIds.value = bizIds;
          currentData.value = { ...firstRow, ...{ incident_id: incidentDetailData.value?.incident_id } };
          dialog.alarmDispatch.show = true;
          break;
        case AlertAllActionEnum.CHAT: {
          // 合并所有选中行的 assignee（去重）
          const assignees = selectedRows.reduce((prev, curr) => {
            for (const user of curr?.assignee ?? []) {
              prev.add(user);
            }
            return prev;
          }, new Set<string>());
          currentData.value = { ...firstRow, ...{ incident_id: incidentDetailData.value?.incident_id } };
          chatGroupDialog.assignee = Array.from(assignees);
          chatGroupDialog.alertName = selectedRows.length === 1 ? firstRow.alert_name : '';
          chatGroupDialog.bizId = bizIds;
          chatGroupDialog.alertIds.splice(0, chatGroupDialog.alertIds.length, ...ids);
          chatGroupShowChange(true);
          break;
        }
        default:
          break;
      }
    };

    // ==================== 生命周期 ====================
    onMounted(() => {
      scenarioInstance.initialize?.();
    });

    onUnmounted(() => {
      scenarioInstance.cleanup?.();
      hoverPopoverTools.hidePopover();
      clickPopoverTools.hidePopover();
    });

    watch(
      () => props.alertIdsObject,
      async val => {
        alertIdsData.value = val;
        const validate = await incidentValidateQueryString(
          {
            query_string: replaceSpecialCondition((alertIdsData.value as Record<string, any>)?.ids),
            search_type: 'incident',
          },
          { needMessage: false, needRes: true }
        )
          .then(res => res.result)
          .catch(() => false);
        validate && handleGetTable();
      },
      { deep: true }
    );

    watch(
      () => bkzIds.value,
      (newVal, _oldVal) => {
        if (newVal && newVal.length > 0 && props.searchValidate) {
          handleGetTable();
        }
      },
      { immediate: true }
    );

    return {
      t,
      alertData,
      collapseId,
      dialog,
      tableLoading,
      chatGroupDialog,
      exceptionData,
      transformedColumns,
      settings,
      tableEmpty,
      tableScenarioClassName,
      quickShieldChange,
      handleChangeCollapse,
      alarmConfirmChange,
      quickShieldSuccess,
      handleConfirmAfter,
      handleFeedbackChange,
      handleRootCauseConfirm,
      handleAlarmDispatchShowChange,
      manualProcessShowChange,
      chatGroupShowChange,
      handleMealInfo,
      handleGetTable,
      alertIdsData,
      incidentDetailData,
      currentData,
      currentIds,
      currentBizIds,
      refresh,
      alarmDetailRef,
      tableWrapperRef,
      tableMaxHeight,
      isSingleCollapse,
      handleColumnResizeChange,
      handleDebugStatus,
      onDisplayColFieldsChange,
      alertContentDetailRef,
      activeAlertContentDetail,
      activeAlertId,
      activeBizId,
      handleSaveContentName,
      selectedRowKeysMap,
      getSelectedRowKeys,
      isSelectedFollower,
      handleSelectChange,
      handleAlertBatchSet,
      tableSortMap,
      getTableSort,
      getSortedAlerts,
      handleSortChange,
    };
  },
  render() {
    const alertData = this.alertData.filter(item => item.alerts.length > 0);
    return (
      <Loading
        class='alarm-detail-loading'
        loading={this.tableLoading}
      >
        <div
          ref='alarmDetailRef'
          class={['alarm-detail', { 'bk-scroll-y': !this.isSingleCollapse }]}
        >
          <FeedbackCauseDialog
            data={this.currentData}
            visible={this.dialog.rootCauseConfirm.show}
            onEditSuccess={this.handleGetTable}
            onRefresh={this.refresh}
            onUpdate:isShow={this.handleFeedbackChange}
          />
          <ChatGroup
            alarmEventName={this.chatGroupDialog.alertName}
            alertIds={this.chatGroupDialog.alertIds}
            assignee={this.chatGroupDialog.assignee}
            data={this.currentData}
            show={this.chatGroupDialog.show}
            onRefresh={this.refresh}
            onShowChange={this.chatGroupShowChange}
          />
          <QuickShield
            bizIds={this.currentBizIds}
            data={this.currentData}
            details={this.dialog.quickShield.details}
            ids={this.currentIds}
            show={this.dialog.quickShield.show}
            onChange={this.quickShieldChange}
            onRefresh={this.refresh}
            onSuccess={this.quickShieldSuccess}
          />
          <ManualProcess
            alertIds={this.currentIds}
            bizIds={this.currentBizIds}
            data={this.currentData}
            show={this.dialog.manualProcess.show}
            onDebugStatus={this.handleDebugStatus}
            onMealInfo={this.handleMealInfo}
            onRefresh={this.refresh}
            onShowChange={this.manualProcessShowChange}
          />
          <AlarmDispatch
            alertIds={this.currentIds}
            bizIds={this.currentBizIds}
            data={this.currentData}
            show={this.dialog.alarmDispatch.show}
            onRefresh={this.refresh}
            onShow={this.handleAlarmDispatchShowChange}
          />
          <AlarmConfirm
            bizIds={this.currentBizIds}
            data={this.currentData}
            ids={this.currentIds}
            show={this.dialog.alarmConfirm.show}
            onChange={this.alarmConfirmChange}
            onConfirm={this.handleConfirmAfter}
            onRefresh={this.refresh}
          />
          <div style='display: none;'>
            <AlertContentDetail
              ref='alertContentDetailRef'
              alertContentDetail={this.activeAlertContentDetail}
              alertId={this.activeAlertId}
              bizId={this.activeBizId}
              onSave={this.handleSaveContentName}
            />
          </div>
          {this.alertData.map(item => {
            const groupSelectedKeys = this.getSelectedRowKeys(item.id);
            return item.alerts.length > 0 ? (
              <Collapse
                id={item.id}
                key={item.id}
                collapse={this.collapseId !== item.id}
                num={item.alerts.length}
                title={item.name}
                onChangeCollapse={this.handleChangeCollapse}
              >
                <div
                  ref={this.isSingleCollapse ? 'tableWrapperRef' : undefined}
                  class={`alarm-detail-table alarm-table alarm-table-container ${this.tableScenarioClassName}`}
                >
                  <CommonTable
                    firstFullRow={
                      groupSelectedKeys?.length
                        ? () =>
                            (
                              <AlertSelectionToolbar
                                class='alarm-table-first-full-row'
                                isSelectedFollower={this.isSelectedFollower(item.id)}
                                selectedRowKeys={groupSelectedKeys}
                                onClickAction={(actionType: AlertSelectBatchAction) =>
                                  this.handleAlertBatchSet(item.id, actionType)
                                }
                              />
                            ) as unknown as SlotReturnValue
                        : null
                    }
                    columns={this.transformedColumns}
                    data={this.getSortedAlerts(item.id)}
                    empty={this.tableEmpty}
                    loading={false}
                    maxHeight={this.tableMaxHeight}
                    scroll={{ type: 'virtual' }}
                    selectedRowKeys={groupSelectedKeys}
                    sort={this.getTableSort(item.id)}
                    tableSettings={this.settings}
                    onColumnResizeChange={this.handleColumnResizeChange}
                    onDisplayColFieldsChange={this.onDisplayColFieldsChange}
                    onSelectChange={(keys: (number | string)[], options: SelectOptions<unknown>) =>
                      this.handleSelectChange(item.id, keys, options)
                    }
                    onSortChange={(sort: string | string[]) => this.handleSortChange(item.id, sort)}
                  />
                </div>
              </Collapse>
            ) : (
              ''
            );
          })}
          {alertData.length === 0 && (
            <ExceptionComp
              errorMsg={this.exceptionData.errorMsg}
              imgHeight={160}
              isError={this.exceptionData.isError}
              title={this.exceptionData.isError ? this.t('查询异常') : this.t('搜索数据为空')}
            />
          )}
        </div>
      </Loading>
    );
  },
});
