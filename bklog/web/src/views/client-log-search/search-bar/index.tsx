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
import axios from 'axios';

import { t } from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import $http from '@/api';
import TimeRange from '@/components/time-range/time-range';
import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '@/components/time-range/utils';

import type { SearchParams, SearchValueType, UrlState } from '../types';

import './index.scss';

export default defineComponent({
  name: 'SearchBar',
  props: {
    /** 初始 URL 状态（用于回填搜索条件） */
    initialUrlState: {
      type: Object as unknown as () => Partial<UrlState>,
      default: undefined,
    },
    /** 面板是否正在加载（加载中时禁用搜索按钮） */
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['search'],
  setup(props, { emit }) {
    const store = useStore();

    /** 搜索 openid — 优先使用 URL 回填值 */
    const urlState = props.initialUrlState ?? {};
    const openid = ref(urlState.keyword || '');

    /** 时间范围 — 优先使用 URL 回填值 */
    const timeRange = ref<[string, string]>(
      urlState.startTime && urlState.endTime
        ? [urlState.startTime, urlState.endTime]
        : DEFAULT_TIME_RANGE as [string, string],
    );

    /** 时区 — 优先使用 URL 回填值 */
    const timezone = ref(urlState.timezone || window.timezone);

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
    /** 上次请求 openid 列表时使用的关键词 */
    let lastKeyword: string | null = null;

    // ---- openid/task_id 类型判断相关 ----
    /** 当前值的类型（openid 或 task_id），从列表选择时为 'openid'，手动输入时待联想结果判断 */
    const currentValueType = ref<SearchValueType | undefined>(undefined);

    /** 搜索按钮是否禁用（联想请求进行中且类型未确定，或面板加载中时禁用） */
    const isSearchDisabled = computed(() => props.loading || (isRequesting.value && openid.value.trim() !== '' && !currentValueType.value));

    /**
     * 请求 openid 列表
     */
    const fetchOpenidList = (keyword: string) => {
      // 清除防抖定时器
      if (debounceTimer) {
        clearTimeout(debounceTimer);
        debounceTimer = null;
      }

      // 如果关键词没变，且不是「空值+空列表」的情况，直接复用上次列表
      if (keyword === lastKeyword && !(keyword.trim() === '' && openidList.value.length === 0)) {
        if (isFocused.value) {
          isOpenidListVisible.value = true;
        }
        return;
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
            lastKeyword = keyword;
            // 如果当前值是手动输入的（非列表选择），根据返回结果判断类型
            if (!currentValueType.value && openid.value.trim()) {
              const trimmedVal = openid.value.trim();
              const isNumeric = !Number.isNaN(Number(trimmedVal));
              currentValueType.value = (openidList.value.includes(trimmedVal) || !isNumeric) ? 'openid' : 'task_id';
            }
          })
          .catch((err: any) => {
            if (axios.isCancel(err)) {
              return;
            }
            openidList.value = [];
            lastKeyword = null;
            // 请求失败时，根据输入内容判断类型：数字按 task_id，非数字按 openid
            if (!currentValueType.value && openid.value.trim()) {
              const isNumeric = !Number.isNaN(Number(openid.value.trim()));
              currentValueType.value = isNumeric ? 'task_id' : 'openid';
            }
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
      lastKeyword = null;
      currentValueType.value = 'openid';
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
        valueType: currentValueType.value,
      };
      emit('search', params);
    };

    /** 时间范围变化 */
    const handleTimeChange = (val: [string, string]) => {
      timeRange.value = val;
      handleSearch();
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
              // 手动输入时重置类型，等待联想结果判断
              currentValueType.value = undefined;
              fetchOpenidList(val);
            }}
            right-icon='bk-icon icon-search'
            onFocus={handleFocus}
            onBlur={handleBlur}
            on-right-icon-click={() => {
              if (!isSearchDisabled.value) handleSearch();
            }}
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
          disabled={isSearchDisabled.value}
          onClick={() => handleSearch()}
        >
          {t('查询')}
        </bk-button>
      </div>
    );
  },
});
