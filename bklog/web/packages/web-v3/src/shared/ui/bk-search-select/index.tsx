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

import { Checkbox as TCheckbox, Popup as TPopup } from 'tdesign-vue-next';
import {
  computed,
  defineComponent,
  getCurrentInstance,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from 'vue';

import useLocale from '@/shared/composables/use-locale';
import { overlayRegistry } from '@/shared/global/overlay/overlay-registry.js';

import {
  buildSearchRecommendItems,
  computeSearchSelectOverflow,
  filterSearchChildOptions,
  formatSearchChipText,
  splitHighlightSegments,
  type SearchSelectOverflowResult,
  type SearchSelectRecord,
} from './helpers';

import './index.scss';

type SearchRecord = SearchSelectRecord;

const renderCheckIcon = () => (
  <svg
    class='item-check-icon'
    viewBox='0 0 16 16'
    width='14'
    height='14'
    fill='none'
    aria-hidden='true'
  >
    <path
      d='M3.2 8.2L6.6 11.4L13 4.8'
      stroke='currentColor'
      stroke-width='1.8'
      stroke-linecap='round'
      stroke-linejoin='round'
    />
  </svg>
);

const renderClearCircleIcon = () => (
  <svg
    class='search-clear-svg'
    viewBox='0 0 16 16'
    width='14'
    height='14'
    fill='currentColor'
    aria-hidden='true'
  >
    <path d='M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13Zm2.83 8.42a.65.65 0 1 1-.92.92L8 8.92l-1.91 1.92a.65.65 0 1 1-.92-.92L7.08 8 5.17 6.09a.65.65 0 1 1 .92-.92L8 7.08l1.91-1.91a.65.65 0 1 1 .92.92L8.92 8l1.91 1.92Z' />
  </svg>
);

const renderSearchIcon = () => (
  <svg
    class='search-nextfix-svg'
    viewBox='0 0 16 16'
    width='15'
    height='15'
    fill='none'
    aria-hidden='true'
  >
    <circle
      cx='7.25'
      cy='7.25'
      r='4.75'
      stroke='currentColor'
      stroke-width='1.4'
    />
    <path
      d='M10.8 10.8L14 14'
      stroke='currentColor'
      stroke-width='1.4'
      stroke-linecap='round'
    />
  </svg>
);

export default defineComponent({
  name: 'BkSearchSelect',
  props: {
    data: { type: Array, default: () => [] },
    values: { type: Array, default: undefined },
    modelValue: { type: Array, default: undefined },
    value: { type: Array, default: undefined },
    splitCode: { type: String, default: ' | ' },
    explainCode: { type: String, default: '：' },
    placeholder: { type: String, default: '' },
    emptyText: { type: String, default: '' },
    maxHeight: { type: [String, Number], default: 120 },
    minHeight: { type: [String, Number], default: 26 },
    shrink: { type: Boolean, default: true },
    displayKey: { type: String, default: 'name' },
    primaryKey: { type: String, default: 'id' },
    remoteMethod: { type: Function, default: undefined },
    remoteEmptyText: { type: String, default: '' },
    remoteLoadingText: { type: String, default: '' },
    keyDelay: { type: Number, default: 300 },
    showCondition: { type: Boolean, default: true },
    showPopoverTagChange: { type: Boolean, default: true },
    selectedStyle: { type: String, default: 'check' },
    readonly: { type: Boolean, default: false },
    clearable: { type: Boolean, default: false },
    inputUnfocusClear: { type: Boolean, default: false },
    popoverZindex: { type: Number, default: 0 },
    extCls: { type: String, default: '' },
  },
  emits: [
    'change',
    'input',
    'update:modelValue',
    'update:values',
    'clear',
    'search',
    'input-change',
    'input-click-outside',
    'menu-select',
    'menu-child-select',
    'child-checked',
    'chip-del',
    'key-delete',
    'key-enter',
    'show-menu',
  ],
  setup(props, { emit }) {
    const { t } = useLocale();
    const chips = ref<SearchRecord[]>([]);
    const wrapRef = ref<HTMLElement | null>(null);
    const selectBoxRef = ref<HTMLElement | null>(null);
    const searchInputRef = ref<HTMLElement | null>(null);
    const measureRef = ref<HTMLElement | null>(null);
    const menuListRef = ref<HTMLElement | null>(null);
    const popupRef = ref<any>(null);
    const inputRef = ref<HTMLElement | null>(null);
    const menuVisible = ref(false);
    const childMode = ref(false);
    const childLoading = ref(false);
    const fieldList = ref<SearchRecord[]>([]);
    const childList = ref<SearchRecord[]>([]);
    const hoverIndex = ref(-1);
    const popupZIndex = ref(overlayRegistry.nextZIndex());
    const overflowTooltipZIndex = ref(overlayRegistry.nextZIndex());
    const overflowState = ref<SearchSelectOverflowResult>({ visibleIndices: [], hiddenIndices: [] });
    const input = reactive({ value: '', focus: false });
    const menu = reactive({
      active: -1,
      id: null as string | number | null,
      checked: {} as Record<string, SearchRecord>,
    });
    const menuChildInstance = {
      get checked() {
        return menu.checked;
      },
      set checked(value: Record<string, SearchRecord>) {
        menu.checked = value || {};
      },
    };
    const menuInstance = ref<unknown>({});
    let searchTimer = 0;
    let requestSeq = 0;
    let closingBySelf = false;
    let resizeObserver: ResizeObserver | null = null;

    const externalValues = computed(() => {
      if (Array.isArray(props.value)) return props.value as SearchRecord[];
      if (Array.isArray(props.modelValue)) return props.modelValue as SearchRecord[];
      return (props.values || []) as SearchRecord[];
    });

    const isShrunk = computed(() => props.shrink && !input.focus);

    const activeFilterKeyword = computed(() => {
      const text = input.value || '';
      if (!childMode.value) return text.trim();
      const field = currentField();
      if (!field) return text.trim();
      if (Object.keys(menu.checked).length > 0) return '';
      const prefix = `${field[props.displayKey]}${props.explainCode}`;
      return text.startsWith(prefix) ? text.slice(prefix.length).trim() : '';
    });

    const chipText = (item: SearchRecord) =>
      formatSearchChipText(item, {
        displayKey: props.displayKey,
        explainCode: props.explainCode,
        splitCode: props.splitCode,
      });

    const syncPopper = () => {
      nextTick(() => {
        popupRef.value?.updatePopper?.();
      });
    };

    const recomputeOverflow = () => {
      if (!isShrunk.value || chips.value.length <= 1) {
        overflowState.value = {
          visibleIndices: chips.value.map((_, idx) => idx),
          hiddenIndices: [],
        };
        return;
      }

      const inputBox = searchInputRef.value;
      const measureEl = measureRef.value;
      if (!inputBox || !measureEl) {
        overflowState.value = {
          visibleIndices: chips.value.map((_, idx) => idx),
          hiddenIndices: [],
        };
        return;
      }

      const availableWidth = Math.max(0, inputBox.clientWidth - 10);
      if (availableWidth <= 0) return;

      const chipNodes = Array.from(
        measureEl.querySelectorAll<HTMLElement>('.bklog-search-select__measure-chip:not(.is-badge)'),
      );
      const badgeNode = measureEl.querySelector<HTMLElement>('.bklog-search-select__measure-chip.is-badge');
      const chipWidths = chipNodes.map(node => Math.ceil(node.getBoundingClientRect().width));
      const badgeWidth = badgeNode ? Math.ceil(badgeNode.getBoundingClientRect().width) : 34;

      if (chipWidths.length !== chips.value.length) return;

      overflowState.value = computeSearchSelectOverflow({
        chipWidths,
        availableWidth,
        chipGap: 6,
        badgeWidth,
      });
    };

    watch(
      externalValues,
      (value) => {
        if (value !== chips.value) chips.value = [...value];
        nextTick(recomputeOverflow);
      },
      { immediate: true, deep: true },
    );

    watch(
      () => input.value,
      (value) => {
        const element = inputRef.value;
        if (element && element.innerText !== value) element.innerText = value;
        if (menuVisible.value) syncPopper();
      },
    );

    watch(
      () => [input.focus, chips.value.length, props.shrink],
      () => {
        nextTick(() => {
          recomputeOverflow();
          if (menuVisible.value) syncPopper();
        });
      },
    );

    const currentField = () =>
      ((props.data || []) as SearchRecord[]).find(item => item?.[props.primaryKey] === menu.id) || null;

    const placeCaretAtEnd = () => {
      nextTick(() => {
        const element = inputRef.value;
        if (!element) return;
        element.focus();
        const selection = element.ownerDocument?.getSelection?.();
        if (!selection) return;
        const range = element.ownerDocument.createRange();
        range.selectNodeContents(element);
        range.collapse(false);
        selection.removeAllRanges();
        selection.addRange(range);
      });
    };

    const commit = (next: SearchRecord[], reopen = false) => {
      chips.value = next;
      emit('change', next);
      emit('input', next);
      emit('update:modelValue', next);
      emit('update:values', next);
      nextTick(() => {
        recomputeOverflow();
        if (reopen && props.showPopoverTagChange) {
          showMenu(true);
        } else if (menuVisible.value) {
          syncPopper();
        }
      });
    };

    const updateInput = (val = '') => {
      input.value = val;
      const element = inputRef.value;
      if (element && element.innerText !== val) element.innerText = val;
    };

    const clearInput = () => {
      const text = inputRef.value?.innerText || '';
      if (text.endsWith('\n') || text.startsWith('\n') || text.startsWith('\r')) {
        updateInput(text.replace(/[\r\n]/g, ''));
      }
    };

    const resetDraft = () => {
      menu.active = -1;
      menu.id = null;
      menu.checked = {};
      hoverIndex.value = -1;
      updateInput('');
      clearInput();
      childMode.value = false;
    };

    const hideMenu = () => {
      closingBySelf = true;
      menuVisible.value = false;
      hoverIndex.value = -1;
    };

    const showFieldMenu = () => {
      childMode.value = false;
      hoverIndex.value = -1;
      fieldList.value = (props.data || []) as SearchRecord[];
      menuVisible.value = fieldList.value.length > 0;
      syncPopper();
    };

    const showMenu = (show = true) => {
      if (!show) {
        hideMenu();
        return;
      }
      popupZIndex.value = Math.max(Number(props.popoverZindex) || 0, overlayRegistry.nextZIndex());
      showFieldMenu();
      emit('show-menu');
    };

    const refreshMenu = async (text: string) => {
      const field = currentField();
      const prefix = field ? `${field[props.displayKey]}${props.explainCode}` : '';
      if (field && text.startsWith(prefix)) {
        const hasChecked = Object.keys(menu.checked).length > 0;
        const filter = hasChecked ? '' : text.slice(prefix.length);
        childMode.value = true;
        hoverIndex.value = -1;
        const seq = ++requestSeq;
        if (field.remote && typeof props.remoteMethod === 'function') {
          childLoading.value = true;
          menuVisible.value = true;
          syncPopper();
          try {
            const list = await props.remoteMethod(filter, field, menu.active);
            if (seq !== requestSeq) return;
            childList.value = Array.isArray(list) ? list : [];
          } catch {
            if (seq !== requestSeq) return;
            childList.value = [];
          } finally {
            if (seq === requestSeq) childLoading.value = false;
          }
        } else {
          const children = Array.isArray(field.children) ? field.children : [];
          childList.value = filterSearchChildOptions({
            children,
            keyword: filter,
            displayKey: props.displayKey,
            primaryKey: props.primaryKey,
            hasCheckedItems: hasChecked,
          });
        }
        menuVisible.value = childLoading.value || childList.value.length > 0;
        syncPopper();
        return;
      }
      childMode.value = false;
      hoverIndex.value = -1;
      if (!text) {
        showFieldMenu();
        return;
      }
      fieldList.value = buildSearchRecommendItems({
        data: (props.data || []) as SearchRecord[],
        keyword: text,
        displayKey: props.displayKey,
        primaryKey: props.primaryKey,
        explainCode: props.explainCode,
      });
      menuVisible.value = fieldList.value.length > 0;
      syncPopper();
    };

    const scheduleSearch = (text: string) => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => refreshMenu(text), props.keyDelay);
    };

    const commitFieldValues = (values: SearchRecord[], reopen = true) => {
      const field = currentField();
      if (!field) {
        const text = input.value.trim();
        if (!text) return;
        commit([...chips.value, { [props.primaryKey]: text, [props.displayKey]: text }], reopen);
      } else {
        const { children, conditions, ...rest } = field;
        commit([...chips.value, { ...rest, values }], reopen);
      }
      menu.checked = {};
      menu.active = -1;
      menu.id = null;
      hoverIndex.value = -1;
      childMode.value = false;
      updateInput('');
      if (!reopen || !props.showPopoverTagChange) hideMenu();
      syncPopper();
    };

    const handleKeyEnter = async (event?: Event, needShowPopover = true, needEmitKeyEnter = false) => {
      event?.preventDefault?.();
      const text = input.value;
      if (!text) {
        if (needEmitKeyEnter) emit('key-enter', event);
        return;
      }
      const field = currentField();
      const prefix = field ? `${field[props.displayKey]}${props.explainCode}` : '';
      if (field && text === prefix) {
        childMode.value = true;
        menuVisible.value = true;
        if (!childList.value.length) refreshMenu(text);
        if (needEmitKeyEnter) emit('key-enter', event);
        return;
      }
      const checked = Object.values(menu.checked);
      if (field && checked.length) {
        commitFieldValues(checked, needShowPopover);
      } else if (field) {
        const raw = text.slice(prefix.length).trim();
        if (raw) {
          commitFieldValues([{ [props.primaryKey]: raw, [props.displayKey]: raw }], needShowPopover);
        }
      } else {
        commitFieldValues([], needShowPopover);
      }
      if (needEmitKeyEnter) emit('key-enter', event);
    };

    const selectField = (item: SearchRecord, index: number) => {
      if (item.recommendValue) {
        menu.id = item.recommendValue[props.primaryKey];
        commit([...chips.value, item.recommendValue], props.showPopoverTagChange);
        menu.id = null;
        hoverIndex.value = -1;
        updateInput('');
        if (!props.showPopoverTagChange) hideMenu();
        return;
      }
      menu.active = index;
      menu.id = item[props.primaryKey];
      menu.checked = {};
      hoverIndex.value = -1;
      const text = `${item[props.displayKey]}${props.explainCode}`;
      updateInput(text);
      emit('menu-select', item, index);
      refreshMenu(text);
      placeCaretAtEnd();
    };

    const updateCheckedInputValue = () => {
      const field = currentField();
      if (!field) return;
      const names = Object.values(menu.checked)
        .map(value => value[props.displayKey])
        .join(props.splitCode);
      updateInput(`${field[props.displayKey]}${props.explainCode}${names}`);
      placeCaretAtEnd();
      syncPopper();
    };

    const toggleCheck = (item: SearchRecord, index = -1) => {
      const key = String(item[props.primaryKey]);
      const nextChecked = !menu.checked[key];
      if (nextChecked) menu.checked[key] = item;
      else delete menu.checked[key];
      menu.checked = { ...menu.checked };
      updateCheckedInputValue();
      emit('child-checked', item, index, nextChecked);
    };

    const selectChild = (item: SearchRecord, index: number) => {
      emit('menu-child-select', item, index);
      const field = currentField();
      if (field?.multiable) {
        toggleCheck(item, index);
        return;
      }
      commitFieldValues([item]);
    };

    const scrollActiveMenuItemIntoView = () => {
      nextTick(() => {
        const listEl = menuListRef.value;
        if (!listEl || hoverIndex.value < 0) return;
        const items = listEl.querySelectorAll<HTMLElement>('.bk-search-list-menu-item');
        items[hoverIndex.value]?.scrollIntoView?.({ block: 'nearest' });
      });
    };

    const handleInputChange = (event: Event) => {
      const text = ((event.target as HTMLElement).innerText || '').replace(/[\r\n]/g, '');
      input.value = text;
      if (menu.id !== null) {
        const field = currentField();
        const prefix = field ? `${field[props.displayKey]}${props.explainCode}` : '';
        if (prefix && !text.startsWith(prefix)) {
          menu.active = -1;
          menu.id = null;
          menu.checked = {};
        } else if (field?.multiable && Object.keys(menu.checked).length > 0) {
          // User manually edited text while items were checked; clear checked map so filtering works naturally.
          const checkedSummary = `${prefix}${Object.values(menu.checked)
            .map(v => v[props.displayKey])
            .join(props.splitCode)}`;
          if (text !== checkedSummary) {
            menu.checked = {};
          }
        }
      }
      emit('input-change', event);
      scheduleSearch(text);
    };

    const handleKeydown = (event: KeyboardEvent) => {
      if (props.readonly && event.key !== 'Backspace') {
        event.preventDefault();
        return;
      }

      if (event.key === 'Escape') {
        if (menuVisible.value) {
          event.preventDefault();
          hideMenu();
        }
        return;
      }

      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        const list = childMode.value ? childList.value : fieldList.value;
        if (!menuVisible.value || !list.length) return;
        event.preventDefault();
        const delta = event.key === 'ArrowDown' ? 1 : -1;
        hoverIndex.value =
          hoverIndex.value < 0
            ? delta > 0
              ? 0
              : list.length - 1
            : (hoverIndex.value + delta + list.length) % list.length;
        scrollActiveMenuItemIntoView();
        return;
      }

      if (event.key === 'Enter') {
        const list = childMode.value ? childList.value : fieldList.value;
        if (menuVisible.value && hoverIndex.value >= 0 && list[hoverIndex.value]) {
          event.preventDefault();
          const targetItem = list[hoverIndex.value];
          if (childMode.value) {
            selectChild(targetItem, hoverIndex.value);
          } else {
            selectField(targetItem, hoverIndex.value);
          }
          return;
        }
        handleKeyEnter(event, true, true);
        return;
      }

      if (event.key === 'Backspace') {
        const field = currentField();
        const checkedKeys = Object.keys(menu.checked);
        if (field?.multiable && checkedKeys.length > 0) {
          event.preventDefault();
          const lastKey = checkedKeys[checkedKeys.length - 1];
          const removedItem = menu.checked[lastKey];
          delete menu.checked[lastKey];
          menu.checked = { ...menu.checked };
          updateCheckedInputValue();
          emit('child-checked', removedItem, -1, false);
          return;
        }

        if (!input.value) {
          if (!chips.value.length) return;
          event.preventDefault();
          const removed = chips.value[chips.value.length - 1];
          const next = chips.value.slice(0, -1);
          commit(next, false);
          emit('key-delete', removed);
          if (props.showPopoverTagChange) showMenu(true);
        }
      }
    };

    const onDocumentMousedown = (event: MouseEvent) => {
      if (!input.focus) return;
      const target = event.target as Node | null;
      const popupListEl = menuListRef.value?.closest('.bk-search-list') ?? menuListRef.value;
      if (target && (wrapRef.value?.contains(target) || popupListEl?.contains(target))) {
        return;
      }
      inputRef.value?.blur();
      handleOutside();
    };

    const bindOutsideGuard = () => {
      if (typeof document !== 'undefined') {
        document.addEventListener('mousedown', onDocumentMousedown, true);
      }
    };

    const unbindOutsideGuard = () => {
      if (typeof document !== 'undefined') {
        document.removeEventListener('mousedown', onDocumentMousedown, true);
      }
    };

    const handleFocus = () => {
      input.focus = true;
      bindOutsideGuard();
      popupZIndex.value = Math.max(Number(props.popoverZindex) || 0, overlayRegistry.nextZIndex());
      if (!input.value) {
        showFieldMenu();
      } else {
        const field = currentField();
        if (field && input.value.startsWith(`${field[props.displayKey]}${props.explainCode}`)) {
          refreshMenu(input.value);
        }
      }
      syncPopper();
    };

    const handleBlur = () => {
      input.focus = false;
      unbindOutsideGuard();
    };

    const handleOutside = () => {
      menuVisible.value = false;
      hoverIndex.value = -1;
      input.focus = false;
      unbindOutsideGuard();
      if (props.inputUnfocusClear) resetDraft();
      emit('input-click-outside', { target: inputRef.value });
      nextTick(recomputeOverflow);
    };

    const handleVisibleChange = (visible: boolean, context?: { trigger?: string }) => {
      // Focus opens the field menu before the same pointer click reaches Popup.
      // Clicking within an editable search field must not toggle that menu closed.
      if (!visible && context?.trigger === 'trigger-element-click') return;
      if (visible) {
        menuVisible.value = true;
        input.focus = true;
        bindOutsideGuard();
        if (!input.value && !childMode.value) showFieldMenu();
        syncPopper();
        return;
      }
      if (closingBySelf) {
        closingBySelf = false;
        if (!context?.trigger) {
          menuVisible.value = false;
          return;
        }
      }
      handleOutside();
    };

    const handleClearAll = (event: Event) => {
      event.stopPropagation();
      resetDraft();
      hideMenu();
      commit([]);
      emit('clear', event);
    };

    const handleSearchClick = (event: Event) => {
      event.stopPropagation();
      handleKeyEnter(event, false, false);
      emit('search', event);
    };

    const removeChip = (index: number, event: Event) => {
      event.stopPropagation();
      const removed = chips.value[index];
      const next = chips.value.filter((_, itemIndex) => itemIndex !== index);
      commit(next, false);
      emit('chip-del', [removed]);
      if (input.focus && !input.value) showMenu(true);
    };

    const handleMultiConfirm = () => {
      const checked = Object.values(menu.checked);
      if (checked.length) {
        commitFieldValues(checked, true);
        placeCaretAtEnd();
        return;
      }
      const field = currentField();
      const prefix = field ? `${field[props.displayKey]}${props.explainCode}` : '';
      const raw = prefix && input.value.startsWith(prefix) ? input.value.slice(prefix.length).trim() : '';
      if (raw) {
        commitFieldValues([{ [props.primaryKey]: raw, [props.displayKey]: raw }], true);
        placeCaretAtEnd();
      }
    };

    const handleMultiCancel = () => {
      resetDraft();
      hideMenu();
      placeCaretAtEnd();
    };

    const setupResizeObserver = () => {
      resizeObserver?.disconnect();
      if (typeof ResizeObserver === 'undefined') return;
      resizeObserver = new ResizeObserver(() => {
        recomputeOverflow();
        if (menuVisible.value) syncPopper();
      });
      if (wrapRef.value) resizeObserver.observe(wrapRef.value);
      if (selectBoxRef.value) resizeObserver.observe(selectBoxRef.value);
    };

    if (getCurrentInstance()) {
      onMounted(() => {
        setupResizeObserver();
        nextTick(recomputeOverflow);
      });
    }

    onBeforeUnmount(() => {
      window.clearTimeout(searchTimer);
      unbindOutsideGuard();
      resizeObserver?.disconnect();
    });

    const renderHighlightedText = (text: string, keyword: string) => {
      const segments = splitHighlightSegments(text, keyword);
      if (segments.length === 1 && !segments[0].matched) return text;
      return segments.map((seg, idx) =>
        seg.matched ? (
          <span
            key={idx}
            class='item-name-filter'
          >
            {seg.text}
          </span>
        ) : (
          seg.text
        ),
      );
    };

    const renderMenu = () => {
      const loadingText = props.remoteLoadingText || t('加载中...');
      const emptyText = childMode.value
        ? props.remoteEmptyText || props.emptyText || t('暂无数据')
        : props.emptyText || t('暂无数据');
      const list = childMode.value ? childList.value : fieldList.value;
      const multiable = childMode.value && !!currentField()?.multiable;
      const useCheckboxStyle = props.selectedStyle === 'checkbox';
      const keyword = activeFilterKeyword.value;
      const hasChecked = Object.keys(menu.checked).length > 0;

      return (
        <div
          class='bk-search-list bklog-popover-stop'
          onMousedown={(event: MouseEvent) => event.preventDefault()}
        >
          <div
            ref={menuListRef}
            class='bk-search-list-menu'
          >
            {childLoading.value ? (
              <div class='bk-search-list-loading'>
                <span
                  class='bklog-loading-mark'
                  role='status'
                  aria-label={loadingText}
                />
              </div>
            ) : null}
            {!childLoading.value && !list.length ? <div class='bk-search-list-error'>{emptyText}</div> : null}
            {list.map((item, index) => {
              const itemKey = String(item?.[props.primaryKey] ?? index);
              const isChecked = multiable && !!menu.checked[itemKey];
              const isHovered = hoverIndex.value === index;
              const itemClass = isHovered ? 'bk-search-list-menu-item is-hover' : 'bk-search-list-menu-item';
              const displayLabel = String(item?.[props.displayKey] ?? '');

              return (
                <div
                  key={`${itemKey}-${index}`}
                  class={itemClass}
                  onMouseenter={() => {
                    hoverIndex.value = index;
                  }}
                  onMouseleave={() => {
                    if (hoverIndex.value === index) hoverIndex.value = -1;
                  }}
                  onMousedown={(event: MouseEvent) => event.preventDefault()}
                  onClick={() => (childMode.value ? selectChild(item, index) : selectField(item, index))}
                >
                  {multiable && useCheckboxStyle ? (
                    <TCheckbox
                      class='search-list-checkbox'
                      checked={isChecked}
                    />
                  ) : null}
                  <span
                    class='item-name'
                    title={displayLabel}
                  >
                    {renderHighlightedText(displayLabel, keyword)}
                  </span>
                  {multiable && !useCheckboxStyle && isChecked ? renderCheckIcon() : null}
                </div>
              );
            })}
          </div>
          {multiable && !childLoading.value ? (
            <div class='bk-search-list-footer'>
              <span
                class={['footer-btn', 'is-confirm', { 'is-disabled': !hasChecked && !keyword }]}
                onMousedown={(event: MouseEvent) => event.preventDefault()}
                onClick={handleMultiConfirm}
              >
                {t('确认')}
              </span>
              <span
                class='footer-btn is-cancel'
                onMousedown={(event: MouseEvent) => event.preventDefault()}
                onClick={handleMultiCancel}
              >
                {t('取消')}
              </span>
            </div>
          ) : null}
        </div>
      );
    };

    return {
      chips,
      wrapRef,
      selectBoxRef,
      searchInputRef,
      measureRef,
      popupRef,
      input,
      inputRef,
      menu,
      menuChildInstance,
      menuInstance,
      menuVisible,
      hoverIndex,
      popupZIndex,
      overflowTooltipZIndex,
      overflowState,
      isShrunk,
      handleKeyEnter,
      showMenu,
      updateInput,
      clearInput,
      handleInputChange,
      handleKeydown,
      handleFocus,
      handleBlur,
      handleVisibleChange,
      handleClearAll,
      handleSearchClick,
      removeChip,
      chipText,
      renderMenu,
    };
  },
  render() {
    const maxHeight = this.input.focus || !this.shrink ? this.maxHeight : this.minHeight;
    const isShrunk = this.isShrunk;
    const visibleIndices =
      isShrunk && this.overflowState.visibleIndices.length > 0
        ? this.overflowState.visibleIndices
        : this.chips.map((_: SearchRecord, idx: number) => idx);
    const hiddenIndices = isShrunk ? this.overflowState.hiddenIndices : [];
    const hiddenTooltipLines = hiddenIndices.map((idx: number) => this.chipText(this.chips[idx]));
    const collapseEmptyInput = isShrunk && this.chips.length > 0 && !this.input.value;

    return (
      <div
        ref='wrapRef'
        class={[
          'search-select-wrap',
          'bklog-search-select',
          {
            'is-focus': this.input.focus,
            'is-shrink': isShrunk,
          },
          this.extCls,
        ]}
      >
        <TPopup
          ref='popupRef'
          visible={this.menuVisible}
          attach='body'
          placement='bottom-left'
          showArrow={false}
          trigger='click'
          zIndex={this.popupZIndex}
          overlayClassName='bklog-search-select-popup'
          overlayInnerStyle={{ padding: '0' }}
          onVisibleChange={this.handleVisibleChange}
          content={this.renderMenu}
        >
          <div
            ref='selectBoxRef'
            class={['bk-search-select', { 'is-focus': this.input.focus, 'is-shrink': isShrunk }]}
          >
            <div
              ref='searchInputRef'
              class='search-input'
              style={{ maxHeight: `${maxHeight}px` }}
              onClick={() => this.inputRef?.focus()}
            >
              {visibleIndices.map((chipIdx: number) => {
                const item = this.chips[chipIdx];
                if (!item) return null;
                return (
                  <div
                    key={`${item?.[this.primaryKey]}-${chipIdx}`}
                    class={['search-input-chip', { 'is-single-line': isShrunk }]}
                  >
                    <span class='chip-name'>{this.chipText(item)}</span>
                    <span
                      class='chip-clear'
                      onMousedown={(event: MouseEvent) => event.preventDefault()}
                      onClick={(event: MouseEvent) => this.removeChip(chipIdx, event)}
                    >
                      ×
                    </span>
                  </div>
                );
              })}
              {hiddenIndices.length > 0 ? (
                <TPopup
                  trigger='hover'
                  placement='top'
                  attach='body'
                  showArrow={true}
                  zIndex={this.overflowTooltipZIndex}
                  overlayClassName='bklog-search-select-overflow-tooltip'
                  content={() => (
                    <div class='bklog-search-select-overflow-tooltip__content'>
                      {hiddenTooltipLines.map((line: string, lineIdx: number) => (
                        <div
                          key={lineIdx}
                          class='bklog-search-select-overflow-tooltip__line'
                        >
                          {line}
                        </div>
                      ))}
                    </div>
                  )}
                >
                  <div
                    class='search-input-chip overflow-chip'
                    onMouseenter={() => {
                      this.overflowTooltipZIndex = overlayRegistry.nextZIndex();
                    }}
                  >
                    +{hiddenIndices.length}
                  </div>
                </TPopup>
              ) : null}
              <div class={['search-input-input', { 'is-collapsed-empty': collapseEmptyInput }]}>
                <div
                  key='bk-search-select-input'
                  ref={(element: HTMLElement | null) => {
                    this.inputRef = element;
                  }}
                  class={['div-input', { 'input-before': !this.chips.length && !this.input.value }]}
                  contenteditable='plaintext-only'
                  data-placeholder={this.placeholder}
                  spellcheck='false'
                  onFocus={this.handleFocus}
                  onBlur={this.handleBlur}
                  onInput={this.handleInputChange}
                  onKeydown={this.handleKeydown}
                />
              </div>
            </div>
            <div class='search-nextfix'>
              {this.clearable && (this.chips.length || this.input.value) ? (
                <span
                  role='button'
                  tabindex={-1}
                  class='search-clear'
                  onMousedown={(event: MouseEvent) => event.preventDefault()}
                  onClick={this.handleClearAll}
                >
                  {renderClearCircleIcon()}
                </span>
              ) : null}
              <span
                role='button'
                tabindex={-1}
                class={['search-nextfix-icon', { 'is-focus': this.input.focus }]}
                onMousedown={(event: MouseEvent) => event.preventDefault()}
                onClick={this.handleSearchClick}
              >
                {renderSearchIcon()}
              </span>
            </div>
          </div>
        </TPopup>
        {isShrunk && this.chips.length > 1 ? (
          <div
            ref='measureRef'
            class='bklog-search-select__measure'
            aria-hidden='true'
          >
            {this.chips.map((item: SearchRecord, idx: number) => (
              <span
                key={`m-${idx}`}
                class='bklog-search-select__measure-chip'
              >
                {this.chipText(item)}
              </span>
            ))}
            <span class='bklog-search-select__measure-chip is-badge'>+{this.chips.length}</span>
          </div>
        ) : null}
      </div>
    );
  },
});
