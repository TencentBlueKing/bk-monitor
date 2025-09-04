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

import { defineComponent, ref } from 'vue';
import './index.scss';

export default defineComponent({
  name: 'SortOperate',
  props: {},
  setup(_, { emit, expose }) {
    const sortState = ref([false, false]);

    const handleClickSort = (e?: Event) => {
      e?.stopPropagation();
      if (sortState.value.every(item => !item)) {
        sortState.value = [true, false];
        emit('sort', 'asc');
        return;
      }

      if (sortState.value[0]) {
        sortState.value = [false, true];
        emit('sort', 'desc');
        return;
      }

      if (sortState.value[1]) {
        sortState.value = [false, false];
        emit('sort', 'none');
      }
    };

    expose({
      reset: () => {
        sortState.value = [false, false];
      },
      update: handleClickSort,
    });

    return () => (
      <div
        class='sort-main'
        on-click={handleClickSort}
      >
        <log-icon
          common
          type='up-shape'
          class={{ 'sort-icon-up': true, 'is-sort-active': sortState.value[0] }}
        />
        <log-icon
          common
          type='down-shape'
          class={{ 'sort-icon-down': true, 'is-sort-active': sortState.value[1] }}
        />
      </div>
    );
  },
});
