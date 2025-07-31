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
  type PropType,
  computed,
  ref as deepRef,
  defineComponent,
  onBeforeUnmount,
  onMounted,
  shallowRef,
  toValue,
  useTemplateRef,
  watch,
} from 'vue';

import { useRouter } from 'vue-router';

import { ALERT_STORAGE_KEY } from '../../services/alert-services';
import { INCIDENT_STORAGE_KEY } from '../../services/incident-services';
import {
  type AlertTableItem,
  type TableColumnItem,
  type TablePagination,
  CONTENT_SCROLL_ELEMENT_CLASS_NAME,
} from '../../typings';
import { AlertSelectAction } from '../../typings/constants';
import AlertContentDetail from './components/alert-content-detail/alert-content-detail';
import AlertSelectionToolbar from './components/alert-selection-toolbar/alert-selection-toolbar';
import CommonTable from './components/common-table/common-table';
import { usePopover } from './hooks/use-popover';
import { useScenarioRenderer } from './hooks/use-scenario-renderer';

import type { ActionScenario } from './scenarios/action-scenario';
import type { AlertScenario } from './scenarios/alert-scenario';
import type { IncidentScenario } from './scenarios/incident-scenario';
import type { BkUiSettings } from '@blueking/tdesign-ui/.';
import type { SelectOptions, SlotReturnValue } from 'tdesign-vue-next';

import './alarm-table.scss';

