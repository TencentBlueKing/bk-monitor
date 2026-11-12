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
import { computed, defineComponent, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue';

import { overlayRegistry } from '@/shared/global/overlay/overlay-registry.js';
import useLocale from '@/shared/composables/use-locale';

import './index.scss';

type SearchRecord = Record<string, any>;

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
    'key-enter',
    'show-menu',
  ],
  setup(props, { emit }) {
    const { t } = useLocale();
    const chips = ref<SearchRecord[]>([]);
    const inputRef = ref<HTMLElement | null>(null);
    const menuVisible = ref(false);
    const childMode = ref(false);
    const childLoading = ref(false);
    const fieldList = ref<SearchRecord[]>([]);
    const childList = ref<SearchRecord[]>([]);
    const popupZIndex = ref(overlayRegistry.nextZIndex());
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

    const externalValues = computed(() => {
      if (Array.isArray(props.value)) return props.value as SearchRecord[];
      if (Array.isArray(props.modelValue)) return props.modelValue as SearchRecord[];
      return (props.values || []) as SearchRecord[];
    });

    watch(
      externalValues,
      (value) => {
        if (value !== chips.value) chips.value = [...value];
      },
      { immediate: true, deep: true },
    );

    watch(
      () => input.value,
      (value) => {
        const element = inputRef.value;
        if (element && element.innerText !== value) element.innerText = value;
      },
    );

    const currentField = () =>
      ((props.data || []) as SearchRecord[]).find(item => item?.[props.primaryKey] === menu.id) || null;

    const chipText = (item: SearchRecord) => {
      const name = String(item?.[props.displayKey] ?? '');
      const values = Array.isArray(item?.values) ? item.values : [];
      if (!values.length) return name;
      const condition = item.condition?.[props.displayKey] ? String(item.condition[props.displayKey]) : '';
      return name + props.explainCode + condition + values.map((value: SearchRecord) => value?.[props.displayKey]).join(props.splitCode);
    };

    const commit = (next: SearchRecord[], reopen = false) => {
      chips.value = next;
      emit('change', next);
      emit('input', next);
      emit('update:modelValue', next);
      emit('update:values', next);
      if (reopen && props.showPopoverTagChange) {
        nextTick(() => showMenu(true));
      }
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
      updateInput('');
      clearInput();
      childMode.value = false;
    };

    const hideMenu = () => {
      closingBySelf = true;
      menuVisible.value = false;
    };

    const showFieldMenu = () => {
      childMode.value = false;
      fieldList.value = (props.data || []) as SearchRecord[];
      menuVisible.value = fieldList.value.length > 0;
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

    const buildRecommend = (keyword: string) => {
      const list: SearchRecord[] = [];
      ((props.data || []) as SearchRecord[]).forEach((item) => {
        const children = Array.isArray(item.children) ? item.children : [];
        const matched = children.filter((child: SearchRecord) => String(child?.[props.displayKey] ?? '').includes(keyword));
        if (matched.length) {
          matched.forEach((child: SearchRecord) => {
            list.push({
              ...item,
              [props.displayKey]: `${item[props.displayKey]}${props.explainCode}${child[props.displayKey]}`,
              [props.primaryKey]: `${item[props.primaryKey]}${props.explainCode}${child[props.primaryKey]}`,
              recommendValue: {
                [props.displayKey]: item[props.displayKey],
                [props.primaryKey]: item[props.primaryKey],
                values: [{ [props.displayKey]: child[props.displayKey], [props.primaryKey]: child[props.primaryKey] }],
              },
            });
          });
          return;
        }
        if (String(item?.[props.displayKey] ?? '').includes(keyword)) list.push(item);
      });
      return list;
    };

    const refreshMenu = async (text: string) => {
      const field = currentField();
      const prefix = field ? `${field[props.displayKey]}${props.explainCode}` : '';
      if (field && text.startsWith(prefix)) {
        const filter = text.slice(prefix.length);
        childMode.value = true;
        const seq = ++requestSeq;
        if (field.remote && typeof props.remoteMethod === 'function') {
          childLoading.value = true;
          menuVisible.value = true;
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
          childList.value = filter
            ? children.filter((item: SearchRecord) => String(item?.[props.displayKey] ?? '').includes(filter))
            : children;
        }
        menuVisible.value = childLoading.value || childList.value.length > 0;
        return;
      }
      childMode.value = false;
      if (!text) {
        showFieldMenu();
        return;
      }
      fieldList.value = buildRecommend(text);
      menuVisible.value = fieldList.value.length > 0;
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
      childMode.value = false;
      updateInput('');
      if (!reopen || !props.showPopoverTagChange) hideMenu();
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
        updateInput('');
        if (!props.showPopoverTagChange) hideMenu();
        return;
      }
      menu.active = index;
      menu.id = item[props.primaryKey];
      menu.checked = {};
      const text = `${item[props.displayKey]}${props.explainCode}`;
      updateInput(text);
      emit('menu-select', item, index);
      refreshMenu(text);
      nextTick(() => {
        const element = inputRef.value;
        if (!element) return;
        element.focus();
        // Replacing contenteditable text does not move its caret after the field prefix.
        const selection = element.ownerDocument.getSelection();
        if (!selection) return;
        const range = element.ownerDocument.createRange();
        range.selectNodeContents(element);
        range.collapse(false);
        selection.removeAllRanges();
        selection.addRange(range);
      });
    };

    const toggleCheck = (item: SearchRecord) => {
      const key = String(item[props.primaryKey]);
      if (menu.checked[key]) delete menu.checked[key];
      else menu.checked[key] = item;
      menu.checked = { ...menu.checked };
      const field = currentField();
      if (!field) return;
      const names = Object.values(menu.checked).map(value => value[props.displayKey]).join(props.splitCode);
      updateInput(`${field[props.displayKey]}${props.explainCode}${names}`);
    };

    const selectChild = (item: SearchRecord, index: number) => {
      emit('menu-child-select', item, index);
      const field = currentField();
      if (field?.multiable) {
        toggleCheck(item);
        return;
      }
      commitFieldValues([item]);
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
      if (event.key === 'Enter') {
        handleKeyEnter(event, true, true);
        return;
      }
      if (event.key === 'Backspace' && !input.value) {
        if (!chips.value.length) return;
        event.preventDefault();
        const next = chips.value.slice(0, -1);
        commit(next, false);
        if (props.showPopoverTagChange) showMenu(true);
      }
    };

    const handleFocus = () => {
      input.focus = true;
      popupZIndex.value = Math.max(Number(props.popoverZindex) || 0, overlayRegistry.nextZIndex());
      if (!input.value) showFieldMenu();
    };

    const handleBlur = () => {
      input.focus = false;
    };

    const handleOutside = () => {
      menuVisible.value = false;
      input.focus = false;
      if (props.inputUnfocusClear) resetDraft();
      emit('input-click-outside', { target: inputRef.value });
    };

    const handleVisibleChange = (visible: boolean, context?: { trigger?: string }) => {
      // Focus opens the field menu before the same pointer click reaches Popup.
      // Clicking within an editable search field must not toggle that menu closed.
      if (!visible && context?.trigger === 'trigger-element-click') return;
      if (visible) {
        menuVisible.value = true;
        input.focus = true;
        if (!input.value && !childMode.value) showFieldMenu();
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
      const next = chips.value.filter((_, itemIndex) => itemIndex !== index);
      commit(next, false);
      if (!input.value) showMenu(true);
    };

    onBeforeUnmount(() => window.clearTimeout(searchTimer));

    const renderMenu = () => {
      const loadingText = props.remoteLoadingText || t('加载中...');
      const emptyText = childMode.value ? props.remoteEmptyText || props.emptyText || t('暂无数据') : props.emptyText || t('暂无数据');
      const list = childMode.value ? childList.value : fieldList.value;
      const multiable = childMode.value && !!currentField()?.multiable;
      return (
        <div class='bk-search-list'>
          <div class='bk-search-list-menu'>
            {childLoading.value ? <div class='bk-search-list-loading'><span class='bklog-loading-mark' role='status' aria-label={loadingText} /></div> : null}
            {!childLoading.value && !list.length ? <div class='bk-search-list-error'>{emptyText}</div> : null}
            {list.map((item, index) => (
              <div
                key={`${item?.[props.primaryKey]}-${index}`}
                class='bk-search-list-menu-item'
                onMousedown={(event: MouseEvent) => event.preventDefault()}
                onClick={() => (childMode.value ? selectChild(item, index) : selectField(item, index))}
              >
                {multiable ? (
                  <TCheckbox
                    class='search-list-checkbox'
                    checked={!!menu.checked[String(item[props.primaryKey])]}
                  />
                ) : null}
                <span class='item-name'>{item?.[props.displayKey]}</span>
              </div>
            ))}
          </div>
          {multiable ? (
            <div class='bk-search-list-footer'>
              <span
                class='footer-btn'
                onMousedown={(event: MouseEvent) => event.preventDefault()}
                onClick={() => {
                  const checked = Object.values(menu.checked);
                  if (checked.length) commitFieldValues(checked);
                }}
              >
                {t('确定')}
              </span>
              <span
                class='footer-btn'
                onMousedown={(event: MouseEvent) => event.preventDefault()}
                onClick={() => {
                  menu.checked = {};
                  const field = currentField();
                  if (field) updateInput(`${field[props.displayKey]}${props.explainCode}`);
                  hideMenu();
                }}
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
      input,
      inputRef,
      menu,
      menuChildInstance,
      menuInstance,
      menuVisible,
      popupZIndex,
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
    return (
      <TPopup
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
          class={['search-select-wrap', 'bklog-search-select', this.extCls]}
          style={{ zIndex: 'var(--bklog-z-page)' }}
        >
          <div class={['bk-search-select', { 'is-focus': this.input.focus }]}>
            <div
              class='search-input'
              style={{ maxHeight: `${maxHeight}px` }}
              onClick={() => this.inputRef?.focus()}
            >
              {this.chips.map((item: SearchRecord, index: number) => (
                <div
                  key={`${item?.[this.primaryKey]}-${index}`}
                  class='search-input-chip'
                >
                  <span class='chip-name'>{this.chipText(item)}</span>
                  <span
                    class='chip-clear'
                    onMousedown={(event: MouseEvent) => event.preventDefault()}
                    onClick={(event: MouseEvent) => this.removeChip(index, event)}
                  >
                    ×
                  </span>
                </div>
              ))}
              <div class='search-input-input'>
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
                <i
                  class='search-clear bklog-icon bklog-close'
                  onMousedown={(event: MouseEvent) => event.preventDefault()}
                  onClick={this.handleClearAll}
                />
              ) : null}
              <i
                class={['bklog-icon', 'bklog-search', 'search-nextfix-icon', { 'is-focus': this.input.focus }]}
                onMousedown={(event: MouseEvent) => event.preventDefault()}
                onClick={this.handleSearchClick}
              />
            </div>
          </div>
        </div>
      </TPopup>
    );
  },
});
