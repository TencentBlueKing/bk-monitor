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

import { defineComponent } from 'vue';

import { t } from '@/hooks/use-locale';

import './log-metric.scss';

export default defineComponent({
  name: 'LogMetric',
  props: {
    data: {
      type: Array,
      default: () => [],
    },
  },
  setup(props) {
    // 指标名称插槽
    const metricNameSlot = {
      default: ({ row }) => (
        <bk-button
          text
          theme='primary'
          class='name-button'
        >
          {row.metricName}
        </bk-button>
      ),
    };

    // 创建人插槽
    const creatorSlot = {
      default: ({ row }) => <bk-user-display-name user-id={row.creator}></bk-user-display-name>,
    };

    // 消费场景插槽
    const consumptionScenarioSlot = {
      default: ({ row }) => (
        <bk-button
          text
          theme='primary'
        >
          {row.consumptionScenario}
        </bk-button>
      ),
    };
    return () => (
      <div class='log-metric'>
        <bk-button
          theme='primary'
          class='new-button'
          title={t('新建')}
        >
          {t('新建')}
        </bk-button>
        <bk-table data={props.data}>
          <bk-table-column
            label={t('指标名称')}
            prop='metricName'
            min-width='120'
            scopedSlots={metricNameSlot}
          />
          <bk-table-column
            label={t('别名')}
            prop='alias'
            min-width='120'
          />
          <bk-table-column
            label={t('指标类型')}
            prop='metricType'
          />
          <bk-table-column
            label={t('创建人')}
            prop='creator'
            min-width='120'
            scopedSlots={creatorSlot}
          />
          <bk-table-column
            label={t('消费场景')}
            prop='consumptionScenario'
            width='120'
            scopedSlots={consumptionScenarioSlot}
          />
          <bk-table-column
            label={t('操作')}
            width='120'
          >
            <bk-button
              text
              theme='primary'
            >
              {t('编辑')}
            </bk-button>
          </bk-table-column>
        </bk-table>
      </div>
    );
  },
});
