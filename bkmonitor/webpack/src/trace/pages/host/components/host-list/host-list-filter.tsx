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

import RetrievalFilter from '../../../../components/retrieval-filter/retrieval-filter';

import type {
  EMode,
  IFilterField,
  IGetValueFnParams,
  IWhereItem,
  IWhereValueOptionsItem,
} from '../../../../components/retrieval-filter/typing';

import './host-list-filter.scss';

export default defineComponent({
  name: 'HostListFilter',
  props: {
    /** 过滤字段列表 */
    fields: {
      type: Array as PropType<IFilterField[]>,
      default: () => [],
    },
    /** ui 模式条件 */
    where: {
      type: Array as PropType<IWhereItem[]>,
      default: () => [],
    },
    /** 语句模式语句 */
    queryString: {
      type: String,
      default: '',
    },
    /** 过滤模式 */
    filterMode: {
      type: String as PropType<EMode>,
      required: true,
    },
    /** 检索候选项获取函数 */
    getValueFn: {
      type: Function as PropType<(params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>>,
      required: true,
    },
  },
  emits: {
    whereChange: (_v: IWhereItem[]) => true,
    queryStringChange: (_v: string) => true,
    modeChange: (_v: EMode) => true,
    search: () => true,
  },
  setup(props, { emit }) {
    return () => (
      <div class='host-list-filter'>
        <RetrievalFilter
          fields={props.fields}
          filterMode={props.filterMode}
          getValueFn={props.getValueFn}
          isShowClear={true}
          isShowCopy={false}
          isShowFavorite={false}
          isShowResident={false}
          queryString={props.queryString}
          where={props.where}
          onModeChange={(v: EMode) => emit('modeChange', v)}
          onQueryStringChange={(v: string) => emit('queryStringChange', v)}
          onSearch={() => emit('search')}
          onWhereChange={(v: IWhereItem[]) => emit('whereChange', v)}
        />
      </div>
    );
  },
});
