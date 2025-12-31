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

import useLocale from '@/hooks/use-locale';

import LeftList from './components/list-main/left-list';
import TableList from './components/list-main/table-list';

import type { IListItemData } from './type';

import './index.scss';

export default defineComponent({
  name: 'V2LogCollection',

  setup() {
    const { t } = useLocale();
    const isShowLeft = ref(true);
    const currentIndexSet = ref<IListItemData>({
      index_set_name: t('全部采集项'),
      index_count: 0,
      index_set_id: 'all',
    });
    /** 展开/收起左侧采集项列表 */
    const handleShowLeft = () => {
      isShowLeft.value = !isShowLeft.value;
    };
    /** 选中索引集 */
    const handleChoose = (item: IListItemData) => {
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
          <button
            class='right-btn-box'
            onClick={handleShowLeft}
            type='button'
          >
            <i class={`bk-icon icon-angle-${isShowLeft.value ? 'left' : 'right'} right-btn`} />
          </button>
          <TableList indexSet={currentIndexSet.value} />
        </div>
      </div>
    );
  },
});
