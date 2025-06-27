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
import { computed, defineComponent, type PropType } from 'vue';

import {
  ExploreTableColumnTypeEnum,
  type BaseTableColumn,
} from '../../../trace-explore/components/trace-explore-table/typing';
import { CONTENT_SCROLL_ELEMENT_CLASS_NAME, type TableColumnItem } from '../../typings';
import CommonTable from './components/common-table';

import './alarm-table.scss';

export default defineComponent({
  name: 'AlarmTable',
  props: {
    /** 表格列配置 */
    columns: {
      type: Array as PropType<TableColumnItem[]>,
      default: () => [],
    },
  },
  setup(props) {
    const transformedColumns = computed(() =>
      props.columns.map(column => ({
        ...column,
        ...(specialRenderColumnsPropsMap[column.colKey] || {}),
      }))
    );

    /** 需要特殊渲染的单元格列 column配置项集合 */
    const specialRenderColumnsPropsMap: Record<string, BaseTableColumn> = {
      metric: {
        renderType: ExploreTableColumnTypeEnum.TAGS,
        getRenderValue: row => row.metric?.map?.(e => ({ alias: e, value: e })),
      },
      event_count: {
        renderType: ExploreTableColumnTypeEnum.CLICK,
        clickCallback(row, column, event) {},
      },
      create_time: {
        renderType: ExploreTableColumnTypeEnum.TIME,
      },
      begin_time: {
        renderType: ExploreTableColumnTypeEnum.TIME,
      },
      end_time: {
        renderType: ExploreTableColumnTypeEnum.TIME,
      },
      latest_time: {
        renderType: ExploreTableColumnTypeEnum.TIME,
      },
      first_anomaly_time: {
        renderType: ExploreTableColumnTypeEnum.TIME,
      },
      tags: {
        renderType: ExploreTableColumnTypeEnum.TAGS,
        getRenderValue: row => {
          return row.tags?.map?.(e => ({ alias: `${e.key}: ${e.value}`, value: e.value }));
        },
      },
      strategy_name: {
        renderType: ExploreTableColumnTypeEnum.LINK,
        getRenderValue: row => ({ url: getStrategyUrl(row), alias: row.strategy_name }),
      },
      labels: {
        renderType: ExploreTableColumnTypeEnum.TAGS,
        getRenderValue: row => row.labels?.map?.(e => ({ alias: e, value: e })),
      },
    };

    /**
     * @description 跳转策略详情页面
     *
     */
    function getStrategyUrl(row) {
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const { strategy_id, bk_biz_id } = row || {};
      if (!strategy_id) return;
      return `${location.origin}${location.pathname}?bizId=${bk_biz_id}#/strategy-config/detail/${strategy_id}`;
    }

    return {
      transformedColumns,
    };
  },
  render() {
    return (
      <CommonTable
        class='alarm-table'
        headerAffixedTop={{
          container: `.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`,
        }}
        horizontalScrollAffixedBottom={{
          container: `.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`,
        }}
        columns={this.transformedColumns}
        {...this.$attrs}
      />
    );
  },
});
