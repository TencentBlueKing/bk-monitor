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

import './dimension-analysis-table.scss';

const tableColumnKey = {
  operation: 'operation',
  percentage: 'percentage',
  currentValue: 'currentValue',
};

export default defineComponent({
  name: 'DimensionAnalysisTable',
  props: {
    dimensions: {
      type: Array as PropType<{ id: string; name: string }[]>,
      default: () => [],
    },
  },
  emits: {
    change: (_val: any) => true,
  },
  setup() {
    const { t } = useI18n();
    const selectorRef = useTemplateRef<HTMLDivElement>('selector');
    const popoverInstance = shallowRef(null);
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
        content: () => selectorRef.value,
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
    const handleSelectDimension = (_dimension?: string) => {
      destroyPopoverInstance();
    };
    const columns = computed<TdPrimaryTableProps['columns']>(
      () =>
        [
          {
            colKey: 'colKey',
            title: 'xxx维度',
            width: 155,
            cell: (_h, { _row }) => {
              return <div>维度值</div>;
            },
          },
          {
            colKey: tableColumnKey.operation,
            title: t('操作'),
            width: '100',
            cell: (_h, { _row }) => {
              return (
                <span
                  class='operation-btn'
                  onClick={event => showPopover(event)}
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
            cell: (_h, { _row }) => {
              return <div>占比</div>;
            },
          },
          {
            colKey: tableColumnKey.currentValue,
            title: t('当前值'),
            width: 100,
            cell: (_h, { _row }) => {
              return <div>当前值</div>;
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
          data={new Array(10).fill(null).map((_, index) => ({ key: index }))}
          hover={true}
          resizable={true}
          tableLayout='fixed'
        />
        <div
          style={{
            display: 'none',
          }}
        >
          <div
            ref='selector'
            class='dimension-analysis-data-table-popover'
          >
            {this.dimensions.map((item, index) => (
              <div
                key={index}
                class={['selector-item', { active: index === 5 }]}
                onClick={() => this.handleSelectDimension()}
              >
                {item.name}
              </div>
            ))}
          </div>
        </div>
      </>
    );
  },
});
