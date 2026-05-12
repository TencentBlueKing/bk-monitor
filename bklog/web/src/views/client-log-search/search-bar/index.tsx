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

import { defineComponent, onBeforeUnmount, onMounted, ref } from 'vue';
import axios from 'axios';

import { t } from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import $http from '@/api';
import TimeRange from '@/components/time-range/time-range';
import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '@/components/time-range/utils';

import type { SearchParams } from '../types';

import './index.scss';

export default defineComponent({
  name: 'SearchBar',
  emits: ['search'],
  setup(_props, { emit }) {
    const store = useStore();

    /** 搜索 openid */
    const openid = ref('');

    /** 时间范围 */
    const timeRange = ref<[string, string]>(DEFAULT_TIME_RANGE as [string, string]);

    /** 时区 */
    const timezone = ref(window.timezone);

    // ---- 字段列表弹窗相关 ----
    /** 接口返回的 openid 列表 */
    const openidList = ref<string[]>([]);
    /** 是否正在请求 */
    const isRequesting = ref(false);
    /** 弹窗是否可见 */
    const isOpenidListVisible = ref(false);
    /** 输入框是否聚焦 */
    const isFocused = ref(false);

    /** 防抖定时器 */
    let debounceTimer: ReturnType<typeof setTimeout> | null = null;
    /** 取消上一个请求的执行函数 */
    let cancelExecutor: (() => void) | null = null;

    /**
     * 请求 openid 列表
     */
    const fetchOpenidList = (keyword: string) => {
      // 清除防抖定时器
      if (debounceTimer) {
        clearTimeout(debounceTimer);
        debounceTimer = null;
      }

      // 取消上一个未完成的请求
      if (cancelExecutor) {
        cancelExecutor();
        cancelExecutor = null;
      }

      debounceTimer = setTimeout(() => {
        if (!isFocused.value) {
          return;
        }
        isRequesting.value = true;
        isOpenidListVisible.value = true;

        const [startTime, endTime] = handleTransformToTimestamp(timeRange.value);

        const cancelToken = new axios.CancelToken((c) => {
          cancelExecutor = c;
        });

        const query: Record<string, any> = {
          bk_biz_id: store.state.bkBizId,
        };

        if (keyword.trim()) {
          query.keyword = keyword.trim();
        }

        if (startTime) {
          query.start_time = startTime;
        }
        if (endTime) {
          query.end_time = endTime;
        }

        $http
          .request('clientLog/getOpenidList', {
            query,
          }, {
            cancelToken,
          })
          .then((res: any) => {
            openidList.value = res.data ?? [];
          })
          .catch((err: any) => {
            if (axios.isCancel(err)) {
              return;
            }
            openidList.value = [];
          })
          .finally(() => {
            isRequesting.value = false;
          });
      }, 300);
    };

    /** 选中某个 openid 项 */
    const handleSelectOpenid = (item: string) => {
      openid.value = item;
      isOpenidListVisible.value = false;
      openidList.value = [];
    };

    /** 输入框聚焦 */
    const handleFocus = () => {
      isFocused.value = true;
      fetchOpenidList(openid.value);
    };

    /** 输入框失焦（延迟关闭，允许点击弹窗项） */
    const handleBlur = () => {
      isFocused.value = false;
      setTimeout(() => {
        isOpenidListVisible.value = false;
      }, 200);
    };

    /** 组件卸载时清理 */
    onBeforeUnmount(() => {
      if (debounceTimer) {
        clearTimeout(debounceTimer);
        debounceTimer = null;
      }
      if (cancelExecutor) {
        cancelExecutor();
        cancelExecutor = null;
      }
    });

    /** 挂载时自动触发一次搜索 */
    onMounted(() => {
      handleSearch(true);
    });

    /**
     * 执行搜索
     * @param allowEmpty 是否允许空 openid 搜索（挂载时首次搜索允许为空）
     */
    const handleSearch = (allowEmpty = true) => {
      if (!allowEmpty && !openid.value.trim()) {
        return;
      }
      const params: SearchParams = {
        openid: openid.value,
        timeRange: timeRange.value,
        timezone: timezone.value,
      };
      emit('search', params);
    };

    /** 时间范围变化 */
    const handleTimeChange = (val: [string, string]) => {
      timeRange.value = val;
    };

    /** 时区变化 */
    const handleTimezoneChange = (val: string) => {
      timezone.value = val;
    };

    return () => (
      <div class='search-bar card-base'>
        {/* 搜索输入框 */}
        <div class='search-bar-input'>
          <bk-input
            value={openid.value}
            onChange={(val: string) => {
              openid.value = val;
              fetchOpenidList(val);
            }}
            right-icon='bk-icon icon-search'
            onFocus={handleFocus}
            onBlur={handleBlur}
            on-right-icon-click={() => handleSearch()}
            clearable
          />
          {/* 字段列表弹窗 */}
          {isOpenidListVisible.value && (
            <ul class='openid-list-dropdown'>
              {isRequesting.value || openidList.value.length === 0 ? (
                <li
                  v-bkloading={{ isLoading: isRequesting.value, size: 'small' }}
                  style='min-height: 32px'
                >
                  {t('暂无数据')}
                </li>
              ) : null}
              {!isRequesting.value && openidList.value.map((item, _index) => (
                <li
                  key={item}
                  title={item}
                  onClick={(e: MouseEvent) => {
                    e.stopPropagation();
                    handleSelectOpenid(item);
                  }}
                >
                  <div>{item}</div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* 时间选择器 */}
        <div class='search-bar-time'>
          <TimeRange
            value={timeRange.value}
            timezone={timezone.value}
            onChange={handleTimeChange}
            onTimezoneChange={handleTimezoneChange}
          />
        </div>

        {/* 查询按钮 */}
        <bk-button
          theme='primary'
          ext-cls='search-bar-btn'
          icon=' bklog-icon bklog-shoudongchaxun'
          onClick={() => handleSearch()}
        >
          {t('查询')}
        </bk-button>
      </div>
    );
  },
});
