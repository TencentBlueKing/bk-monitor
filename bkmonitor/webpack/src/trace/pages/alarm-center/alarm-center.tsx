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
import {
  type ComponentPublicInstance,
  type Ref,
  computed,
  defineComponent,
  inject,
  onBeforeMount,
  shallowRef,
  useTemplateRef,
  watch,
} from 'vue';

import { commonPageSizeSet, convertDurationArray, copyText, tryURLDecodeParse } from 'monitor-common/utils';
import FavoriteBox, {
  type IFavorite,
  type IFavoriteGroup,
  EditFavorite,
} from 'trace/pages/trace-explore/components/favorite-box';
import VueJsonPretty from 'vue-json-pretty';
import { useRoute, useRouter } from 'vue-router';

import { EFieldType, EMode } from '../../components/retrieval-filter/typing';
import { mergeWhereList } from '../../components/retrieval-filter/utils';
import useUserConfig from '../../hooks/useUserConfig';
import { getDefaultTimezone } from '../../i18n/dayjs';
import TraceExploreLayout from '../trace-explore/components/trace-explore-layout';
import AlarmCenterDetail from './alarm-detail/alarm-detail-sideslider';
import AlarmAnalysis from './components/alarm-analysis/alarm-analysis';
import AlarmCenterHeader from './components/alarm-center-header';
import AlarmRetrievalFilter from './components/alarm-retrieval-filter/alarm-retrieval-filter';
import { useAlarmFilter } from './components/alarm-retrieval-filter/hooks/use-alarm-filter';
import AlarmTable from './components/alarm-table/alarm-table';
import AlarmTrendChart from './components/alarm-trend-chart/alarm-trend-chart';
import AlertOperationDialogs from './components/alert-operation-dialogs/alert-operation-dialogs';
import BizPermissionTips from './components/biz-permission-tips/biz-permission-tips';
import QuickFiltering from './components/quick-filtering';
import { useAlarmTable } from './composables/use-alarm-table';
import { useAlertDialogs } from './composables/use-alert-dialogs';
import { useLegacyEventCenterCompat } from './composables/use-legacy-event-center-compat';
import { useQuickFilter } from './composables/use-quick-filter';
import { useAlarmTableColumns } from './composables/use-table-columns';
import {
  type ActionTableItem,
  type AlarmUrlParams,
  type AlertAllActionEnum,
  type AlertContentNameEditInfo,
  type AlertTableItem,
  type CommonCondition,
  AlarmType,
  CAN_AUTO_SHOW_ALERT_DIALOG_ACTIONS,
  CONTENT_SCROLL_ELEMENT_CLASS_NAME,
} from './typings';
import { useAlarmCenterStore } from '@/store/modules/alarm-center';
import { useAppStore } from '@/store/modules/app';

import type { SelectOptions } from '@blueking/tdesign-ui/.';

const ALARM_CENTER_SHOW_FAVORITE = 'ALARM_CENTER_SHOW_FAVORITE';

import { Message } from 'bkui-vue';
import dayjs from 'dayjs';
import { traceGenerateQueryString } from 'monitor-api/modules/apm_trace';
import { handleTransformToTimestamp } from 'trace/components/time-range/utils';
import { useI18n } from 'vue-i18n';

import { type AlarmCenterApmHooks, ALARM_CENTER_APM_HOOKS_KEY } from './alarm-center-apm';
import { useIssuesImpactScopeDrawer } from './alarm-issues/components/issues-impact-scope-drawer/hooks/use-issues-impact-scope-drawer';
import IssuesImpactScopeDrawer from './alarm-issues/components/issues-impact-scope-drawer/issues-impact-scope-drawer';
import { useIssuesDialogs } from './alarm-issues/components/issues-operation-dialogs/hooks/use-issues-dialogs';
import IssuesOperationDialogs from './alarm-issues/components/issues-operation-dialogs/issues-operation-dialogs';
import { IssuesBatchActionEnum } from './alarm-issues/constant';
import IssuesDetailSideSlider from './alarm-issues/issues-detail/issues-detail-sideslider';
import IssuesTable from './alarm-issues/issues-table/issues-table';
import IssuesToolbar from './alarm-issues/issues-toolbar/issues-toolbar';
/* import { exportIssues } from './alarm-issues/services/issues-operations'; */
import { showOperationResult, updateIssuesPriority } from './alarm-issues/services/issues-operations';
import { saveAlertContentName } from './services/alert-services';
import EmptyStatus from '@/components/empty-status/empty-status';

import type { IssueItem, IssuePriorityType, IssuesBatchActionType } from './alarm-issues/typing';
import type { AlertSavePromiseEvent } from './components/alarm-table/components/alert-content-detail/alert-content-detail';

import './alarm-center.scss';

