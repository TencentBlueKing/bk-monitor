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

import { type PropType, defineComponent } from 'vue';

import { Exception } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import DashboardRow from './dashboard-row';

import type { GraphApi } from '../services/graph-api';
import type { DashboardRow as DashboardRowModel } from '../typings/dashboard';
import type { ScopedVarMap } from '../variables/resolve';

import './dashboard-panel.scss';

export default defineComponent({
  name: 'DashboardPanel',
  props: {
    /** 分组行（已过滤） */
    rows: {
      type: Array as PropType<DashboardRowModel[]>,
      default: () => [],
    },
    /** 列数：1 / 2 / 3 */
    columns: {
      type: Number,
      default: 3,
    },
    /** 变量取值映射 */
    scopedVars: {
      type: Object as PropType<ScopedVarMap>,
      default: () => ({}),
    },
    /** 取数 API */
    api: {
      type: Object as PropType<GraphApi>,
      required: true,
    },
  },
  setup(props) {
    const { t } = useI18n();
    return () =>
      props.rows.length ? (
        <div class='dashboard-panel'>
          {props.rows.map(row => (
            <DashboardRow
              key={row.id}
              api={props.api}
              columns={props.columns}
              row={row}
              scopedVars={props.scopedVars}
            />
          ))}
        </div>
      ) : (
        <Exception
          class='dashboard-panel__empty'
          description={t('暂无数据')}
          scene='part'
          type='empty'
        />
      );
  },
});
