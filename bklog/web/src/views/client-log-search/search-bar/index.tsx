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
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
 * TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

import { computed, defineComponent, nextTick, onBeforeUnmount, ref } from 'vue';
import axios from 'axios';

import $http from '@/api';
import TimeRange from '@/components/time-range/time-range';
import { handleTransformToTimestamp } from '@/components/time-range/utils';
import { t } from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import type { SearchCondition, SearchParams, SearchSelectValue, SearchValueType, UrlState } from '../types';

import './index.scss';

interface SearchFieldOption {
  id: SearchValueType;
  name: string;
  multiable: boolean;
  remote?: boolean;
}

const CLIENT_LOG_DEFAULT_TIME_RANGE: [string, string] = ['now-6h', 'now'];
const SEARCH_KEYS: SearchValueType[] = ['file_name', 'task_id', 'openid', 'extend_info'];

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
  setup(props, { emit, expose }) {
    const store = useStore();
    const urlState = props.initialUrlState ?? {};

    const timeRange = ref<[string, string]>(
      urlState.startTime && urlState.endTime ? [urlState.startTime, urlState.endTime] : CLIENT_LOG_DEFAULT_TIME_RANGE,
    );
    const timezone = ref(urlState.timezone || window.timezone);
    const searchSelectRef = ref<any>(null);
    const searchValues = ref<SearchSelectValue[]>([]);
    const activeValueType = ref<SearchValueType | null>(null);
    const isInferring = ref(false);

    let cancelExecutor: (() => void) | null = null;
    let requestSequence = 0;
    let lastKeyword: string | null = null;
    let openidOptions: Array<{ id: string; name: string }> = [];
    let searchAfterOpenidSelect = false;
    let pendingNormalization: Promise<void> = Promise.resolve();

    const searchFieldOptions: SearchFieldOption[] = [
      { id: 'file_name', name: t('文件名'), multiable: false },
      { id: 'task_id', name: t('任务 ID'), multiable: false },
      { id: 'openid', name: 'OpenID', multiable: false, remote: true },
      { id: 'extend_info', name: t('扩展信息'), multiable: false },
    ];
    const fieldNameMap = new Map(searchFieldOptions.map(item => [item.id, item.name]));

    /** 将 SearchSelect 的组件值转换为有效的业务搜索条件 */
    const getSearchConditions = (): SearchCondition[] =>
      searchValues.value
        .filter(item => SEARCH_KEYS.includes(item.id as SearchValueType) && item.values?.[0]?.id !== undefined)
        .map(item => ({
          key: item.id as SearchValueType,
          value: String(item.values?.[0]?.id ?? '').trim(),
        }))
        .filter(item => item.value !== '');

    const selectedKeys = computed(() => new Set(getSearchConditions().map(item => item.key)));
    const searchSelectData = computed(() =>
      searchFieldOptions.filter(item => !selectedKeys.value.has(item.id) || activeValueType.value === item.id),
    );
    const isValueInputReadonly = computed(() => searchValues.value.length > 0 && activeValueType.value === null);
    const isSearchDisabled = computed(() => props.loading || isInferring.value);

    /** 将字段和值组装成 SearchSelect 可回填的选中项 */
    const toSearchSelectValue = (key: SearchValueType, value: string): SearchSelectValue => ({
      id: key,
      name: fieldNameMap.get(key) ?? key,
      values: [{ id: value, name: value }],
    });

    /** 请求 OpenID 候选，并保证旧请求不会覆盖新结果 */
    const fetchOpenidOptions = async (searchVal: string) => {
      const keyword = searchVal.includes('：')
        ? searchVal.slice(searchVal.lastIndexOf('：') + 1).trim()
        : searchVal.trim();
      if (keyword === lastKeyword) {
        return openidOptions;
      }

      cancelExecutor?.();
      cancelExecutor = null;
      requestSequence += 1;
      const currentSequence = requestSequence;
      const [startTime, endTime] = handleTransformToTimestamp(timeRange.value);
      const cancelToken = new axios.CancelToken(cancel => {
        cancelExecutor = cancel;
      });
      const query: Record<string, any> = { bk_biz_id: store.state.bkBizId };
      if (keyword) query.keyword = keyword;
      if (startTime) query.start_time = startTime;
      if (endTime) query.end_time = endTime;

      try {
        const res = await $http.request('clientLog/getOpenidList', { query }, { cancelToken });
        if (currentSequence !== requestSequence) return [];
        openidOptions = (res.data ?? []).map((item: string) => ({ id: item, name: item }));
        lastKeyword = keyword;
        return openidOptions;
      } catch (err) {
        if (!axios.isCancel(err) && currentSequence === requestSequence) {
          openidOptions = [];
          lastKeyword = null;
        }
        return [];
      } finally {
        if (currentSequence === requestSequence) {
          cancelExecutor = null;
        }
      }
    };

    /** 首组裸值沿用原有规则推断字段 */
    const inferValueType = async (value: string): Promise<SearchValueType> => {
      if (value.endsWith('.zip')) return 'file_name';
      const options = await fetchOpenidOptions(value);
      const isNumeric = /^\d+$/.test(value);
      return options.some(item => item.id === value) || !isNumeric ? 'openid' : 'task_id';
    };

    /** 按新版字段、旧版关键词、旧版文件名的优先级回填初始搜索条件 */
    const initializeSearchValues = async () => {
      const explicitConditions = SEARCH_KEYS.flatMap(key => {
        const value = urlState[key];
        return value ? [toSearchSelectValue(key, value)] : [];
      });
      if (explicitConditions.length) {
        searchValues.value = explicitConditions;
        return;
      }

      if (urlState.keyword) {
        const value = urlState.keyword.trim();
        if (!value) return;
        isInferring.value = true;
        const key = urlState.valueType || (await inferValueType(value));
        searchValues.value = [toSearchSelectValue(key, value)];
        isInferring.value = false;
        return;
      }

      if (urlState.fileName) {
        searchValues.value = [toSearchSelectValue('file_name', urlState.fileName)];
      }
    };
    const initializationPromise = initializeSearchValues();

    /** 向父组件提交当前有效条件、时间范围和时区 */
    const emitSearch = () => {
      const params: SearchParams = {
        conditions: getSearchConditions(),
        timeRange: timeRange.value,
        timezone: timezone.value,
      };
      emit('search', params);
    };

    /** 等待初始化和裸值归一化完成后执行正式查询 */
    const handleSearch = async () => {
      await initializationPromise;
      await pendingNormalization;
      if (isSearchDisabled.value) return;
      emitSearch();
    };

    /** 推断首组裸值的字段类型，并转换为标准 SearchSelect 条件 */
    const normalizeRawValue = async (rawValue: SearchSelectValue) => {
      const value = String(rawValue.id || rawValue.name || '').trim();
      if (!value) {
        searchValues.value = [];
        return;
      }
      isInferring.value = true;
      const key = await inferValueType(value);
      searchValues.value = [toSearchSelectValue(key, value)];
      activeValueType.value = null;
      isInferring.value = false;
    };

    /** 同步 SearchSelect 条件变化，并处理裸值、删除条件和 OpenID 候选选择后的查询 */
    const handleValuesChange = (values: SearchSelectValue[]) => {
      const previousConditions = getSearchConditions();
      const rawValue = values.find(item => !SEARCH_KEYS.includes(item.id as SearchValueType));
      if (rawValue) {
        pendingNormalization = normalizeRawValue(rawValue);
        return;
      }

      searchValues.value = values.map(item => ({
        id: item.id,
        name: fieldNameMap.get(item.id as SearchValueType) ?? item.name,
        values: item.values?.slice(0, 1).map(value => ({ id: String(value.id), name: String(value.name) })),
      }));
      activeValueType.value = null;
      pendingNormalization = Promise.resolve();

      const currentConditions = getSearchConditions();
      const isConditionRemoved =
        currentConditions.length < previousConditions.length ||
        previousConditions.some(item => !currentConditions.some(current => current.key === item.key));
      if (isConditionRemoved || searchAfterOpenidSelect) {
        const shouldRefreshMenu = isConditionRemoved;
        searchAfterOpenidSelect = false;
        nextTick(() => {
          if (shouldRefreshMenu) {
            searchSelectRef.value?.showMenu?.();
          }
          handleSearch();
        });
      }
    };

    /** 记录当前已选择、正在输入 value 的字段 */
    const handleMenuSelect = (item: SearchFieldOption) => {
      activeValueType.value = item.id;
    };

    /** 输入内容离开当前字段前缀时，清理正在编辑的字段状态 */
    const handleInputChange = (event: InputEvent) => {
      if (!activeValueType.value) return;
      const fieldName = fieldNameMap.get(activeValueType.value);
      const inputValue = (event.target as HTMLElement)?.innerText ?? '';
      if (!inputValue.startsWith(`${fieldName}：`)) {
        activeValueType.value = null;
      }
    };

    /** 标记 OpenID 候选已选中，待条件写入完成后自动查询 */
    const handleOpenidSelect = () => {
      if (activeValueType.value === 'openid') {
        searchAfterOpenidSelect = true;
      }
    };

    /** 清空全部搜索条件，并按当前时间范围重新查询 */
    const handleClear = () => {
      searchValues.value = [];
      activeValueType.value = null;
      searchAfterOpenidSelect = false;
      pendingNormalization = Promise.resolve();
      nextTick(() => handleSearch());
    };

    /** 提交 SearchSelect 中尚未生成标签的草稿值 */
    const commitDraftValue = async (event?: Event) => {
      if (!searchSelectRef.value?.input?.value) return;
      await searchSelectRef.value.handleKeyEnter(event ?? { preventDefault: () => {} }, false, false);
      await nextTick();
    };

    /** 点击查询按钮时先提交草稿值，再执行正式查询 */
    const handleButtonSearch = async (event: MouseEvent) => {
      await commitDraftValue(event);
      await handleSearch();
    };

    /** 更新时间范围、失效 OpenID 候选缓存，并按新时间重新查询 */
    const handleTimeChange = async (val: [string, string]) => {
      timeRange.value = val;
      lastKeyword = null;
      openidOptions = [];
      await commitDraftValue();
      await handleSearch();
    };

    /** 更新时区，并在提交当前草稿值后重新查询 */
    const handleTimezoneChange = async (val: string) => {
      timezone.value = val;
      await commitDraftValue();
      await handleSearch();
    };

    /** 供父组件重新查询；可选择清空条件或等待 URL 初始条件回填 */
    const reSearch = async (clearConditions = true) => {
      if (clearConditions) {
        searchValues.value = [];
        activeValueType.value = null;
      } else {
        await initializationPromise;
      }
      await handleSearch();
    };

    onBeforeUnmount(() => {
      requestSequence += 1;
      cancelExecutor?.();
      cancelExecutor = null;
    });

    expose({ reSearch });

    return () => (
      <div class='search-bar card-base'>
        <div class='search-bar-input'>
          <bk-search-select
            ref={searchSelectRef}
            data={searchSelectData.value}
            values={searchValues.value}
            show-condition={false}
            show-popover-tag-change={false}
            remote-method={fetchOpenidOptions}
            key-delay={300}
            readonly={isValueInputReadonly.value}
            input-unfocus-clear={searchValues.value.length > 0}
            clearable
            onChange={handleValuesChange}
            onClear={handleClear}
            onInput-change={handleInputChange}
            onInput-click-outside={() => {
              activeValueType.value = null;
            }}
            onMenu-select={handleMenuSelect}
            onMenu-child-select={handleOpenidSelect}
            onKey-enter={handleSearch}
            onSearch={() => window.setTimeout(handleSearch, 20)}
          />
        </div>

        <div class='search-bar-time'>
          <TimeRange
            value={timeRange.value}
            timezone={timezone.value}
            onChange={handleTimeChange}
            on-timezone-change={handleTimezoneChange}
          />
        </div>

        <bk-button
          theme='primary'
          ext-cls='search-bar-btn'
          icon=' bklog-icon bklog-shoudongchaxun'
          disabled={isSearchDisabled.value}
          onClick={handleButtonSearch}
        >
          {t('查询')}
        </bk-button>
      </div>
    );
  },
});