/** 表格固定配置项(表头吸顶、横向滚动条吸底) */
const tableAffixed = { container: `.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}` };
export default defineComponent({
  name: 'AlarmCenter',
  setup() {
    const { t } = useI18n();
    const router = useRouter();
    const route = useRoute();
    const alarmStore = useAlarmCenterStore();
    const appStore = useAppStore();

    const apmHooks = inject<AlarmCenterApmHooks | null>(ALARM_CENTER_APM_HOOKS_KEY, null);

    const {
      handleGetUserConfig: handleGetResidentSettingUserConfig,
      handleSetUserConfig: handleSetResidentSettingUserConfig,
    } = useUserConfig();

    const {
      isFirstInit,
      quickFilterList,
      quickFilterLoading,
      quickFilterEmptyStatusType,
      updateQuickFilterValue,
      handleQuickFilteringOperation,
    } = useQuickFilter();

    const { data, loading, total, page, pageSize, ordering } = useAlarmTable();

    /** 表格分页配置 */
    const pagination = computed(() => ({
      currentPage: page.value,
      pageSize: pageSize.value,
      total: total.value,
    }));
    const {
      tableColumns: tableSourceColumns,
      storageColumns,
      allTableFields,
      lockedTableFields,
      fieldsWidthConfig,
    } = useAlarmTableColumns();

    const {
      alertDialogShow,
      alertDialogType,
      alertDialogBizId,
      alertDialogIds,
      alertDialogParam,
      handleAlertDialogShow,
      handleAlertDialogHide,
      handleAlertDialogConfirm,
    } = useAlertDialogs(data as Ref<AlertTableItem[]>);

    const {
      issuesDialogShow,
      issuesDialogType,
      issuesDialogData,
      issuesDialogParam,
      updateIssueItems,
      handleIssuesDialogShow,
      handleIssuesDialogHide,
      handleIssuesDialogSuccess,
    } = useIssuesDialogs(data as Ref<IssueItem[]>);

    /**
     * @description 直接调用优先级变更接口，无需打开弹窗，成功后原地更新对应 Issue 行数据
     * @param {string} id - Issue ID
     * @param {IssuePriorityType} priority - 目标优先级（P0 / P1 / P2）
     * @returns {void}
     */
    const handleIssuesPriorityChange = async (id: string, priority: IssuePriorityType) => {
      const issuesData = data.value as IssueItem[];
      const targetRow = issuesData.find(item => item.id === id);
      if (!targetRow) return;

      const res = await updateIssuesPriority({
        issues: [{ bk_biz_id: targetRow.bk_biz_id, issue_id: id }],
        priority,
      });

      showOperationResult(res, t('修改成功'));

      updateIssueItems(res.succeeded);
    };

    /** 兼容旧版「事件中心」(fta-solutions/pages/event) 的 URL 入口 */
    const {
      legacyBatchAction,
      shouldAutoOpenFirstDetail,
      showPermissionTips,
      applyLegacyQueryStringInjection,
      applyPromqlIfNeeded,
      setupAutoOpenFirstDetailFlag,
      computeShowPermissionTips,
      dismissPermissionTips,
      handleApplyPermission,
    } = useLegacyEventCenterCompat();

    const favoriteBox = useTemplateRef<ComponentPublicInstance<typeof FavoriteBox>>('favoriteBox');
    const allFavoriteList = computed(() => {
      return favoriteBox.value?.getFavoriteList() || [];
    });
    // 收藏列表（检索条件栏使用）
    const retrievalFavoriteList = computed(() => {
      return allFavoriteList.value.map(item => ({
        ...item,
        config: {
          queryString: item?.config?.queryParams?.query_string || '',
          where: item?.config?.componentData?.conditions || [],
          commonWhere: item?.config?.componentData?.residentCondition || [],
        },
      }));
    });
    /** 默认选择的收藏Id */
    const defaultFavoriteId = shallowRef(null);
    /* 当前选择的收藏项 */
    const currentFavorite = shallowRef(null);
    const alarmDetailDefaultTab = shallowRef('');
    // 当前选择的收藏项（检索条件栏使用）
    const retrievalSelectFavorite = computed(() => {
      if (currentFavorite.value) {
        return {
          commonWhere: currentFavorite.value?.config?.componentData?.residentCondition || [],
          where: currentFavorite.value?.config?.componentData?.conditions || [],
        };
      }
      return null;
    });
    const showResidentBtn = shallowRef(false);

    const isCollapsed = shallowRef(false);
    /* 当前选中的告警id */
    const detailId = shallowRef<string>('');
    /* 当前选中的告警bizId */
    const detailBizId = shallowRef<number>(undefined);
    const alarmDetailShow = shallowRef(false);
    /** table 选中的 rowKey 数组 */
    const selectedRowKeys = shallowRef<string[]>([]);
    const defaultActiveRowKeys = computed(() => {
      return detailId.value ? [detailId.value] : [];
    });
    /* 是否是所选中告警记录行的关注人 */
    const isSelectedFollower = shallowRef(false);

    /** 是否展示收藏夹 */
    const isShowFavorite = shallowRef(false);
    const editFavoriteData = shallowRef<IFavoriteGroup['favorites'][number]>(null);
    const editFavoriteShow = shallowRef(false);

    /** issue 第一个告警时间（用于确认告警详情默认时间范围） */
    const issueFirstAlarmTime = shallowRef<number | string>('');

    const { impactScopeDrawerShow, impactScopeResourceKey, impactScopeResource, handleImpactScopeClick } =
      useIssuesImpactScopeDrawer();

    /**
     * @description 检索栏字段列表
     */
    const retrievalFilterFields = computed(() => {
      const filterFields = [...alarmStore.alarmService.filterFields];
      const spliceIndex = filterFields.findIndex(item => item.name === 'tags');
      if (spliceIndex !== -1) {
        filterFields.splice(
          spliceIndex,
          1,
          ...alarmStore.dimensionTags.map(item => ({
            name: item.id,
            alias: item.name,
            methods: [
              {
                alias: '=',
                value: 'eq',
              },
              {
                alias: '!=',
                value: 'neq',
              },
            ],
            isEnableOptions: true,
            type: EFieldType.keyword,
          }))
        );
      }
      return filterFields;
    });
    const { getRetrievalFilterValueData } = useAlarmFilter(() => {
      const [start, end] = handleTransformToTimestamp(alarmStore.timeRange);
      return {
        alarmType: alarmStore.alarmType,
        commonFilterParams: {
          ...alarmStore.commonFilterParams,
          start_time: start,
          end_time: end,
        },
        filterMode: alarmStore.filterMode,
        fields: retrievalFilterFields.value,
      };
    });
    /**
     * @description 检索栏常驻设置唯一id
     */
    const residentSettingOnlyId = computed(() => {
      return `ALARM_CENTER_RESIDENT_SETTING__${alarmStore.alarmType}`;
    });

    const favoriteType = computed(() => {
      return `alarm_${alarmStore.alarmType}`;
    });

    watch(
      () => favoriteType.value,
      () => {
        defaultFavoriteId.value = null;
        currentFavorite.value = null;
      }
    );

    /** 告警类型切换 */
    const handleAlarmTypeChange = (value: AlarmType) => {
      alarmStore.handleAlarmTypeChange(value);
      isFirstInit.value = true;
      ordering.value = ''; // 清理排序
    };

    const updateIsCollapsed = (v: boolean) => {
      isCollapsed.value = v;
    };

    /** 快捷筛选 */
    const handleFilterValueChange = (filterValue: CommonCondition[], category: string) => {
      handleCurrentPageChange(1);
      alarmStore.lastQuickFilterOperationCategory = category;
      alarmStore.lastQuickFilterOperationCategoryData =
        quickFilterList.value.find(item => item.id === category) || null;
      updateQuickFilterValue(filterValue);
    };
    /** 告警分析添加条件 */
    const handleAddCondition = (condition: CommonCondition) => {
      handleCurrentPageChange(1);
      if (alarmStore.filterMode === EMode.ui) {
        let conditionResult: CommonCondition[] = [condition];
        // 持续时间需要特殊处理
        if (condition.key === 'duration') {
          conditionResult = convertDurationArray(condition.value as string[]);
        }
        alarmStore.conditions = mergeWhereList(
          alarmStore.conditions,
          conditionResult.map(condition => ({
            key: condition.key,
            method: condition.method,
            value: condition.value.map(item => {
              if (item.startsWith('"') && item.endsWith('"')) {
                return item.slice(1, -1);
              }
              return item;
            }),
            ...(alarmStore.conditions.length > 1 ? { condition: 'and' } : {}),
          }))
        );
      } else {
        const queryString = `${alarmStore.queryString ? ' AND ' : ''}${condition.method === 'neq' ? '-' : ''}${condition.key}: ${condition.value[0]}`;
        alarmStore.queryString = queryString;
      }
    };
    /** UI条件变化 */
    const handleConditionChange = (condition: CommonCondition[]) => {
      handleCurrentPageChange(1);
      alarmStore.conditions = condition;
      apmHooks?.onConditionChange?.(condition);
    };
    /** 查询语句变化 */
    const handleQueryStringChange = (queryString: string) => {
      handleCurrentPageChange(1);
      alarmStore.queryString = queryString;
      apmHooks?.onQueryStringChange?.(queryString);
    };
    /** 查询模式变化 */
    const handleFilterModeChange = (mode: EMode) => {
      handleCurrentPageChange(1);
      alarmStore.filterMode = mode;
      apmHooks?.onFilterModeChange?.(mode);
    };
    const handleResidentConditionChange = (condition: CommonCondition[]) => {
      alarmStore.residentCondition = condition;
    };
    /** 查询 */
    const handleQuery = () => {
      handleCurrentPageChange(1);
      alarmStore.refreshImmediate += 1;
    };
    /** 业务变化 */
    const handleBizIdsChange = (bizIds: (number | string)[]) => {
      handleCurrentPageChange(1);
      alarmStore.bizIds = bizIds as number[];
    };

    /** URL参数 */
    const urlParams = computed<AlarmUrlParams>(() => {
      let detailUrlParams = {};

      if (alarmDetailShow.value) {
        detailUrlParams = {
          /** 详情ID */
          detailId: detailId.value,
          detailBizId: detailBizId.value,
          /** 是否展示详情 */
          showDetail: JSON.stringify(alarmDetailShow.value),
          /** issue 首次告警时间 */
          issueFirstAlarmTime: String(issueFirstAlarmTime.value),
        };
      }

      return {
        from: String(alarmStore.timeRange[0]),
        to: String(alarmStore.timeRange[1]),
        timezone: alarmStore.timezone,
        refreshInterval: String(alarmStore.refreshInterval),
        queryString: alarmStore.queryString,
        conditions: JSON.stringify(alarmStore.conditions),
        residentCondition: JSON.stringify(alarmStore.residentCondition),
        quickFilterValue: JSON.stringify(alarmStore.quickFilterValue),
        /** 最后一次操作的快速过滤条件分类数据 */
        lastQuickFilterCategoryData: JSON.stringify(alarmStore.lastQuickFilterOperationCategoryData),
        filterMode: alarmStore.filterMode,
        alarmType: alarmStore.alarmType,
        bizIds: JSON.stringify(alarmStore.bizIds),
        currentPage: page.value,
        sortOrder: ordering.value,
        showResidentBtn: String(showResidentBtn.value),
        ...detailUrlParams,
      };
    });

    watch(
      () => urlParams.value,
      () => {
        setUrlParams();
      }
    );

    function setUrlParams(otherParams: { autoShowAlertAction?: string } = {}) {
      const queryParams = {
        ...urlParams.value,
        ...otherParams,
      };

      const targetRoute = router.resolve({
        query: queryParams,
      });
      /** 防止出现跳转当前地址导致报错 */
      if (targetRoute.fullPath !== route.fullPath) {
        router.replace({
          query: queryParams,
        });
      }
    }

    function getUrlParams() {
      const {
        from,
        to,
        timezone,
        refreshInterval,
        queryString,
        conditions,
        residentCondition,
        quickFilterValue,
        filterMode,
        bizIds,
        alarmType,
        sortOrder,
        currentPage,
        showDetail,
        detailId: queryDetailId,
        detailBizId: queryDetailBizId,
        favorite_id: favoriteId,
        showResidentBtn: queryShowResidentBtn,
        /** 最后一次操作的快速过滤条件分类数据 */
        lastQuickFilterCategoryData,
        /** issue 相关参数 */
        issueFirstAlarmTime: queryIssueFirstAlarmTime,
        /** 以下是兼容事件中心的URL参数 */
        searchType,
        condition,
      } = route.query;

      try {
        alarmStore.alarmType = (alarmType as AlarmType) || (searchType as AlarmType) || AlarmType.ALERT;
        if (from && to) {
          alarmStore.timeRange = [from as string, to as string];
        }
        alarmStore.timezone = (timezone as string) || getDefaultTimezone();
        alarmStore.refreshInterval = Number(refreshInterval) || -1;
        alarmStore.queryString = (queryString as string) || '';
        alarmStore.conditions = tryURLDecodeParse(conditions as string, []);
        alarmStore.residentCondition = tryURLDecodeParse(residentCondition as string, []);
        /** 兼容事件中心的condition */
        if (condition) {
          const params = tryURLDecodeParse(condition as string, {});
          alarmStore.quickFilterValue = Object.keys(params).map(key => ({
            key,
            value: params[key],
          }));
        } else {
          alarmStore.quickFilterValue = tryURLDecodeParse(quickFilterValue as string, []);
          alarmStore.lastQuickFilterOperationCategoryData = tryURLDecodeParse(
            lastQuickFilterCategoryData as string,
            null
          );
          alarmStore.lastQuickFilterOperationCategory = alarmStore.lastQuickFilterOperationCategoryData?.id || '';
        }
        showResidentBtn.value = tryURLDecodeParse<boolean>(queryShowResidentBtn as string, false);
        alarmStore.filterMode = (filterMode as EMode) || EMode.ui;
        if (bizIds) {
          /** 兼容事件中心的bizIds */
          if (typeof bizIds === 'string') {
            alarmStore.bizIds = Number.isNaN(Number(bizIds)) ? tryURLDecodeParse(bizIds, [-1]) : [Number(bizIds)];
          } else {
            alarmStore.bizIds = bizIds.map(item => Number(item));
          }
        }
        ordering.value = (sortOrder as string) || '';
        page.value = Number(currentPage || 1);
        if (favoriteId) {
          defaultFavoriteId.value = Number(favoriteId);
        }
        isShowFavorite.value = JSON.parse(localStorage.getItem(ALARM_CENTER_SHOW_FAVORITE) || 'false');
        alarmDetailShow.value = JSON.parse((showDetail as string) || 'false');
        detailId.value = (queryDetailId as string) || '';
        detailBizId.value = queryDetailBizId ? Number(queryDetailBizId) : null;
        issueFirstAlarmTime.value = (queryIssueFirstAlarmTime as string) || '';
        alarmStore.initAlarmService();
      } catch (error) {
        console.log('route query:', error);
      }
    }

    /**
     * @description 展示告警详情
     * @param {AlertTableItem} row - 告警记录行数据
     * @param {string} defaultTab - 默认选中的 Tab 页签名
     */
    function handleShowAlertDetail(row: AlertTableItem, defaultTab?: string) {
      alarmDetailDefaultTab.value = defaultTab || '';
      detailId.value = row.id;
      detailBizId.value = row.bk_biz_id;
      handleDetailShowChange(true);
    }

    /**
     * @description 展示处理记录详情
     * @param {ActionTableItem} row - 处理记录行数据
     */
    function handleShowActionDetail(row: ActionTableItem) {
      detailId.value = row.id;
      detailBizId.value = row.bk_biz_id as number;
      handleDetailShowChange(true);
    }

    /**
     * @description 展示 Issue 详情
     * @param {string} _id - Issue ID
     */
    const handleIssuesShowDetail = (item: IssueItem) => {
      detailId.value = item.id;
      issueFirstAlarmTime.value = item.first_alert_time;
      detailBizId.value = item.bk_biz_id;
      handleDetailShowChange(true);
    };

    function handleDetailShowChange(show: boolean) {
      alarmDetailShow.value = show;
      if (!show) {
        detailId.value = '';
        alarmDetailDefaultTab.value = '';
      }
    }

    /**
     * @description 表格 -- 处理分页变化
     * @param {number} currentPage 当前页码
     */
    const handleCurrentPageChange = (currentPage: number) => {
      page.value = currentPage;
    };
    /**
     * @description 表格 -- 处理分页大小变化
     * @param {number} size 分页大小
     */
    const handlePageSizeChange = (size: number) => {
      pageSize.value = size;
      commonPageSizeSet(size);
      handleCurrentPageChange(1);
    };
    /**
     * @description 表格 -- 处理排序变化
     * @param {string} sort 排序字段
     */
    const handleSortChange = (sort: string) => {
      ordering.value = sort;
      handleCurrentPageChange(1);
    };
    /**
     * @description 表格 -- 处理选中行变化
     * @param {string[]} keys 选中行 key 数组
     * @param {SelectOptions} options 当前选中操作相关的信息
     */
    const handleSelectedRowKeysChange = (keys?: string[], options?: SelectOptions<any>) => {
      selectedRowKeys.value = keys ?? [];
      isSelectedFollower.value = options?.selectedRowData?.some?.(item => item.followerDisabled);
    };

    /** 上一个详情 */
    const handlePreviousDetail = () => {
      let index = data.value.findIndex(item => item.id === detailId.value);
      index = index === -1 ? 0 : index;
      const target = (data.value as AlertTableItem[])[index === 0 ? data.value.length - 1 : index - 1];
      detailId.value = target.id;
      detailBizId.value = target.bk_biz_id;
    };

    /** 下一个详情 */
    const handleNextDetail = () => {
      let index = data.value.findIndex(item => item.id === detailId.value);
      index = index === -1 ? 0 : index;
      const target = (data.value as AlertTableItem[])[index === data.value.length - 1 ? 0 : index + 1];
      detailId.value = target.id;
      detailBizId.value = target.bk_biz_id;
    };

    /** issues 上一个详情*/
    const handleIssuePreviousDetail = () => {
      let index = data.value.findIndex(item => item.id === detailId.value);
      index = index === -1 ? 0 : index;
      const target = (data.value as IssueItem[])[index === 0 ? data.value.length - 1 : index - 1];
      issueFirstAlarmTime.value = target.first_alert_time;
      detailBizId.value = target.bk_biz_id;
      detailId.value = target.id;
    };

    /** issues 下一个详情 */
    const handleIssueNextDetail = () => {
      let index = data.value.findIndex(item => item.id === detailId.value);
      index = index === -1 ? 0 : index;
      const target = (data.value as IssueItem[])[index === data.value.length - 1 ? 0 : index + 1];
      issueFirstAlarmTime.value = target.first_alert_time;
      detailBizId.value = target.bk_biz_id;
      detailId.value = target.id;
    };

    /**
     * @method autoShowAlertDialog 自动打开告警确认 | 告警屏蔽 dialog
     * @description 当移动端的 告警通知 中点击 告警确认 | 告警屏蔽，进入页面时，需要自动打开 告警确认 | 告警屏蔽 dialog
     * 同时兼容旧版 fta-solutions/pages/event 的 ?batchAction=alarmConfirm|quickShield 入口
     * 旧版安全策略：仅当 queryString 以 `action_id` 开头才自动弹出，避免误操作
     * @returns {boolean} 是否自动打开了告警确认 | 告警屏蔽 dialog
     */
    const autoShowAlertDialog = () => {
      const isLegacy = !!route?.query?.batchAction;
      const alertAction = (route?.query?.autoShowAlertAction as AlertAllActionEnum) || legacyBatchAction.value;
      const isCanAutoShowAlertDialog = CAN_AUTO_SHOW_ALERT_DIALOG_ACTIONS.includes(alertAction);
      if (isLegacy && !/(^action_id).+/g.test(alarmStore.queryString || '')) {
        return false;
      }
      if (
        alarmStore.alarmType !== AlarmType.ALERT ||
        !data.value?.length ||
        alertDialogShow.value ||
        !isCanAutoShowAlertDialog
      ) {
        return false;
      }
      const alertIds = data.value.map(item => item.id as string);
      handleSelectedRowKeysChange(alertIds, {
        type: 'check',
        selectedRowData: data.value,
      });
      handleAlertDialogShow(alertAction, selectedRowKeys.value);
      return true;
    };

    const handleFavoriteShowChange = (isShow: boolean) => {
      isShowFavorite.value = isShow;
      localStorage.setItem(ALARM_CENTER_SHOW_FAVORITE, JSON.stringify(isShow));
    };

    const handleFavoriteSave = async (isEdit: boolean) => {
      const [startTime, endTime] = handleTransformToTimestamp(alarmStore.timeRange);
      const conditions = mergeWhereList(alarmStore.conditions, alarmStore.residentCondition);
      const params = {
        config: {
          componentData: {
            conditions: alarmStore.conditions,
            filterMode: alarmStore.filterMode,
            residentCondition: alarmStore.residentCondition,
            timeRange: alarmStore.timeRange,
            refreshInterval: alarmStore.refreshInterval,
            timezone: alarmStore.timezone,
            quickFilterValue: alarmStore.quickFilterValue,
            bizIds: alarmStore.bizIds,
          },
          queryParams: {
            ...alarmStore.commonFilterParams,
            start_time: startTime,
            end_time: endTime,
            conditions,
          },
        },
      } as any;
      if (isEdit) {
        await alarmStore.alarmService.updateFavorite(currentFavorite.value.id, {
          type: favoriteType.value,
          ...params,
        });
        favoriteBox.value.refreshGroupList();
        Message({
          theme: 'success',
          message: t('收藏成功'),
        });
      } else {
        editFavoriteData.value = params;
        editFavoriteShow.value = true;
      }
    };
    const handleEditFavoriteShow = (isShow: boolean) => {
      editFavoriteShow.value = isShow;
    };

    const handleFavoriteChange = data => {
      currentFavorite.value = data || null;
      handleCurrentPageChange(1);
      if (data) {
        const favoriteConfig = data?.config;
        alarmStore.timezone = favoriteConfig?.componentData?.timezone || getDefaultTimezone();
        alarmStore.timeRange =
          favoriteConfig?.queryParams?.start_time && favoriteConfig?.queryParams?.end_time
            ? [favoriteConfig?.queryParams?.start_time, favoriteConfig?.queryParams?.end_time].map(item => {
                return dayjs(item * 1000).format('YYYY-MM-DD HH:mm:ssZZ');
              })
            : favoriteConfig?.componentData?.timeRange || [];
        alarmStore.refreshInterval = favoriteConfig?.componentData?.refreshInterval || -1;
        alarmStore.queryString = favoriteConfig?.queryParams?.query_string || '';
        alarmStore.conditions = favoriteConfig?.queryParams?.conditions || [];
        alarmStore.residentCondition = [];
        alarmStore.quickFilterValue = favoriteConfig?.componentData?.quickFilterValue || [];
        alarmStore.filterMode = favoriteConfig?.componentData?.filterMode || EMode.ui;
        alarmStore.bizIds = favoriteConfig?.componentData?.bizIds || [-1];
      } else {
        alarmStore.conditions = [];
        alarmStore.residentCondition = [];
        alarmStore.quickFilterValue = [];
        alarmStore.queryString = '';
        defaultFavoriteId.value = null;
      }
    };

    /** 收藏夹新开标签页 */
    const handleFavoriteOpenBlank = data => {
      const href = `${location.origin}${location.pathname}?bizId=${appStore.bizId}#${route.path}`;
      window.open(`${href}?favorite_id=${data.id}`, '_blank');
    };

    /**
     * @description 保存告警内容数据含义
     * @param {AlertContentNameEditInfo} saveInfo 保存接口参数信息
     * @param {AlertSavePromiseEvent['promiseEvent']} savePromiseEvent.promiseEvent Promise 对象，用于告诉 操作发起者 接口请求状态
     * @param {AlertSavePromiseEvent['errorCallback']} savePromiseEvent.errorCallback Promise.reject 方法，用于告诉 操作发起者 接口请求失败
     * @param {AlertSavePromiseEvent['successCallback']} savePromiseEvent.successCallback Promise.resolve 方法，用于告诉 操作发起者 接口请求成功
     */
    const handleSaveAlertContentName = (
      saveInfo: AlertContentNameEditInfo,
      savePromiseEvent: AlertSavePromiseEvent
    ) => {
      saveAlertContentName(saveInfo)
        .then(() => {
          savePromiseEvent?.successCallback?.();
          const targetRow = data.value.find(item => item.id === saveInfo.alert_id) as AlertTableItem;
          const alertContent = targetRow?.items?.[0];
          if (alertContent) {
            alertContent.name = saveInfo.data_meaning;
          }
          Message({
            message: t('更新成功'),
            theme: 'success',
          });
        })
        .catch(() => {
          savePromiseEvent?.errorCallback?.();
          Message({
            message: t('更新失败'),
            theme: 'error',
          });
        });
    };

    const handleShowResidentBtnChange = (val: boolean) => {
      showResidentBtn.value = val;
    };

    const handleCopyWhereQueryString = async (whereParams: CommonCondition[]) => {
      const filters = whereParams.map(item => {
        if (item.key === '*') {
          return {
            ...item,
            operator: 'equal',
            options: {},
          };
        }
        const type = retrievalFilterFields.value.find(v => v.name === item.key)?.type || 'keyword';
        return {
          ...item,
          value: [EFieldType.integer, EFieldType.long].includes(type as EFieldType)
            ? item.value.map(v => {
                const numberV = Number(v);
                return numberV === 0 ? 0 : numberV || v;
              })
            : item.value,
          operator: item.method,
        };
      });
      if (filters.length) {
        const copyStr = await traceGenerateQueryString({
          filters,
        }).catch(() => {
          return '';
        });
        if (copyStr) {
          copyText(copyStr, msg => {
            Message({
              message: msg,
              theme: 'error',
            });
            return;
          });
          Message({
            message: t('复制成功'),
            theme: 'success',
          });
        }
      }
    };

    watch(
      () => data.value,
      () => {
        if (autoShowAlertDialog()) return;
        /** 旧版「移动端告警通知/首页搜索」入口要求自动展开第一条数据的详情 */
        if (shouldAutoOpenFirstDetail.value && data.value?.length) {
          shouldAutoOpenFirstDetail.value = false;
          handleShowAlertDetail(data.value[0] as AlertTableItem);
          return;
        }
        // 如非自动打开dialog，则清空selectedRowKeys
        handleSelectedRowKeysChange();
      }
    );
    /** 业务变化时刷新权限提示 */
    watch(
      () => alarmStore.bizIds,
      () => computeShowPermissionTips()
    );
    onBeforeMount(async () => {
      getUrlParams();
      /** 旧 URL 兼容：actionId / collectId / alertId / metricId 注入 queryString */
      applyLegacyQueryStringInjection();
      setupAutoOpenFirstDetailFlag();
      computeShowPermissionTips();
      /** PromQL 异步转换 queryString，需在首次表格请求触发前完成 */
      await applyPromqlIfNeeded();
      setUrlParams();
    });
    return {
      apmHooks,
      isFirstInit,
      quickFilterList,
      quickFilterLoading,
      quickFilterEmptyStatusType,
      isCollapsed,
      pagination,
      data,
      loading,
      total,
      page,
      pageSize,
      ordering,
      tableSourceColumns,
      selectedRowKeys,
      defaultActiveRowKeys,
      isSelectedFollower,
      storageColumns,
      allTableFields,
      lockedTableFields,
      alarmStore,
      appStore,
      retrievalFilterFields,
      residentSettingOnlyId,
      detailId,
      detailBizId,
      alarmDetailShow,
      alertDialogShow,
      alertDialogType,
      alertDialogBizId,
      alertDialogIds,
      alertDialogParam,
      isShowFavorite,
      editFavoriteData,
      editFavoriteShow,
      favoriteType,
      retrievalFavoriteList,
      retrievalSelectFavorite,
      defaultFavoriteId,
      alarmDetailDefaultTab,
      showResidentBtn,
      issueFirstAlarmTime,
      impactScopeDrawerShow,
      impactScopeResourceKey,
      impactScopeResource,
      handleImpactScopeClick,
      setUrlParams,
      handleSelectedRowKeysChange,
      handleAlertDialogShow,
      handleAlertDialogHide,
      handleAlertDialogConfirm,
      handleFilterValueChange,
      updateIsCollapsed,
      handleAddCondition,
      handleConditionChange,
      handleQueryStringChange,
      handleFilterModeChange,
      handleResidentConditionChange,
      handleQuery,
      handleBizIdsChange,
      handleCurrentPageChange,
      handlePageSizeChange,
      handleSortChange,
      fieldsWidthConfig,
      handleGetResidentSettingUserConfig,
      handleSetResidentSettingUserConfig,
      handleShowAlertDetail,
      handleShowActionDetail,
      getRetrievalFilterValueData,
      handleDetailShowChange,
      handlePreviousDetail,
      handleNextDetail,
      handleAlarmTypeChange,
      handleFavoriteShowChange,
      handleFavoriteSave,
      handleEditFavoriteShow,
      handleFavoriteChange,
      handleFavoriteOpenBlank,
      handleSaveAlertContentName,
      handleShowResidentBtnChange,
      handleQuickFilteringOperation,
      handleIssuesDialogShow,
      handleIssuesDialogHide,
      handleIssuesDialogSuccess,
      issuesDialogShow,
      issuesDialogType,
      issuesDialogData,
      issuesDialogParam,
      handleIssuesShowDetail,
      handleIssuesPriorityChange,
      handleIssuePreviousDetail,
      handleIssueNextDetail,
      handleCopyWhereQueryString,
      showPermissionTips,
      dismissPermissionTips,
      handleApplyPermission,
    };
  },
  render() {
    const renderFavoriteQuery = (favoriteType: string) => {
      return favoriteType === `alarm_${AlarmType.ISSUES}`
        ? params => {
            const queryParams = params?.config?.queryParams || {};
            const filterMode = params?.config?.componentData?.filterMode || EMode.ui;
            if (filterMode === EMode.queryString || queryParams?.query_string) {
              return <span>{queryParams.query_string}</span>;
            }
            if (filterMode === EMode.ui || queryParams?.conditions?.length) {
              return (
                <VueJsonPretty
                  data={queryParams}
                  deep={5}
                />
              );
            }
            return '*';
          }
        : undefined;
    };
    return (
      <div class='alarm-center-page'>
        <div
          style={{ display: this.isShowFavorite ? 'block' : 'none' }}
          class='alarm-center-favorite-box'
        >
          <FavoriteBox
            key={this.favoriteType}
            ref='favoriteBox'
            defaultFavoriteId={this.defaultFavoriteId}
            type={this.favoriteType as IFavorite}
            onChange={this.handleFavoriteChange}
            onClose={() => this.handleFavoriteShowChange(false)}
            onOpenBlank={this.handleFavoriteOpenBlank}
          >
            {{
              renderFavoriteQuery: renderFavoriteQuery(this.favoriteType),
            }}
          </FavoriteBox>
        </div>
        <div class='alarm-center'>
          {!this.apmHooks && (
            <AlarmCenterHeader
              class='alarm-center-header'
              isShowFavorite={this.isShowFavorite}
              onAlarmTypeChange={this.handleAlarmTypeChange}
              onFavoriteShowChange={this.handleFavoriteShowChange}
            />
          )}
          <AlarmRetrievalFilter
            class='alarm-center-filters'
            bizIds={this.alarmStore.bizIds}
            bizList={this.appStore.bizList}
            conditions={this.alarmStore.conditions}
            defaultShowResidentBtn={this.showResidentBtn}
            favoriteList={this.retrievalFavoriteList}
            fields={this.retrievalFilterFields}
            filterMode={this.alarmStore.filterMode}
            getValueFn={this.getRetrievalFilterValueData}
            handleGetUserConfig={this.handleGetResidentSettingUserConfig}
            handleSetUserConfig={this.handleSetResidentSettingUserConfig}
            needIncidentOption={this.alarmStore.alarmType === AlarmType.INCIDENT}
            queryString={this.alarmStore.queryString}
            residentCondition={this.alarmStore.residentCondition}
            residentSettingOnlyId={this.residentSettingOnlyId}
            selectFavorite={this.retrievalSelectFavorite}
            onBizIdsChange={this.handleBizIdsChange}
            onConditionChange={this.handleConditionChange}
            onCopyWhere={this.handleCopyWhereQueryString}
            onFavoriteSave={this.handleFavoriteSave}
            onFilterModeChange={this.handleFilterModeChange}
            onQuery={this.handleQuery}
            onQueryStringChange={this.handleQueryStringChange}
            onResidentConditionChange={this.handleResidentConditionChange}
            onShowResidentBtnChange={this.handleShowResidentBtnChange}
          />
          <BizPermissionTips
            show={this.showPermissionTips}
            onApply={this.handleApplyPermission}
            onClose={this.dismissPermissionTips}
          />
          <div class='alarm-center-main'>
            <TraceExploreLayout
              class='alarm-center-layout'
              v-slots={{
                aside: () => {
                  return (
                    <div class='quick-filtering'>
                      <QuickFiltering
                        filterList={this.quickFilterList}
                        filterValue={this.alarmStore.quickFilterValue}
                        isFilterEmptyItem={false}
                        isFirstInit={this.isFirstInit}
                        loading={this.quickFilterLoading}
                        onClose={this.updateIsCollapsed}
                        onUpdate:filterValue={this.handleFilterValueChange}
                      >
                        {{
                          empty: () => (
                            <EmptyStatus
                              type={this.quickFilterEmptyStatusType}
                              onOperation={this.handleQuickFilteringOperation}
                            />
                          ),
                        }}
                      </QuickFiltering>
                    </div>
                  );
                },
                default: () => {
                  return (
                    <div class={CONTENT_SCROLL_ELEMENT_CLASS_NAME}>
                      {this.alarmStore.alarmType !== AlarmType.ISSUES && (
                        <div class='chart-trend'>
                          <AlarmTrendChart total={this.total} />
                        </div>
                      )}
                      {![AlarmType.INCIDENT, AlarmType.ISSUES].includes(this.alarmStore.alarmType) && (
                        <div class='alarm-analysis'>
                          <AlarmAnalysis onConditionChange={this.handleAddCondition} />
                        </div>
                      )}
                      <div class='alarm-center-table'>
                        {this.alarmStore.alarmType === AlarmType.ISSUES ? (
                          <IssuesToolbar
                            batchAction={action => this.handleIssuesDialogShow(action, this.selectedRowKeys)}
                            issuesIds={this.selectedRowKeys}
                            /* onExport={async () => {
                              const selectedIds = new Set(this.selectedRowKeys);
                              const issues = (this.data as IssueItem[])
                                .filter(item => selectedIds.has(item.id))
                                .map(item => ({ bk_biz_id: item.bk_biz_id, issue_id: item.id }));
                              await exportIssues(issues);
                              Message({ theme: 'success', message: 'TODO 导出待联调' });
                            }} */
                          >
                            <IssuesTable
                              showEmptyOperation={
                                this.alarmStore.filterMode === EMode.ui
                                  ? this.alarmStore.conditions.length > 0 ||
                                    this.alarmStore.residentCondition.length > 0
                                  : this.alarmStore.queryString !== ''
                              }
                              columns={this.tableSourceColumns}
                              data={this.data as IssueItem[]}
                              headerAffixedTop={tableAffixed}
                              horizontalScrollAffixedBottom={tableAffixed}
                              loading={this.loading}
                              pagination={this.pagination}
                              scrollContainerSelector={`.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`}
                              selectedRowKeys={this.selectedRowKeys}
                              sort={this.ordering}
                              onAction={(type: IssuesBatchActionType, id: string) =>
                                this.handleIssuesDialogShow(type, id)
                              }
                              onAssignClick={(id, data) =>
                                this.handleIssuesDialogShow(IssuesBatchActionEnum.ASSIGN, id, data)
                              }
                              onClearFilter={() => {
                                if (this.alarmStore.filterMode === EMode.ui) {
                                  this.handleConditionChange([]);
                                  this.handleResidentConditionChange([]);
                                  return;
                                }
                                this.handleQueryStringChange('');
                              }}
                              onCurrentPageChange={this.handleCurrentPageChange}
                              onImpactScopeClick={this.handleImpactScopeClick}
                              onPageSizeChange={this.handlePageSizeChange}
                              onPriorityChange={(id: string, priority: IssuePriorityType) =>
                                this.handleIssuesPriorityChange(id, priority)
                              }
                              onSelectionChange={this.handleSelectedRowKeysChange}
                              onShowDetail={this.handleIssuesShowDetail}
                              onSortChange={sort => this.handleSortChange(sort as string)}
                            />
                          </IssuesToolbar>
                        ) : (
                          <AlarmTable
                            tableSettings={{
                              checked: this.storageColumns,
                              fields: this.allTableFields,
                              disabled: this.lockedTableFields,
                            }}
                            columns={this.tableSourceColumns}
                            data={this.data}
                            defaultActiveRowKeys={this.defaultActiveRowKeys}
                            headerAffixedTop={tableAffixed}
                            horizontalScrollAffixedBottom={tableAffixed}
                            isSelectedFollower={this.isSelectedFollower}
                            loading={this.loading}
                            pagination={this.pagination}
                            scrollContainerSelector={`.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`}
                            selectedRowKeys={this.selectedRowKeys}
                            sort={this.ordering}
                            timeRange={this.alarmStore.timeRange}
                            onCurrentPageChange={this.handleCurrentPageChange}
                            onDisplayColFieldsChange={displayColFields => {
                              this.storageColumns = displayColFields;
                            }}
                            onOpenAlertDialog={this.handleAlertDialogShow}
                            onPageSizeChange={this.handlePageSizeChange}
                            onSaveAlertContentName={this.handleSaveAlertContentName}
                            onSelectionChange={this.handleSelectedRowKeysChange}
                            onShowActionDetail={this.handleShowActionDetail}
                            onShowAlertDetail={this.handleShowAlertDetail}
                            onSortChange={sort => this.handleSortChange(sort as string)}
                          />
                        )}
                      </div>
                    </div>
                  );
                },
              }}
              initialDivide={208}
              isCollapsed={this.isCollapsed}
              maxWidth={500}
              minWidth={160}
              onUpdate:isCollapsed={this.updateIsCollapsed}
            />
          </div>
          {this.alarmStore.alarmType === AlarmType.ISSUES ? (
            <IssuesDetailSideSlider
              firstAlarmTime={this.issueFirstAlarmTime}
              issueBizId={this.detailBizId}
              issueId={this.detailId}
              show={this.alarmDetailShow}
              showStepBtn={this.data.length > 1}
              onNext={this.handleIssueNextDetail}
              onPrevious={this.handleIssuePreviousDetail}
              onUpdate:show={this.handleDetailShowChange}
            />
          ) : (
            <AlarmCenterDetail
              alarmBizId={this.detailBizId}
              alarmId={this.detailId}
              alarmType={this.alarmStore.alarmType}
              defaultTab={this.alarmDetailDefaultTab}
              show={this.alarmDetailShow}
              showStepBtn={this.data.length > 1}
              onNext={this.handleNextDetail}
              onPrevious={this.handlePreviousDetail}
              onUpdate:show={this.handleDetailShowChange}
            />
          )}

          <AlertOperationDialogs
            alarmBizId={this.alertDialogBizId}
            alarmIds={this.alertDialogIds}
            dialogParam={this.alertDialogParam}
            dialogType={this.alertDialogType}
            show={this.alertDialogShow}
            onConfirm={this.handleAlertDialogConfirm}
            onUpdate:show={() => {
              this.handleAlertDialogHide();
              this.setUrlParams({ autoShowAlertAction: '' });
            }}
          />

          <IssuesOperationDialogs
            dialogParam={this.issuesDialogParam}
            dialogType={this.issuesDialogType}
            issuesData={this.issuesDialogData}
            show={this.issuesDialogShow}
            onSuccess={this.handleIssuesDialogSuccess}
            onUpdate:show={(v: boolean) => {
              if (!v) {
                this.handleIssuesDialogHide();
              }
            }}
          />

          <IssuesImpactScopeDrawer
            resource={this.impactScopeResource}
            resourceKey={this.impactScopeResourceKey}
            show={this.impactScopeDrawerShow}
            onFilterByInstance={this.handleAddCondition}
            onUpdate:show={(v: boolean) => {
              if (v) return;
              this.handleImpactScopeClick();
            }}
          />
        </div>
        <EditFavorite
          key={this.favoriteType}
          data={this.editFavoriteData}
          isCreate={true}
          isShow={this.editFavoriteShow}
          onClose={() => this.handleEditFavoriteShow(false)}
          onSuccess={() => this.handleEditFavoriteShow(false)}
        >
          {{
            renderFavoriteQuery: renderFavoriteQuery(this.favoriteType),
          }}
        </EditFavorite>
      </div>
    );
  },
});
