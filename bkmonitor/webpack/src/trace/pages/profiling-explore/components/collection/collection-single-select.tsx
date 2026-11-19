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
  onScopeDispose,
  shallowRef,
  useTemplateRef,
  watch,
} from 'vue';

import { onClickOutside, promiseTimeout } from '@vueuse/core';

import {
  COLLECTION_CANDIDATE_MAX_LIMIT,
  COLLECTION_CANDIDATE_PAGE_SIZE,
  getCollectionCandidates,
} from '../../services/collection-history';
import ValueOptions from '@/components/retrieval-filter/value-options';

import type { SelectionRange } from '../../types';
import type { IFieldItem, IGetValueFnParams, IOptionsInfo, IValue } from '@/components/retrieval-filter/typing';

import './collection-single-select.scss';

// 单选场景不在下拉里排除任何已选项，常量避免每次渲染都创建新数组
const EMPTY_SELECTED: string[] = [];

/**
 * 采集筛选的单选输入框：复用 ValueOptions 的候选下拉，
 * 支持选择候选、直接输入自定义值，以及清空。
 */
export default defineComponent({
  name: 'CollectionSingleSelect',
  props: {
    modelValue: { type: String, default: '' },
    bizId: { type: Number, required: true },
    range: { type: Array as unknown as PropType<null | SelectionRange>, default: null },
    placeholder: { type: String, default: '' },
  },
  emits: {
    change: (_value: string) => true,
    error: (_hasError: boolean) => true,
  },
  setup(props, { emit }) {
    const elRef = useTemplateRef<HTMLDivElement>('el');
    const inputRef = useTemplateRef<HTMLInputElement>('input');
    // 输入框展示值：未聚焦时等于外部值，聚焦后可编辑
    const inputValue = shallowRef('');
    // 下拉搜索词：聚焦时为空，展示全部候选；输入时跟随输入
    const searchValue = shallowRef('');
    const isFocus = shallowRef(false);
    const isShowDropDown = shallowRef(false);
    // ValueOptions 是否高亮了候选项，高亮时回车交给它选中
    const isChecked = shallowRef(false);
    const fieldInfo = computed<IFieldItem>(() => ({
      alias: '',
      field: 'task_name',
      isEnableOptions: true,
      methods: [],
    }));
    let cache = new Map<string, IValue[]>();
    let controller: AbortController | null = null;
    let stopOutside: (() => void) | null = null;

    watch(
      () => props.modelValue,
      value => {
        if (!isFocus.value) inputValue.value = value;
      },
      { immediate: true }
    );
    // 时间范围变化后候选失效，重新打开下拉时重新请求
    watch([() => props.bizId, () => props.range], () => {
      cache = new Map();
    });

    function openDropDown() {
      if (isShowDropDown.value) return;
      isShowDropDown.value = true;
      // 与检索栏的 tag 选择器一致：延迟注册外部点击，避免打开当次的点击立刻关闭
      setTimeout(() => {
        if (!isShowDropDown.value) return;
        stopOutside?.();
        stopOutside = onClickOutside(elRef.value, () => closeDropDown());
      }, 100);
    }

    function closeDropDown(restore = true) {
      isShowDropDown.value = false;
      isFocus.value = false;
      if (restore) inputValue.value = props.modelValue;
      stopOutside?.();
      stopOutside = null;
    }

    function handleFocus() {
      isFocus.value = true;
      inputValue.value = props.modelValue;
      searchValue.value = '';
      openDropDown();
      nextTick(() => inputRef.value?.select());
    }

    async function handleBlur() {
      isFocus.value = false;
      // 失焦后未确认的输入不保留，恢复为外部值
      await promiseTimeout(200);
      if (!isShowDropDown.value) inputValue.value = props.modelValue;
    }

    function handleInput(event: Event) {
      inputValue.value = (event.target as HTMLInputElement).value;
      searchValue.value = inputValue.value;
      isChecked.value = false;
      openDropDown();
    }

    function commit(value: string) {
      const name = value.trim();
      inputValue.value = name;
      searchValue.value = name;
      // 空值同样下发，用于清空任务筛选
      emit('change', name);
      closeDropDown(false);
    }

    function handleKeydown(event: KeyboardEvent) {
      if (event.key === 'Enter') {
        // 有高亮候选项时回车由 ValueOptions 处理选中
        if (isChecked.value) return;
        // 提交输入值后阻止冒泡，避免 ValueOptions 再按旧的高亮项选一次
        event.preventDefault();
        event.stopPropagation();
        commit(inputValue.value);
        return;
      }
      if (event.key === 'Escape') {
        closeDropDown();
      }
    }

    function handleSelect(item: IValue) {
      inputValue.value = item.name;
      searchValue.value = item.name;
      emit('change', item.name);
      closeDropDown(false);
    }

    function handleIsChecked(checked: boolean) {
      isChecked.value = checked;
    }

    async function getValueFn(params: IGetValueFnParams): Promise<IOptionsInfo> {
      const range = props.range;
      if (!range) return { count: 0, list: [] };
      const keyword = params.search || '';
      const limit = Math.min(
        Math.max(params.limit || COLLECTION_CANDIDATE_PAGE_SIZE, COLLECTION_CANDIDATE_PAGE_SIZE),
        COLLECTION_CANDIDATE_MAX_LIMIT
      );
      const key = `${keyword}:${limit}`;
      let list = cache.get(key);
      if (!list) {
        controller?.abort();
        const current = new AbortController();
        controller = current;
        try {
          const items = await getCollectionCandidates(
            props.bizId,
            range,
            'task_name',
            { keyword, limit },
            current.signal
          );
          if (current.signal.aborted) return { count: 0, list: [] };
          list = items.map(item => ({ id: String(item.value), name: item.alias || String(item.value) }));
          cache.set(key, list);
        } catch {
          if (!current.signal.aborted) emit('error', true);
          return { count: 0, list: [] };
        }
      }
      emit('error', false);
      return { count: list.length, list };
    }

    onScopeDispose(() => {
      controller?.abort();
      stopOutside?.();
    });

    return {
      inputValue,
      searchValue,
      isFocus,
      isShowDropDown,
      fieldInfo,
      getValueFn,
      handleBlur,
      handleFocus,
      handleInput,
      handleIsChecked,
      handleKeydown,
      handleSelect,
    };
  },
  render() {
    return (
      <div
        ref='el'
        class='collection-single-select'
      >
        <input
          ref='input'
          class='collection-single-select-input'
          placeholder={this.placeholder}
          value={this.inputValue}
          onBlur={this.handleBlur}
          onFocus={this.handleFocus}
          onInput={this.handleInput}
          onKeydown={this.handleKeydown}
        />
        {this.isShowDropDown && (
          <ValueOptions
            fieldInfo={this.fieldInfo}
            getValueFn={this.getValueFn}
            limit={COLLECTION_CANDIDATE_PAGE_SIZE}
            loadDelay={0}
            needUpDownCheck={this.isFocus}
            noDataSimple={true}
            search={this.searchValue}
            selected={EMPTY_SELECTED}
            onIsChecked={this.handleIsChecked}
            onSelect={this.handleSelect}
          />
        )}
      </div>
    );
  },
});
