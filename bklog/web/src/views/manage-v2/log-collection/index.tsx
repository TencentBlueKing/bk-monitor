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

import { defineComponent, ref, onMounted } from 'vue';

import useLocale from '@/hooks/use-locale';

import LeftList from './components/list-main/left-list';
import TableList from './components/list-main/table-list';
import { mockList } from './data.ts';

import './index.scss';

export default defineComponent({
  name: 'V2LogCollection',

  emits: ['width-change'],

  setup(props, { emit }) {
    console.log('props', props, emit);
    const LOADING_TIMEOUT_MS = 1200;
    const { t } = useLocale();
    const isShowLeft = ref(true);
    const listLoading = ref(false);
    const currentIndexSet = ref({ label: t('全部采集项'), count: 1124, key: 'all' });
    const tableList = ref(mockList);
    const list = [
      { label: 'bk_apm_trace', count: 11, key: 'bk_apm_trace', isDelete: false },
      { label: 'bk_aiop', count: 23, key: 'bk_apm_trace1', isDelete: true },
      { label: 'bk_apm_trace', count: 164, key: 'bk_apm_trace2', isDelete: true },
      { label: '容器日志采集示例', count: 99, key: 'bk_apm_trace3', isDelete: true },
      { label: '默认索引集', count: 11, key: 'bk_apm_trace4', isDelete: true },
      { label: '主机采集示例', count: 101, key: 'bk_apm_trace5', isDelete: true },
    ];
    /** 展开/收起左侧采集项列表 */
    const handleShowLeft = () => {
      isShowLeft.value = !isShowLeft.value;
    };
    /** 选中索引集 */
    const handleChoose = item => {
      currentIndexSet.value = item;
    };

    onMounted(() => {
      listLoading.value = true;
      setTimeout(() => {
        listLoading.value = false;
      }, LOADING_TIMEOUT_MS);
    });

    return () => (
      <div class='v2-log-collection-main'>
        {isShowLeft.value && (
          <div class='v2-log-collection-left'>
            <LeftList
              list={list}
              loading={listLoading.value}
              on-choose={handleChoose}
            />
          </div>
        )}
        <div class='v2-log-collection-right'>
          <span
            class='right-btn-box'
            on-Click={handleShowLeft}
          >
            <i class={`bk-icon icon-angle-${isShowLeft.value ? 'left' : 'right'} right-btn`} />
          </span>
          <TableList
            data={tableList.value}
            indexSet={currentIndexSet.value}
            loading={listLoading.value}
          />
        </div>
      </div>
    );
  },
});
