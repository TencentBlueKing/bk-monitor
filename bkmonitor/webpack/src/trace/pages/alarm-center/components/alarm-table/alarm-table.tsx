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
  computed,
  defineComponent,
  ref as deepRef,
  type PropType,
  useTemplateRef,
  shallowRef,
  watch,
  onMounted,
  onBeforeUnmount,
} from 'vue';

import { CONTENT_SCROLL_ELEMENT_CLASS_NAME, type TableColumnItem, type TablePagination } from '../../typings';
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
    const scenarioContext: AlertScenario['context'] & IncidentScenario['context'] & ActionScenario['context'] = {
      handleShowDetail,
      hoverPopoverTools,
      handleAlertContentDetailShow,
    };
    // 使用场景渲染器
    const { transformColumns, currentScenario } = useScenarioRenderer(scenarioContext);
    /** 转换后的列配置 */
    const transformedColumns = computed(() => transformColumns(props.columns));

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
     * @description 处理行选择变化
     */
    const handleSelectionChange = (keys: (number | string)[], options?: SelectOptions<any>) => {
      selectedRowKeys.value = keys;
      isSelectedFollower.value = options?.selectedRowData?.some?.(item => item.followerDisabled);
    };
    /**
     * @description: 展示详情
     */
    function handleShowDetail(id: string) {
      alert(`记录${id}的详情弹窗`);
    }

    /**
     * @description 打开告警内容详情 popover
     */
    function handleAlertContentDetailShow(e: MouseEvent) {
      console.log('================ alertContentDetailRef.value ================', alertContentDetailRef.value);
      clickPopoverTools.showPopover(e, () => alertContentDetailRef.value.$el);
    }

    watch(
      () => props.data,
      () => {
        // 数据变化时，清空选中状态
        handleSelectionChange([]);
      }
    );

    return {
      transformedColumns,
      currentScenario,
      selectedRowKeys,
      isSelectedFollower,
      handleSelectionChange,
    };
  },
  render() {
    return (
      <div class='alarm-table-container'>
        <CommonTable
          ref='tableRef'
          class='alarm-table'
          firstFullRow={
            this.selectedRowKeys?.length
              ? () =>
                  (
                    <AlertSelectionToolbar
                      class='alarm-table-first-full-row'
                      isSelectedFollower={this.isSelectedFollower}
                      selectedRowKeys={this.selectedRowKeys}
                    />
                  ) as unknown as SlotReturnValue
              : undefined
          }
          headerAffixedTop={{
            container: `.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`,
          }}
          horizontalScrollAffixedBottom={{
            container: `.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`,
          }}
          tableSettings={{
            ...this.tableSettings,
            hasCheckAll: true,
          }}
          autoFillSpace={true}
          columns={this.transformedColumns}
          data={this.data}
          loading={this.loading}
          pagination={this.pagination}
          selectedRowKeys={this.selectedRowKeys}
          sort={this.sort}
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
