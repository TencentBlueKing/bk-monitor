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

import './left-list.scss';

export default defineComponent({
  name: 'LeftList',

  emits: ['choose'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const activeKey = ref('all');
    const list = [
      { label: 'bk_apm_trace', count: 11, key: 'bk_apm_trace' },
      { label: 'bk_aiop', count: 23, key: 'bk_apm_trace1' },
      { label: 'bk_apm_trace', count: 164, key: 'bk_apm_trace2' },
      { label: '容器日志采集示例', count: 99, key: 'bk_apm_trace3' },
      { label: '默认索引集', count: 11, key: 'bk_apm_trace4' },
      { label: '主机采集示例', count: 101, key: 'bk_apm_trace5' },
    ];
    const handleItem = item => {
      activeKey.value = item.key;
      emit('choose', item);
    };
    const renderBaseItem = item => (
      <div
        class={['base-item', { active: activeKey.value === item.key }]}
        onClick={() => handleItem(item)}
      >
        <i class='bklog-icon item-icon bklog-file-close'></i>
        <span class='item-label'>{item.label}</span>
        <span class='item-count'>{item.count}</span>
      </div>
    );
    return () => (
      <div class='log-collection-left-list'>
        <div class='list-top'>
          {renderBaseItem({ label: t('全部采集项'), count: 1124, key: 'all' })}
          {renderBaseItem({ label: t('未归属索引集'), count: 23, key: 'unassigned' })}
        </div>
        <div class='list-main'>
          <div class='list-main-title'>{t('索引集列表')}</div>
          <div class='list-main-search'>
            <span class='add-btn'>+</span>
            <bk-input
              class='search-input'
              placeholder={t('搜索 索引集名称')}
              right-icon='bk-icon icon-search'
            />
          </div>
          <div class='list-main-content'>{list.map(item => renderBaseItem(item))}</div>
        </div>
      </div>
    );
  },
});
