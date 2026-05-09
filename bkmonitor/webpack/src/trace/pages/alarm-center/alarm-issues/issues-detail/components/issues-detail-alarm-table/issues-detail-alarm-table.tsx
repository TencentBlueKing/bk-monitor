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
  type PropType,
  type ShallowRef,
  computed,
  defineComponent,
  onMounted,
  onScopeDispose,
  shallowRef,
  watchEffect,
} from 'vue';

import { Message } from 'bkui-vue';
import { EMode } from 'trace/components/retrieval-filter/typing';
import { handleTransformToTimestamp } from 'trace/components/time-range/utils';
import { useI18n } from 'vue-i18n';

import AlarmTable from '../../../../components/alarm-table/alarm-table';
import AlertOperationDialogs from '../../../../components/alert-operation-dialogs/alert-operation-dialogs';
import { useAlertDialogs } from '../../../../composables/use-alert-dialogs';
import {
  type AlertContentNameEditInfo,
  type AlertTableItem,
  type CommonCondition,
  AlarmType,
} from '../../../../typings';
import { conditionAlertQueryFieldReplace } from '../../utils';
import { useAlarmTableColumns } from './use-table-columns';
import { saveAlertContentName } from '@/pages/alarm-center/services/alert-services';
import { AlarmServiceFactory } from '@/pages/alarm-center/services/factory';

import type { AlertSavePromiseEvent } from '../../../../components/alarm-table/components/alert-content-detail/alert-content-detail';
import type { IssueDetail } from '../../../typing';
import type { BkUiSettings } from '@blueking/tdesign-ui';

import './issues-detail-alarm-table.scss';

