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

import { commonPageSizeGet } from 'monitor-common/utils';
import { handleTransformToTimestamp } from 'trace/components/time-range/utils';

import AlarmTable from '../../../../components/alarm-table/alarm-table';
import AlertOperationDialogs from '../../../../components/alert-operation-dialogs/alert-operation-dialogs';
import { useAlertDialogs } from '../../../../composables/use-alert-dialogs';
import { type AlertTableItem, type CommonCondition, AlarmType } from '../../../../typings';
import { useAlarmTableColumns } from './use-table-columns';
import { AlarmServiceFactory } from '@/pages/alarm-center/services/factory';

import type { BkUiSettings } from '@blueking/tdesign-ui';

import './issues-detail-alarm-table.scss';

export default defineComponent({
  name: 'IssuesDetailAlarmTable',
  props: {
    timeRange: {
      type: Array as PropType<string[]>,
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
    /** 业务ID列表 */
    bizIds: {
      type: Array as PropType<number[]>,
      default: () => [],
    },
  },
  emits: {
    showAlertDetail: (_id: string, _defaultTab?: string) => true,
    showActionDetail: (_id: string) => true,
  },
  setup(props, { emit }) {
    // 分页参数
    const pageSize = shallowRef(commonPageSizeGet() ?? 50);
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
      total: total.value,
    }));

    // 获取数据
    const fetchData = async () => {
      // 中止上一次未完成的请求
      if (abortController) {
        abortController.abort();
      }
      // 创建新的中止控制器
      abortController = new AbortController();
      const { signal } = abortController;

      loading.value = true;
      data.value = [];

      const [startTime, endTime] = handleTransformToTimestamp(props.timeRange);

      const params = {
        bk_biz_ids: props.bizIds,
        conditions: props.conditions,
        query_string: props.queryString,
        start_time: startTime,
        end_time: endTime,
        page_size: pageSize.value,
        page: page.value,
        ordering: ordering.value ? [ordering.value] : [],
      };

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
    const handleShowAlertDetail = (id: string, defaultTab?: string) => {
      emit('showAlertDetail', id, defaultTab);
    };

    // 显示处理记录详情
    const handleShowActionDetail = (id: string) => {
      emit('showActionDetail', id);
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
          headerAffixedTop={null}
          horizontalScrollAffixedBottom={null}
          isSelectedFollower={this.isSelectedFollower}
          loading={this.loading}
          pagination={this.pagination}
          scrollContainerSelector={null}
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
          onSaveAlertContentName={() => {
            // 暂不支持保存告警内容名称
          }}
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
