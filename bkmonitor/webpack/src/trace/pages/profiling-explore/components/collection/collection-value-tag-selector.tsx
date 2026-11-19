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
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions
 * of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import {
  type PropType,
  computed,
  defineComponent,
  nextTick,
  onMounted,
  onScopeDispose,
  shallowRef,
  useTemplateRef,
  watch,
} from 'vue';

import {
  COLLECTION_CANDIDATE_MAX_LIMIT,
  COLLECTION_CANDIDATE_PAGE_SIZE,
  getCollectionCandidates,
} from '../../services/collection-history';
import { PID_PREFIX } from '../../utils/collection-history';
import ValueTagSelector from '@/components/retrieval-filter/value-tag-selector';

import type { SelectionRange } from '../../types';
import type { CollectionCandidate, CollectionCandidateField } from '../../types/collection-history';
import type { IFieldItem, IGetValueFnParams, IOptionsInfo, IValue } from '@/components/retrieval-filter/typing';

import './collection-value-tag-selector.scss';

export type CollectionTagGroup = {
  field: CollectionCandidateField;
  values: string[];
};

const toTagId = (field: CollectionCandidateField, value: string) =>
  field === 'process_pids' ? `${PID_PREFIX}${value}` : value;

const toDisplayName = (field: CollectionCandidateField, value: string, alias?: string) =>
  field === 'process_pids' ? `${PID_PREFIX}${alias || value}` : alias || value;

/**
 * 采集筛选用的 tag 选择器：交互沿用 retrieval-filter 的 ValueTagSelector，
 * 这里只负责候选加载、值编码与别名缓存，不改动 ValueTagSelector 本身。
 */