export default defineComponent({
  name: 'IssuesDetailAlarmTable',
  props: {
    timeRange: {
      type: Array as PropType<(number | string)[]>,
      default: () => [],
    },
    /** 筛选条件 */
    conditions: {
      type: Array as PropType<CommonCondition[]>,
      default: () => [],
    },
    /** 查询字符串 */
    queryString: {
      type: String,
      default: '',
    },
    detail: {
      type: Object as PropType<IssueDetail>,
      default: () => ({}),
    },
    /** 查询模式 */
    filterMode: {
      type: String as PropType<EMode>,
      default: EMode.ui,
    },
    /** 滚动容器的 CSS 选择器（用于滚动优化及表头/滚动条吸附） */
    scrollContainerSelector: {
      type: String,
    },
    headerAffixedTop: {
      type: Object as PropType<{ [key: string]: number | string; container: string }>,
    },
    horizontalScrollAffixedBottom: {
      type: Object as PropType<{ container: string }>,
    },
    refreshKey: {
      type: String,
      default: '',
    },
  },
  emits: {
    showAlertDetail: (_id: string, _defaultTab?: string) => true,
    showActionDetail: (_id: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    // 分页参数
    const pageSize = shallowRef(100);
    // 当前页
    const page = shallowRef(1);
    // 总条数
    const total = shallowRef(0);
    // 数据
    const data = shallowRef<AlertTableItem[]>([]);
    // 排序
    const ordering = shallowRef('');
    // 是否加载中
    const loading = shallowRef(false);
    // 选中的行
    const selectedRowKeys = shallowRef<string[]>([]);
    // 是否是关注人
    const isSelectedFollower = shallowRef(false);
    // 请求中止控制器
    let abortController: AbortController | null = null;

    // 告警服务实例
    const alarmService = shallowRef(AlarmServiceFactory(AlarmType.ALERT));

    // 表格列配置
    const {
      tableColumns: tableSourceColumns,
      storageColumns,
      allTableFields,
      lockedTableFields,
    } = useAlarmTableColumns();

    // 表格设置
    const tableSettings = computed<Omit<BkUiSettings, 'hasCheckAll'>>(() => ({
      checked: storageColumns.value,
      fields: allTableFields.value,
      disabled: lockedTableFields.value,
    }));

    // 分页配置
    const pagination = computed(() => ({
      currentPage: page.value,
      pageSize: pageSize.value,
    }));

    const commonParams = computed<Record<string, unknown>>(oldValue => {
      const newValue = {
        conditions: [
          { key: 'issue_id', value: [props.detail.id], method: 'eq' },
          ...(props.filterMode === EMode.ui
            ? conditionAlertQueryFieldReplace(props.conditions, props.detail?.impact_scope || {})
            : []),
        ],
        query_string: props.filterMode === EMode.queryString ? props.queryString : '',
      };
      if (JSON.stringify(oldValue) === JSON.stringify(newValue)) {
        return oldValue;
      }
      return newValue;
    });

    // 获取数据
    const fetchData = async () => {
      if (!props.detail?.id) {
        return;
      }
      // 中止上一次未完成的请求
      if (abortController) {
        abortController.abort();
      }
      // 创建新的中止控制器
      abortController = new AbortController();
      const { signal } = abortController;
      const [startTime, endTime] = handleTransformToTimestamp(props.timeRange);

      const params = {
        bk_biz_id: props.detail.bk_biz_id,
        bk_biz_ids: [props.detail.bk_biz_id],
        ...commonParams.value,
        start_time: startTime,
        end_time: endTime,
        page_size: pageSize.value,
        page: page.value,
        ordering: ordering.value ? [ordering.value] : [],
        // 仅触发watchEffect
        ...(props.refreshKey ? {} : {}),
      };
      loading.value = true;
      data.value = [];

      try {
        const res = await alarmService.value.getFilterTableList(params, { signal });

        // 获取告警关联事件数和关联告警信息
        await alarmService.value.getAlterRelevance(res.data, { signal }).then(result => {
          if (!result) return;
          const { event_count, extend_info } = result;
          for (const item of res.data as unknown as AlertTableItem[]) {
            item.event_count = event_count?.[item.id];
            item.extend_info = extend_info?.[item.id];
          }
        });

        // 检查请求是否已被中止
        if (signal.aborted) return;

        total.value = res.total;
        data.value = res.data as unknown as AlertTableItem[];
      } catch (error) {
        if (!signal.aborted) {
          console.error('Failed to fetch alarm data:', error);
        }
      } finally {
        if (!signal.aborted) {
          loading.value = false;
        }
      }
    };

    // 页码变化
    const handleCurrentPageChange = (newPage: number) => {
      page.value = newPage;
    };

    // 每页条数变化
    const handlePageSizeChange = (newPageSize: number) => {
      pageSize.value = newPageSize;
      page.value = 1;
    };

    // 排序变化
    const handleSortChange = (sort: string | string[]) => {
      ordering.value = Array.isArray(sort) ? sort[0] || '' : sort;
      page.value = 1;
    };

    // 选择变化
    const handleSelectionChange = (keys: string[]) => {
      selectedRowKeys.value = keys;
    };

    // 显示告警详情
    const handleShowAlertDetail = (row: AlertTableItem, defaultTab?: string) => {
      emit('showAlertDetail', row.id, defaultTab);
    };

    // 显示处理记录详情
    const handleShowActionDetail = (id: string) => {
      emit('showActionDetail', id);
    };

    // 保存告警内容名称
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

    // 告警操作弹窗
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

    // 监听参数变化重新获取数据
    onMounted(() => {
      watchEffect(fetchData);
    });

    onScopeDispose(() => {
      if (abortController) {
        abortController.abort();
        abortController = null;
      }
    });

    return {
      pageSize,
      page,
      total,
      data,
      ordering,
      loading,
      selectedRowKeys,
      isSelectedFollower,
      tableSettings,
      pagination,
      tableSourceColumns,
      storageColumns,
      allTableFields,
      lockedTableFields,
      alertDialogShow,
      alertDialogType,
      alertDialogBizId,
      alertDialogIds,
      alertDialogParam,
      handleCurrentPageChange,
      handlePageSizeChange,
      handleSortChange,
      handleSelectionChange,
      handleShowAlertDetail,
      handleShowActionDetail,
      handleSaveAlertContentName,
      handleAlertDialogShow,
      handleAlertDialogHide,
      handleAlertDialogConfirm,
    };
  },
  render() {
    return (
      <div class='issues-detail-alarm-table'>
        <AlarmTable
          columns={this.tableSourceColumns}
          data={this.data}
          defaultActiveRowKeys={[]}
          headerAffixedTop={this.headerAffixedTop}
          horizontalScrollAffixedBottom={this.horizontalScrollAffixedBottom}
          isSelectedFollower={this.isSelectedFollower}
          loading={this.loading}
          pagination={this.pagination}
          scrollContainerSelector={this.scrollContainerSelector}
          selectedRowKeys={this.selectedRowKeys}
          sort={this.ordering}
          tableSettings={this.tableSettings}
          timeRange={this.timeRange}
          onCurrentPageChange={this.handleCurrentPageChange}
          onDisplayColFieldsChange={(displayColFields: string[]) => {
            this.storageColumns = displayColFields;
          }}
          onOpenAlertDialog={this.handleAlertDialogShow}
          onPageSizeChange={this.handlePageSizeChange}
          onSaveAlertContentName={this.handleSaveAlertContentName}
          onSelectionChange={this.handleSelectionChange}
          onShowAlertDetail={this.handleShowAlertDetail}
          onSortChange={this.handleSortChange}
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
          }}
        />
      </div>
    );
  },
});
