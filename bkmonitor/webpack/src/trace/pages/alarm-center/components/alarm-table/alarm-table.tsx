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
import { computed, defineComponent, ref as deepRef, type PropType } from 'vue';

import { CONTENT_SCROLL_ELEMENT_CLASS_NAME, type TableColumnItem, type TablePagination } from '../../typings';
import AlertSelectionToolbar from './components/alert-selection-toolbar';
import CommonTable from './components/common-table';
import { usePopover } from './hooks/use-popover';
import { useScenarioRenderer } from './hooks/use-scenario-renderer';

import type { ActionScenario } from './scenarios/action-scenario';
import type { AlertScenario } from './scenarios/alert-scenario';
import type { IncidentScenario } from './scenarios/incident-scenario';
import type { BkUiSettings } from '@blueking/tdesign-ui/.';

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
  setup(props) {
    // const alarmStore = useAlarmCenterStore();
    const { showPopover, hidePopover, clearPopoverTimer } = usePopover();

    /** 创建场景上下文 */
    const scenarioContext: AlertScenario['context'] & IncidentScenario['context'] & ActionScenario['context'] = {
      handleShowDetail,
      showPopover,
      hidePopover,
      clearPopoverTimer,
    };
    // 使用场景渲染器
    const { transformColumns, currentScenario } = useScenarioRenderer(scenarioContext);
    /** 转换后的列配置 */
    const transformedColumns = computed(() => transformColumns(props.columns));

    /** 多选状态 */
    const selectedRowKeys = deepRef<(number | string)[]>([]);

    /**
     * @description 处理行选择变化
     */
    const handleSelectionChange = (keys: (number | string)[]) => {
      selectedRowKeys.value = keys;
    };
    /**
     * @description: 展示详情
     */
    function handleShowDetail(id: string) {
      alert(`记录${id}的详情弹窗`);
    }

    return {
      transformedColumns,
      currentScenario,
      selectedRowKeys,
      handleSelectionChange,
    };
  },
  render() {
    console.log('================ transformedColumns ================', this.transformedColumns);
    return (
      <CommonTable
        class='alarm-table'
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
        columns={this.transformedColumns}
        data={this.data}
        loading={this.loading}
        pagination={this.pagination}
        selectedRowKeys={this.selectedRowKeys}
        sort={this.sort}
        onSelectChange={this.handleSelectionChange}
        {...this.$emit}
      />
    );
  },
});