export default defineComponent({
  name: 'CollectionValueTagSelector',
  props: {
    // 已选值按候选字段分组，PID 由本组件加前缀，外部始终传原始值
    value: { type: Array as PropType<CollectionTagGroup[]>, default: () => [] },
    fields: { type: Array as PropType<CollectionCandidateField[]>, default: () => [] },
    bizId: { type: Number, required: true },
    range: { type: Array as unknown as PropType<null | SelectionRange>, default: null },
    placeholder: { type: String, default: '' },
  },
  emits: {
    change: (_values: string[]) => true,
    error: (_hasError: boolean) => true,
  },
  setup(props, { emit }) {
    const selectorRef = useTemplateRef<{ handleGetOptions?: (options: IValue[]) => void }>('selector');
    // tag id → 别名；回填的 tag 首屏就能取到别名，不必等下拉加载
    const names = shallowRef<Map<string, string>>(new Map());
    // 候选结果缓存，预加载与首次打开下拉共用；时间范围变化时整体失效
    let candidateCache = new Map<string, CollectionCandidate[]>();
    let preloadToken = 0;
    let preloadController: AbortController | null = null;
    let valueController: AbortController | null = null;

    const selected = computed<IValue[]>(() =>
      props.value.flatMap(({ field, values }) =>
        values.map(value => {
          const id = toTagId(field, value);
          return { id, name: names.value.get(id) || toDisplayName(field, value) };
        })
      )
    );
    const fieldInfo = computed<IFieldItem>(() => ({
      alias: '',
      field: props.fields[0] || '',
      isEnableOptions: true,
      methods: [],
    }));

    function syncOptionsMap() {
      // 注入已选值的别名，ValueTagInput 依赖组件的 optionsMap 展示 tag 文案
      selectorRef.value?.handleGetOptions?.(selected.value);
    }

    function cacheCandidates(field: CollectionCandidateField, list: CollectionCandidate[]) {
      if (!list.length) return;
      const nextNames = new Map(names.value);
      for (const item of list) {
        const value = String(item.value);
        nextNames.set(toTagId(field, value), toDisplayName(field, value, item.alias));
      }
      names.value = nextNames;
    }

    // 同一组查询参数只请求一次，滚动加载提升 limit 时再取更大范围
    async function fetchCandidates(
      range: SelectionRange,
      field: CollectionCandidateField,
      keyword: string,
      limit: number,
      signal: AbortSignal
    ) {
      // 捕获请求发出时的业务、范围与缓存实例，返回后只写入属于这次上下文的缓存
      const bizId = props.bizId;
      const currentCache = candidateCache;
      const key = `${bizId}:${range[0]}:${range[1]}:${field}:${keyword}:${limit}`;
      const cached = currentCache.get(key);
      if (cached) return cached;
      const list = await getCollectionCandidates(bizId, range, field, { keyword, limit }, signal);
      if (signal.aborted || currentCache !== candidateCache) return [];
      currentCache.set(key, list);
      return list;
    }

    // 已选值不在首屏候选里时按值补搜一次，指针回填也能拿到别名
    async function fillSelectedNames(range: SelectionRange, signal: AbortSignal, token: number) {
      const missing = props.value.flatMap(({ field, values }) =>
        values.filter(value => !names.value.has(toTagId(field, value))).map(value => ({ field, value }))
      );
      if (!missing.length) return;
      const results = await Promise.allSettled(
        missing.map(({ field, value }) => fetchCandidates(range, field, value, COLLECTION_CANDIDATE_PAGE_SIZE, signal))
      );
      if (token !== preloadToken || signal.aborted) return;
      missing.forEach(({ field, value }, index) => {
        const result = results[index];
        if (result.status !== 'fulfilled') return;
        const matched = result.value.find(item => String(item.value) === value);
        // 补搜只是为了别名，命中不到时 tag 继续展示原始值
        if (matched) cacheCandidates(field, [matched]);
      });
    }

    // 静默预加载：不经过下拉的 loading，只用于建立别名与字段映射
    async function preload() {
      const range = props.range;
      if (!range || !props.fields.length) return;
      preloadController?.abort();
      const controller = new AbortController();
      preloadController = controller;
      const token = ++preloadToken;
      // 单个字段失败不影响其它字段的别名缓存
      const results = await Promise.allSettled(
        props.fields.map(field => fetchCandidates(range, field, '', COLLECTION_CANDIDATE_PAGE_SIZE, controller.signal))
      );
      if (token !== preloadToken || controller.signal.aborted) return;
      props.fields.forEach((field, index) => {
        const result = results[index];
        if (result.status === 'fulfilled') cacheCandidates(field, result.value);
      });
      await fillSelectedNames(range, controller.signal, token);
      if (token === preloadToken && !controller.signal.aborted) {
        syncOptionsMap();
      }
    }

    async function getValueFn(params: IGetValueFnParams): Promise<IOptionsInfo> {
      const range = props.range;
      if (!range || !props.fields.length) return { count: 0, list: [] };
      const keyword = params.search || '';
      const limit = Math.min(
        Math.max(params.limit || COLLECTION_CANDIDATE_PAGE_SIZE, COLLECTION_CANDIDATE_PAGE_SIZE),
        COLLECTION_CANDIDATE_MAX_LIMIT
      );
      valueController?.abort();
      const controller = new AbortController();
      valueController = controller;
      try {
        const results = await Promise.all(
          props.fields.map(field => fetchCandidates(range, field, keyword, limit, controller.signal))
        );
        if (controller.signal.aborted) return { count: 0, list: [] };
        // ValueOptions 用 limit > count 判断是否还有更多，多字段合并后需按单字段返回量计算：
        // 用合并总数会让 limit 达到上限后仍小于 count，滚动加载永远不会结束
        const count = Math.max(0, ...results.map(list => list.length));
        const candidates: IValue[] = [];
        props.fields.forEach((field, index) => {
          cacheCandidates(field, results[index]);
          for (const item of results[index]) {
            const value = String(item.value);
            candidates.push({ id: toTagId(field, value), name: toDisplayName(field, value, item.alias) });
          }
        });
        emit('error', false);
        return { count, list: candidates };
      } catch {
        if (!controller.signal.aborted) emit('error', true);
        return { count: 0, list: [] };
      }
    }

    function handleChange(values: IValue[]) {
      const nextNames = new Map(names.value);
      const ids: string[] = [];
      for (const item of values) {
        const id = String(item.id);
        // 选中或自定义输入后立即缓存别名，删除、回写时不再需要请求
        nextNames.set(id, item.name);
        ids.push(id);
      }
      names.value = nextNames;
      // 保留 PID 前缀下发，上层据此区分 process_names 与 process_pids
      emit('change', ids);
    }

    watch(
      () => props.value,
      () => {
        nextTick(() => syncOptionsMap());
      },
      { deep: true, immediate: true }
    );
    watch([() => props.bizId, () => props.range], () => {
      valueController?.abort();
      candidateCache = new Map();
      preload();
    });
    onMounted(preload);
    onScopeDispose(() => {
      preloadController?.abort();
      valueController?.abort();
    });

    return {
      fieldInfo,
      selected,
      getValueFn,
      handleChange,
    };
  },
  render() {
    return (
      <div class='collection-value-tag-selector'>
        <ValueTagSelector
          ref='selector'
          fieldInfo={this.fieldInfo}
          getValueFn={this.getValueFn}
          limit={COLLECTION_CANDIDATE_PAGE_SIZE}
          loadDelay={0}
          placeholder={this.placeholder}
          value={this.selected}
          onChange={this.handleChange}
        />
      </div>
    );
  },
});
