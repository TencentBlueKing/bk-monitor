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

import { computed, defineComponent, onBeforeUnmount, onMounted, ref } from 'vue';
import useLocale from '@/hooks/use-locale';
import LeftList from './components/list-main/left-list';
import TableList from './components/list-main/table-list';

import './index.scss';

export default defineComponent({
  name: 'V2LogCollection',

  emits: ['width-change'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const isShowLeft = ref(false);
    const currentIndexSet = ref({ label: t('全部采集项'), count: 1124, key: 'all' });
    const handleShowLeft = () => {
      isShowLeft.value = !isShowLeft.value;
    };
    const handleChoose = item => {
      currentIndexSet.value = item;
    };
    return () => (
      <div class='v2-log-collection-main'>
        {isShowLeft.value && (
          <div class='v2-log-collection-left'>
            <LeftList on-choose={handleChoose} />
          </div>
        )}
        <div class='v2-log-collection-right'>
          <span
            class='right-btn-box'
            onClick={handleShowLeft}
          >
            <i class={`bk-icon icon-angle-${isShowLeft.value ? 'left' : 'right'} right-btn`}></i>
          </span>
          <TableList indexSet={currentIndexSet.value} />
        </div>
      </div>
    );
  },
});
