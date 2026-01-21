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

import { type PropType, computed, defineComponent, shallowRef, useTemplateRef } from 'vue';

import { type TdPrimaryTableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { useI18n } from 'vue-i18n';
import { useTippy } from 'vue-tippy';

import DrillDownOptions from './drill-down-options';
import { getValueFormatFn, handleGetMinPrecisionFn } from './utils';

import './dimension-analysis-table.scss';

const tableColumnKey = {
  operation: 'operation',
  percentage: 'percentage',
  currentValue: 'currentValue',
};

export default defineComponent({
  name: 'DimensionAnalysisTable',
  props: {
    displayDimensions: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    dimensions: {
      type: Array as PropType<{ id: string; name: string }[]>,
      default: () => [],
    },
    tableData: {
      type: Array as PropType<any[]>,
      default: () => [],
    },
  },
  emits: {
    drillDown: (_val: { dimension: string; where: any[] }) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const selectorRef = useTemplateRef<InstanceType<typeof DrillDownOptions>>('selector');
    const popoverInstance = shallowRef(null);
    const currentRow = shallowRef<any>(null);
    const destroyPopoverInstance = () => {
      popoverInstance.value?.hide();
      popoverInstance.value?.destroy();
      popoverInstance.value = null;
    };
    const showPopover = (event: MouseEvent) => {
      if (popoverInstance.value) {
        destroyPopoverInstance();
        return;
      }
      popoverInstance.value = useTippy(event.target as any, {
        content: () => selectorRef.value.$el,
        trigger: 'click',
        placement: 'bottom-start',
        theme: 'light common-monitor padding-0',
        arrow: false,
        appendTo: document.body,
        zIndex: 4000,
        maxWidth: 700,
        offset: [0, 6],
        interactive: true,
        onHidden: () => {
          destroyPopoverInstance();
        },
      });
      popoverInstance.value?.show();
    };
    const handleSelectDimension = (dimension: string) => {
      emit('drillDown', {
        dimension,
        where: props.displayDimensions.map(id => {
          return {
            method: 'eq',
            value: currentRow.value?.dimensions?.[id] || '',
            condition: 'and',
            key: id,
          };
        }),
      });
      destroyPopoverInstance();
    };
    const renderPercentage = (row: any) => {
      if (row.percentage === undefined || row.percentage === null) {
        return '--';
      }
      return <span>{row.percentage}%</span>;
    };
    const renderValue = (row: any, prop: string) => {
      console.log(row);
      if (row[prop] === undefined || row[prop] === null) {
        return '--';
      }
      const precision = handleGetMinPrecisionFn(
        props.tableData.map(item => item[prop]).filter((set: any) => typeof set === 'number'),
        getValueFormatFn(row.unit),
        row.unit
      );
      const unitFormatter = getValueFormatFn(row.unit);
      const set: any = unitFormatter(row[prop], row.unit !== 'none' && precision < 1 ? 2 : precision);
      return (
        <span>
          {set.text} {set.suffix}
        </span>
      );
    };
    const columns = computed<TdPrimaryTableProps['columns']>(
      () =>
        [
          ...props.displayDimensions.map(dimension => {
            return {
              colKey: dimension,
              title: props.dimensions.find(item => item.id === dimension)?.name || dimension,
              width: 155,
              cell: (_h, { row }) => {
                return (
                  <div class='dimension-value'>
                    <span
                      style={{ background: row?.color || '#7EC7E7' }}
                      class='color-rect'
                    />
                    {row?.dimensions?.[dimension] || '--'}
                  </div>
                );
              },
            };
          }),
          {
            colKey: tableColumnKey.operation,
            title: t('操作'),
            width: '100',
            fixed: 'right',
            cell: (_h, { row }) => {
              return (
                <span
                  class='operation-btn'
                  onClick={event => {
                    currentRow.value = row;
                    showPopover(event);
                  }}
                >
                  <span>{t('下钻')}</span>
                  <span class='icon-monitor icon-mc-triangle-down' />
                </span>
              );
            },
          },
          {
            colKey: tableColumnKey.percentage,
            title: t('占比'),
            width: 100,
            sorter: true,
            fixed: 'right',
            cell: (_h, { row }) => {
              return renderPercentage(row);
            },
          },
          {
            colKey: tableColumnKey.currentValue,
            title: t('当前值'),
            width: 100,
            fixed: 'right',
            cell: (_h, { row }) => {
              return renderValue(row, 'value');
            },
          },
        ] as any
    );

    return {
      columns,
      handleSelectDimension,
    };
  },
  render() {
    return (
      <>
        <PrimaryTable
          class='dimension-analysis-data-table'
          columns={this.columns}
          data={this.tableData}
          horizontalScrollAffixedBottom={true}
          hover={true}
          needCustomScroll={false}
          resizable={true}
          tableLayout='fixed'
        />
        <div
          style={{
            display: 'none',
          }}
        >
          <DrillDownOptions
            ref='selector'
            active={this.displayDimensions?.[0] || ''}
            dimensions={this.dimensions}
            onSelect={this.handleSelectDimension}
          />
        </div>
      </>
    );
  },
});