export default defineComponent({
  name: 'AlarmTable',
  props: {
    /** 表格列配置 */
    columns: {
      type: Array as PropType<TableColumnItem[]>,
      default: () => [],
    },
    /** 表格分页属性类型 */
    pagination: {
      type: Object as PropType<TablePagination>,
    },
    /** 表格设置属性类型 */
    tableSettings: {
      type: Object as PropType<Omit<BkUiSettings, 'hasCheckAll'>>,
    },
    /** 表格渲染数据 */
    data: {
      type: Array as PropType<Record<string, any>[]>,
      default: () => [],
    },
    /** 表格加载状态 */
    loading: {
      type: Boolean,
      default: false,
    },
    /** 表格排序信息,字符串格式，以id为例：倒序 => -id；正序 => id；*/
    sort: {
      type: [String, Array] as PropType<string | string[]>,
    },
  },
  emits: {
    currentPageChange: (currentPage: number) => typeof currentPage === 'number',
    displayColFieldsChange: (displayColFields: string[]) => Array.isArray(displayColFields),
    pageSizeChange: (pageSize: number) => typeof pageSize === 'number',
    sortChange: (sort: string | string[]) => typeof sort === 'string' || Array.isArray(sort),
  },
  setup(props) {
    // const alarmStore = useAlarmCenterStore();
    const router = useRouter();
    const tableRef = useTemplateRef<InstanceType<typeof CommonTable>>('tableRef');
    const alertContentDetailRef = useTemplateRef<InstanceType<typeof AlertContentDetail>>('alertContentDetailRef');

    /** hover 场景使用的popover工具函数 */
    const hoverPopoverTools = usePopover();
    /** click 场景使用的popover工具函数 */
    const clickPopoverTools = usePopover({
      trigger: 'click',
      placement: 'bottom',
      theme: 'light alarm-center-popover max-width-50vw text-wrap padding-0',
    });
    /** 多选状态 */
    const selectedRowKeys = deepRef<(number | string)[]>([]);
    /* 关注人则禁用操作 */
    const isSelectedFollower = shallowRef(false);
    /** 滚动容器元素 */
    let scrollContainer: HTMLElement = null;
    /** 滚动结束后回调逻辑执行计时器  */
    let scrollPointerEventsTimer = null;
    /** 创建场景上下文 */
    const scenarioContext: ActionScenario['context'] & AlertScenario['context'] & IncidentScenario['context'] = {
      router,
      handleAlertSliderShowDetail,
      hoverPopoverTools,
      handleAlertContentDetailShow,
      handleAlertOperationClick,
      handleActionSliderShowDetail,
    };
    // 使用场景渲染器
    const { transformColumns, currentScenario, tableEmpty, tableScenarioClassName } =
      useScenarioRenderer(scenarioContext);
    /** 转换后的列配置 */
    const transformedColumns = computed(() => transformColumns(props.columns));
    /** 表格 setting 配置 */
    const settings = computed(() =>
      toValue(currentScenario).name !== INCIDENT_STORAGE_KEY
        ? {
            ...props.tableSettings,
            hasCheckAll: true,
          }
        : null
    );

    onMounted(() => {
      addScrollListener();
    });

    onBeforeUnmount(() => {
      scrollPointerEventsTimer && clearTimeout(scrollPointerEventsTimer);
      removeScrollListener();
    });

    /**
     * @description 添加滚动监听
     */
    function addScrollListener() {
      removeScrollListener();
      scrollContainer = document.querySelector(`.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`);
      if (!scrollContainer) return;
      scrollContainer.addEventListener('scroll', handleScroll);
    }

    /**
     * @description 移除滚动监听
     */
    function removeScrollListener() {
      if (!scrollContainer) return;
      scrollContainer.removeEventListener('scroll', handleScroll);
      scrollContainer = null;
    }

    /**
     * @description 滚动触发事件
     */
    function handleScroll() {
      updateTablePointEvents('none');
      hoverPopoverTools.hidePopover();
      clickPopoverTools.hidePopover();
      scrollPointerEventsTimer && clearTimeout(scrollPointerEventsTimer);
      scrollPointerEventsTimer = setTimeout(() => {
        updateTablePointEvents('auto');
      }, 600);
    }

    /**
     * @description 配置表格是否能够触发事件target
     */
    function updateTablePointEvents(val: 'auto' | 'none') {
      const tableDom = tableRef?.value?.$el;
      if (!tableDom) return;
      tableDom.style.pointerEvents = val;
    }

    /**
     * @description 处理行选择变化(不传参数则清空选择)
     */
    const handleSelectionChange = (keys?: (number | string)[], options?: SelectOptions<any>) => {
      // 表格空格键按下后会触发选择事件，此时需要禁止
      if (keys?.length && toValue(currentScenario).name !== ALERT_STORAGE_KEY) return;
      selectedRowKeys.value = keys || [];
      isSelectedFollower.value = options?.selectedRowData?.some?.(item => item.followerDisabled);
    };
    /**
     * @description: 展示 告警 详情抽屉
     */
    function handleAlertSliderShowDetail(id: string) {
      alert(`展示 告警 ${id}的详情抽屉窗`);
    }

    /**
     * @description: 展示 处理记录 详情抽屉
     */
    function handleActionSliderShowDetail(id: number | string) {
      alert(`展示 处理记录 ${id}的详情抽屉窗`);
    }

    /**
     * @description 打开告警内容详情 popover
     */
    function handleAlertContentDetailShow(e: MouseEvent) {
      console.log('================ alertContentDetailRef.value ================', alertContentDetailRef.value);
      clickPopoverTools.showPopover(e, () => alertContentDetailRef.value.$el);
    }

    /**
     * @description 告警行操作工具栏按钮点击回调事件
     */
    function handleAlertOperationClick(
      clickType: 'chart' | 'confirm' | 'manual' | 'more',
      row: AlertTableItem,
      e?: MouseEvent
    ) {
      alert(`${row.id}-${clickType} ${e}`);
    }

    /**
     * @description 告警批量设置
     */
    function handleAlertBatchSet(actionType: AlertSelectAction) {
      if (actionType === AlertSelectAction.CANCEL) {
        handleSelectionChange();
        return;
      }
      alert(`批量设置${actionType}`);
    }

    watch(
      () => props.data,
      () => {
        // 数据变化时，清空选中状态
        handleSelectionChange();
      }
    );

    return {
      transformedColumns,
      currentScenario,
      selectedRowKeys,
      tableEmpty,
      tableScenarioClassName,
      settings,
      isSelectedFollower,
      handleSelectionChange,
      handleAlertBatchSet,
    };
  },
  render() {
    return (
      <div class='alarm-table-container'>
        <CommonTable
          ref='tableRef'
          class={`alarm-table ${this.tableScenarioClassName}`}
          firstFullRow={
            this.selectedRowKeys?.length
              ? () =>
                  (
                    <AlertSelectionToolbar
                      class='alarm-table-first-full-row'
                      isSelectedFollower={this.isSelectedFollower}
                      selectedRowKeys={this.selectedRowKeys}
                      onClickAction={this.handleAlertBatchSet}
                    />
                  ) as unknown as SlotReturnValue
              : null
          }
          headerAffixedTop={{
            container: `.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`,
          }}
          horizontalScrollAffixedBottom={{
            container: `.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`,
          }}
          autoFillSpace={true}
          columns={this.transformedColumns}
          data={this.data}
          empty={this.tableEmpty}
          loading={this.loading}
          pagination={this.pagination}
          selectedRowKeys={this.selectedRowKeys}
          sort={this.sort}
          tableSettings={this.settings}
          onCurrentPageChange={page => this.$emit('currentPageChange', page)}
          onDisplayColFieldsChange={displayColFields => this.$emit('displayColFieldsChange', displayColFields)}
          onPageSizeChange={pageSize => this.$emit('pageSizeChange', pageSize)}
          onSelectChange={this.handleSelectionChange}
          onSortChange={sort => this.$emit('sortChange', sort)}
        />

        <div style='display: none;'>
          <AlertContentDetail ref='alertContentDetailRef' />
        </div>
      </div>
    );
  },
});
