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

import { t } from '@/hooks/use-locale';
import TimeRange from '@/components/time-range/time-range';
import { DEFAULT_TIME_RANGE } from '@/components/time-range/utils';

import type { SearchParams } from '../types';

import './index.scss';

export default defineComponent({
  name: 'SearchBar',
  emits: ['search'],
  setup(props, { emit }) {
    /** 搜索 openid */
    const openid = ref('');

    /** 时间范围 */
    const timeRange = ref<[string, string]>(DEFAULT_TIME_RANGE as [string, string]);

    /**
     * 执行搜索
     */
    const handleSearch = () => {
      const params: SearchParams = {
        openid: openid.value,
        timeRange: timeRange.value,
      };
      emit('search', params);
    };

    /** 回车触发搜索 */
    const handleEnter = () => {
      handleSearch();
    };

    /** 时间范围变化 */
    const handleTimeChange = (val: [string, string]) => {
      timeRange.value = val;
    };

    return () => (
      <div class='search-bar card-base'>
        {/* 搜索输入框 */}
        <div class='search-bar-input'>
          <bk-input
            value={openid.value}
            onChange={(val: string) => {
              openid.value = val;
            }}
            clearable
            onEnter={handleEnter}
          />
        </div>

        {/* 时间选择器 */}
        <div class='search-bar-time'>
          <TimeRange
            value={timeRange.value}
            onChange={handleTimeChange}
          />
        </div>

        {/* 查询按钮 */}
        <bk-button
          theme='primary'
          ext-cls='search-bar-btn'
          icon=' bklog-icon bklog-shoudongchaxun'
          onClick={handleSearch}
        >
          {t('查询')}
        </bk-button>
      </div>
    );
  },
});
