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
  type ShallowRef,
  computed,
  defineComponent,
  onBeforeMount,
  shallowRef,
  useTemplateRef,
  watch,
} from 'vue';

import { commonPageSizeSet, convertDurationArray, tryURLDecodeParse } from 'monitor-common/utils';
import FavoriteBox, {
  type IFavorite,
  type IFavoriteGroup,
  EditFavorite,
} from 'trace/pages/trace-explore/components/favorite-box';
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
import QuickFiltering from './components/quick-filtering';
import { useAlarmTable } from './composables/use-alarm-table';
import { useAlertDialogs } from './composables/use-alert-dialogs';
import { useQuickFilter } from './composables/use-quick-filter';
import { useAlarmTableColumns } from './composables/use-table-columns';
import {
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
import { handleTransformToTimestamp } from 'trace/components/time-range/utils';
import { useI18n } from 'vue-i18n';

import { saveAlertContentName } from './services/alert-services';

import type { AlertSavePromiseEvent } from './components/alarm-table/components/alert-content-detail/alert-content-detail';

import './alarm-center.scss';

export default defineComponent({
  name: 'AlarmCenter',
  setup() {
    const { t } = useI18n();
    const router = useRouter();
    const route = useRoute();
    const alarmStore = useAlarmCenterStore();
    const appStore = useAppStore();
    const {
      handleGetUserConfig: handleGetResidentSettingUserConfig,
      handleSetUserConfig: handleSetResidentSettingUserConfig,
    } = useUserConfig();

    const { quickFilterList, quickFilterLoading } = useQuickFilter();
    const { data, loading, total, page, pageSize, ordering } = useAlarmTable();
    const {
      tableColumns: tableSourceColumns,
      storageColumns,
      allTableFields,
      lockedTableFields,
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
    } = useAlertDialogs(data as unknown as ShallowRef<AlertTableItem[]>);

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
      };
    });

    const isCollapsed = shallowRef(false);
    const alarmId = shallowRef<string>('');
    const alarmDetailShow = shallowRef(false);
    /** table 选中的 rowKey 数组 */
    const selectedRowKeys = shallowRef<string[]>([]);
    const defaultActiveRowKeys = computed(() => {
      return alarmId.value ? [alarmId.value] : [];
    });
    /* 是否是所选中告警记录行的关注人 */
    const isSelectedFollower = shallowRef(false);

    /** 是否展示收藏夹 */
    const isShowFavorite = shallowRef(false);
    const editFavoriteData = shallowRef<IFavoriteGroup['favorites'][number]>(null);
    const editFavoriteShow = shallowRef(false);
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

    const updateIsCollapsed = (v: boolean) => {
      isCollapsed.value = v;
    };
    /** 快捷筛选 */
    const handleFilterValueChange = (filterValue: CommonCondition[]) => {
      handleCurrentPageChange(1);
      alarmStore.quickFilterValue = filterValue;
    };
    /** 告警分析添加条件 */
    const handleAddCondition = (condition: CommonCondition) => {
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
    };
    /** 查询语句变化 */
    const handleQueryStringChange = (queryString: string) => {
      alarmStore.queryString = queryString;
    };
    /** 查询模式变化 */
    const handleFilterModeChange = (mode: EMode) => {
      handleCurrentPageChange(1);
      alarmStore.filterMode = mode;
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
      return {
        from: alarmStore.timeRange[0],
        to: alarmStore.timeRange[1],
        timezone: alarmStore.timezone,
        refreshInterval: String(alarmStore.refreshInterval),
        queryString: alarmStore.queryString,
        conditions: JSON.stringify(alarmStore.conditions),
        residentCondition: JSON.stringify(alarmStore.residentCondition),
        quickFilterValue: JSON.stringify(alarmStore.quickFilterValue),
        filterMode: alarmStore.filterMode,
        alarmType: alarmStore.alarmType,
        alarmId: alarmId.value,
        bizIds: JSON.stringify(alarmStore.bizIds),
        currentPage: page.value,
        sortOrder: ordering.value,
        showDetail: JSON.stringify(alarmDetailShow.value),
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
        alarmId: alarmIdParams,
        favorite_id: favoriteId,
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
        }
        alarmStore.filterMode = (filterMode as EMode) || EMode.ui;

        /** 兼容事件中心的bizIds */
        alarmStore.bizIds =
          typeof bizIds === 'string' ? tryURLDecodeParse(bizIds, [-1]) : bizIds.map(item => Number(item));
        ordering.value = (sortOrder as string) || '';
        page.value = Number(currentPage || 1);
        if (favoriteId) {
          defaultFavoriteId.value = Number(favoriteId);
        }
        isShowFavorite.value = JSON.parse(localStorage.getItem(ALARM_CENTER_SHOW_FAVORITE) || 'false');
        alarmDetailShow.value = JSON.parse((showDetail as string) || 'false');
        alarmId.value = (alarmIdParams as string) || '';
        alarmStore.initAlarmService();
      } catch (error) {
        console.log('route query:', error);
      }
    }

    /**
     * 展示告警详情
     */
    function handleShowAlertDetail(id: string, defaultTab?: string) {
      alarmDetailDefaultTab.value = defaultTab || '';
      alarmId.value = id;
      handleDetailShowChange(true);
    }

    /**  展示处理记录详情  */
    function handleShowActionDetail(id: string) {
      alarmId.value = id;
      handleDetailShowChange(true);
    }

    function handleDetailShowChange(show: boolean) {
      alarmDetailShow.value = show;
      if (!show) {
        alarmId.value = '';
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
      const index = data.value.findIndex(item => item.id === alarmId.value);
      alarmId.value = (data.value as AlertTableItem[])[index === 0 ? data.value.length - 1 : index - 1].id;
    };

    /** 下一个详情 */
    const handleNextDetail = () => {
      const index = data.value.findIndex(item => item.id === alarmId.value);
      alarmId.value = (data.value as AlertTableItem[])[index === data.value.length - 1 ? 0 : index + 1].id;
    };

    /**
     * @method autoShowAlertDialog 自动打开告警确认 | 告警屏蔽 dialog
     * @description 当移动端的 告警通知 中点击 告警确认 | 告警屏蔽，进入页面时，需要自动打开 告警确认 | 告警屏蔽 dialog
     * @returns {boolean} 是否自动打开了告警确认 | 告警屏蔽 dialog
     */
    const autoShowAlertDialog = () => {
      const alertAction = route?.query?.autoShowAlertAction as AlertAllActionEnum;
      const isCanAutoShowAlertDialog = CAN_AUTO_SHOW_ALERT_DIALOG_ACTIONS.includes(alertAction);
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
      console.log(data);
      currentFavorite.value = data || null;
      handleCurrentPageChange(1);
      if (data) {
        const favoriteConfig = data?.config;
        alarmStore.timezone = favoriteConfig?.componentData?.timezone || getDefaultTimezone();
        alarmStore.timeRange = favoriteConfig?.componentData?.timeRange || [];
        alarmStore.refreshInterval = favoriteConfig?.componentData?.refreshInterval || -1;
        alarmStore.queryString = favoriteConfig?.queryParams?.query_string || '';
        alarmStore.conditions = favoriteConfig?.componentData?.conditions || [];
        alarmStore.residentCondition = favoriteConfig?.componentData?.residentCondition || [];
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

    watch(
      () => data.value,
      () => {
        if (autoShowAlertDialog()) return;
        // 如非自动打开dialog，则清空selectedRowKeys
        handleSelectedRowKeysChange();
      }
    );
    onBeforeMount(() => {
      getUrlParams();
      setUrlParams();
    });

    return {
      quickFilterList,
      quickFilterLoading,
      isCollapsed,
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
      alarmId,
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
      handleGetResidentSettingUserConfig,
      handleSetResidentSettingUserConfig,
      handleShowAlertDetail,
      handleShowActionDetail,
      getRetrievalFilterValueData,
      handleDetailShowChange,
      handlePreviousDetail,
      handleNextDetail,
      handleFavoriteShowChange,
      handleFavoriteSave,
      handleEditFavoriteShow,
      handleFavoriteChange,
      handleFavoriteOpenBlank,
      handleSaveAlertContentName,
    };
  },
  render() {
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
          />
        </div>
        <div class='alarm-center'>
          <AlarmCenterHeader
            class='alarm-center-header'
            isShowFavorite={this.isShowFavorite}
            onFavoriteShowChange={this.handleFavoriteShowChange}
          />
          <AlarmRetrievalFilter
            class='alarm-center-filters'
            bizIds={this.alarmStore.bizIds}
            bizList={this.appStore.bizList}
            conditions={this.alarmStore.conditions}
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
            onFavoriteSave={this.handleFavoriteSave}
            onFilterModeChange={this.handleFilterModeChange}
            onQuery={this.handleQuery}
            onQueryStringChange={this.handleQueryStringChange}
            onResidentConditionChange={this.handleResidentConditionChange}
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
                        loading={this.quickFilterLoading}
                        onClose={this.updateIsCollapsed}
                        onUpdate:filterValue={this.handleFilterValueChange}
                      />
                    </div>
                  );
                },
                default: () => {
                  return (
                    <div class={CONTENT_SCROLL_ELEMENT_CLASS_NAME}>
                      <div class='chart-trend'>
                        <AlarmTrendChart total={this.total} />
                      </div>
                      {this.alarmStore.alarmType !== AlarmType.INCIDENT && (
                        <div class='alarm-analysis'>
                          <AlarmAnalysis onConditionChange={this.handleAddCondition} />
                        </div>
                      )}
                      <div class='alarm-center-table'>
                        <AlarmTable
                          pagination={{
                            currentPage: this.page,
                            pageSize: this.pageSize,
                            total: this.total,
                          }}
                          tableSettings={{
                            checked: this.storageColumns,
                            fields: this.allTableFields,
                            disabled: this.lockedTableFields,
                          }}
                          columns={this.tableSourceColumns}
                          data={this.data}
                          defaultActiveRowKeys={this.defaultActiveRowKeys}
                          isSelectedFollower={this.isSelectedFollower}
                          loading={this.loading}
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

          <AlarmCenterDetail
            alarmId={this.alarmId}
            alarmType={this.alarmStore.alarmType}
            defaultTab={this.alarmDetailDefaultTab}
            show={this.alarmDetailShow}
            showStepBtn={this.data.length > 1}
            onNext={this.handleNextDetail}
            onPrevious={this.handlePreviousDetail}
            onUpdate:show={this.handleDetailShowChange}
          />

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
        </div>
        <EditFavorite
          key={this.favoriteType}
          data={this.editFavoriteData}
          isCreate={true}
          isShow={this.editFavoriteShow}
          onClose={() => this.handleEditFavoriteShow(false)}
          onSuccess={() => this.handleEditFavoriteShow(false)}
        />
      </div>
    );
  },
});
