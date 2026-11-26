/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { CloseCircleFilledIcon } from 'tdesign-icons-vue-next';
import {
  Popup as TPopup,
  Tag as TTag,
  TagInput as TTagInput,
  Tooltip as TTooltip,
  type TagInputChangeContext,
  type TagInputProps,
} from 'tdesign-vue-next';
import {
  computed,
  defineComponent,
  getCurrentInstance,
  h,
  nextTick,
  normalizeClass,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type PropType,
  type VNodeChild,
} from 'vue';

import { overlayRegistry } from '@/shared/global/overlay/overlay-registry.js';

import {
  computeCollapsedVisibleCount,
  filterTagOptions,
  normalizeTagOptions,
  parsePastedTags,
  resolveTagAddition,
  type NormalizedTagOption,
} from './helpers';

import './index.scss';

const getModelValue = (props: { modelValue?: unknown[]; value?: unknown[] }) =>
  props.modelValue !== undefined ? props.modelValue : props.value;

export default defineComponent({
  name: 'BkTagInput',
  inheritAttrs: false,
  props: {
    value: { type: Array as PropType<Array<string | number>>, default: () => [] },
    modelValue: { type: Array as PropType<Array<string | number>>, default: undefined },
    inputValue: { type: String, default: undefined },
    placeholder: { type: String, default: '' },
    disabled: { type: Boolean, default: false },
    readonly: { type: Boolean, default: false },
    clearable: { type: Boolean, default: true },
    extCls: { type: String, default: '' },
    popoverClassName: { type: String, default: '' },
    hasDeleteIcon: { type: [Boolean, String] as PropType<boolean | string>, default: undefined },
    maxData: { type: [Number, String], default: undefined },
    max: { type: [Number, String], default: undefined },
    pasteFn: { type: Function as PropType<(value: string) => unknown>, default: undefined },
    freePaste: { type: Boolean, default: false },
    separator: { type: String, default: '' },
    list: { type: Array as PropType<unknown[]>, default: () => [] },
    saveKey: { type: String, default: 'id' },
    displayKey: { type: String, default: 'name' },
    searchKey: { type: [String, Array] as PropType<string | string[]>, default: 'name' },
    tooltipKey: { type: String, default: '' },
    trigger: { type: String as PropType<'focus' | 'search'>, default: 'search' },
    tpl: { type: Function as PropType<(node: Record<string, unknown>, ctx?: unknown) => VNodeChild>, default: undefined },
    tagTpl: { type: Function as PropType<(node: Record<string, unknown>) => VNodeChild>, default: undefined },
    allowCreate: { type: Boolean, default: true },
    allowAutoMatch: { type: Boolean, default: false },
    allowNextFocus: { type: Boolean, default: true },
    collapseTags: { type: Boolean, default: false },
    minCollapsedNum: { type: Number, default: 0 },
    collapsedItems: { type: Function as PropType<TagInputProps['collapsedItems']>, default: undefined },
    contentWidth: { type: Number, default: undefined },
    contentMaxHeight: { type: Number, default: 240 },
    size: { type: String as PropType<'small' | 'medium' | 'large'>, default: 'medium' },
    status: { type: String as PropType<'default' | 'success' | 'warning' | 'error'>, default: undefined },
    excessTagsDisplayType: { type: String as PropType<'break-line' | 'scroll'>, default: 'break-line' },
    tagProps: { type: Object as PropType<Record<string, unknown>>, default: undefined },
  },
  emits: [
    'update:modelValue',
    'change',
    'input',
    'select',
    'blur',
    'focus',
    'enter',
    'remove',
    'remove-all',
    'removeAll',
    'inputchange',
    'input-change',
    'clear',
  ],
  setup(props, { attrs, emit, expose, slots }) {
    const hostRef = ref<HTMLElement | null>(null);
    const tagInputRef = ref<any>(null);
    const popupRef = ref<any>(null);
    const measureRef = ref<HTMLElement | null>(null);
    const optionListRef = ref<HTMLElement | null>(null);

    const innerInputValue = ref('');
    const isFocused = ref(false);
    const activeOptionIndex = ref(-1);
    const dynamicVisibleCount = ref(0);
    const triggerWidth = ref(0);
    const popupZIndex = ref(overlayRegistry.nextZIndex());
    const tooltipZIndex = ref(overlayRegistry.nextZIndex());

    let hostObserver: ResizeObserver | null = null;
    let controlObserver: ResizeObserver | null = null;
    let boundFocusEl: HTMLElement | null = null;

    const currentTags = computed(() =>
      ((getModelValue(props) as Array<string | number>) || []).map(item => String(item)),
    );

    const resolvedInputValue = computed(() =>
      props.inputValue !== undefined ? String(props.inputValue) : innerInputValue.value,
    );

    const resolvedMax = computed(() => {
      if (props.max !== undefined) return Number(props.max);
      if (props.maxData !== undefined) return Number(props.maxData);
      return undefined;
    });

    const disableTagClose = computed(() => props.hasDeleteIcon === false || props.hasDeleteIcon === 'false');

    const normalizedOptions = computed(() =>
      normalizeTagOptions(props.list, props.saveKey, props.displayKey, props.tooltipKey),
    );

    const optionMap = computed(() => {
      const map = new Map<string, NormalizedTagOption>();
      for (const option of normalizedOptions.value) {
        map.set(option.id, option);
      }
      return map;
    });

    const filteredOptions = computed(() =>
      filterTagOptions({
        options: normalizedOptions.value,
        selected: currentTags.value,
        keyword: resolvedInputValue.value,
        searchKey: props.searchKey,
      }),
    );

    const hasOptionsList = computed(() => normalizedOptions.value.length > 0);

    const dropdownVisible = computed(() => {
      if (!hasOptionsList.value || props.disabled || props.readonly || !isFocused.value) return false;
      if (props.trigger !== 'focus' && !resolvedInputValue.value.trim()) return false;
      return filteredOptions.value.length > 0;
    });

    const getTagDisplayText = (value: string) => optionMap.value.get(value)?.name ?? value;

    const instance = getCurrentInstance();

    const getControlElement = (): HTMLElement | null => {
      const refEl = tagInputRef.value?.$el ?? tagInputRef.value;
      if (refEl instanceof HTMLElement) return refEl;
      if (hostRef.value) {
        return hostRef.value.querySelector<HTMLElement>('.t-tag-input') ?? hostRef.value;
      }
      const rootEl = instance?.proxy?.$el;
      if (rootEl instanceof HTMLElement) {
        return rootEl.classList.contains('t-tag-input')
          ? rootEl
          : (rootEl.querySelector<HTMLElement>('.t-tag-input') ?? rootEl);
      }
      return null;
    };

    const setInputValue = (value: string, context?: unknown) => {
      innerInputValue.value = value;
      emit('inputchange', value, context);
      emit('input-change', value, context);
    };

    const publish = (nextValue: string[]) => {
      emit('update:modelValue', nextValue);
      emit('input', nextValue);
      emit('change', nextValue);
    };

    const syncPopper = () => {
      nextTick(() => {
        const controlEl = getControlElement();
        if (controlEl) {
          triggerWidth.value = controlEl.getBoundingClientRect().width;
        }
        popupRef.value?.updatePopper?.();
      });
    };

    const recomputeVisibleCount = () => {
      if (!props.collapseTags || isFocused.value || currentTags.value.length <= 1) {
        dynamicVisibleCount.value = 0;
        return;
      }

      const controlEl = getControlElement();
      const inputBox = controlEl?.querySelector<HTMLElement>(':scope > .t-input') ?? controlEl;
      const measureEl = measureRef.value;
      if (!inputBox || !measureEl) return;

      const boxWidth = inputBox.getBoundingClientRect().width;
      if (boxWidth <= 0) return;

      const style = window.getComputedStyle(inputBox);
      const paddingLeft = Number.parseFloat(style.paddingLeft) || 4;
      const paddingRight = Number.parseFloat(style.paddingRight) || 8;
      const hasClear = props.clearable && !props.disabled && !props.readonly && currentTags.value.length > 0;
      const rightReserve = Math.max(paddingRight, hasClear ? 30 : 8);
      const availableWidth = Math.max(0, boxWidth - paddingLeft - rightReserve - 6);

      const tagNodes = Array.from(
        measureEl.querySelectorAll<HTMLElement>('.bklog-tag-input__measure-tag:not(.bklog-tag-input__measure-more)'),
      );
      const moreNode = measureEl.querySelector<HTMLElement>('.bklog-tag-input__measure-more');
      const tagWidths = tagNodes.map(node => Math.ceil(node.getBoundingClientRect().width));
      const moreBadgeWidth = moreNode ? Math.ceil(moreNode.getBoundingClientRect().width) : 34;

      dynamicVisibleCount.value = computeCollapsedVisibleCount({
        tagWidths,
        availableWidth,
        gap: 4,
        moreBadgeWidth,
      });
    };

    const scrollActiveOptionIntoView = () => {
      nextTick(() => {
        const listEl = optionListRef.value;
        if (!listEl || activeOptionIndex.value < 0) return;
        const activeEl = listEl.children[activeOptionIndex.value] as HTMLElement | undefined;
        activeEl?.scrollIntoView?.({ block: 'nearest' });
      });
    };

    const selectOption = (option: NormalizedTagOption) => {
      const nextTags = resolveTagAddition({
        currentTags: currentTags.value,
        candidate: option.id,
        allowCreate: true,
        options: normalizedOptions.value,
        max: resolvedMax.value,
      });
      if (nextTags) {
        publish(nextTags);
        emit('select', option.raw);
      }
      setInputValue('', { trigger: 'enter' });
      activeOptionIndex.value = filteredOptions.value.length > 0 ? 0 : -1;

      if (props.allowNextFocus) {
        nextTick(() => {
          const inputEl = getControlElement()?.querySelector<HTMLInputElement>('input');
          inputEl?.focus();
          syncPopper();
        });
      } else {
        isFocused.value = false;
      }
    };

    const handleNativeKeydown = (event: KeyboardEvent) => {
      if (!dropdownVisible.value) return;

      const count = filteredOptions.value.length;
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        activeOptionIndex.value = count > 0 ? (activeOptionIndex.value + 1) % count : -1;
        scrollActiveOptionIntoView();
        return;
      }

      if (event.key === 'ArrowUp') {
        event.preventDefault();
        activeOptionIndex.value = count > 0 ? (activeOptionIndex.value <= 0 ? count - 1 : activeOptionIndex.value - 1) : -1;
        scrollActiveOptionIntoView();
        return;
      }

      if (event.key === 'Escape') {
        event.preventDefault();
        isFocused.value = false;
        getControlElement()?.querySelector<HTMLInputElement>('input')?.blur();
        return;
      }

      if (event.key === 'Enter') {
        const hasExplicitHighlight = activeOptionIndex.value >= 0 && activeOptionIndex.value < count;
        if (hasExplicitHighlight) {
          event.preventDefault();
          event.stopPropagation();
          selectOption(filteredOptions.value[activeOptionIndex.value]);
        } else if (!props.allowCreate && count > 0 && resolvedInputValue.value.trim()) {
          event.preventDefault();
          event.stopPropagation();
          selectOption(filteredOptions.value[0]);
        }
      }
    };

    const handleTagChange = (value: Array<string | number>, context?: TagInputChangeContext) => {
      const normalized = (value || []).map(item => String(item));
      if (context?.trigger === 'enter') {
        const candidate = String(context.item ?? '').trim();
        const nextTags = resolveTagAddition({
          currentTags: currentTags.value,
          candidate,
          allowCreate: props.allowCreate,
          options: normalizedOptions.value,
          max: resolvedMax.value,
        });
        if (nextTags) {
          publish(nextTags);
        }
        syncPopper();
        return;
      }

      const deduped = Array.from(new Set(normalized));
      publish(deduped);
      syncPopper();
    };

    const handleClearClick = (event?: MouseEvent) => {
      event?.stopPropagation();
      publish([]);
      setInputValue('', { trigger: 'clear', e: event });
      emit('removeAll', { e: event });
      emit('remove-all', { e: event });
      emit('clear', { e: event });
      syncPopper();
    };

    const handleFocus = (value?: Array<string | number>, context?: unknown) => {
      if (props.disabled || props.readonly) return;
      const controlEl = getControlElement();
      if (controlEl) {
        triggerWidth.value = controlEl.getBoundingClientRect().width;
      }
      if (isFocused.value) {
        syncPopper();
        return;
      }
      isFocused.value = true;
      document.addEventListener('mousedown', onDocumentMousedown, true);
      popupZIndex.value = overlayRegistry.nextZIndex();
      activeOptionIndex.value = -1;
      emit('focus', value ?? currentTags.value, context);
      syncPopper();
    };

    const handleBlur = (value?: Array<string | number>, context?: { inputValue?: string | number; e?: FocusEvent }) => {
      if (!isFocused.value) return;
      const rawInput = String(context?.inputValue ?? resolvedInputValue.value ?? '');
      let nextTags = (value ?? currentTags.value).map(item => String(item));

      if (props.allowAutoMatch && rawInput.trim()) {
        const added = resolveTagAddition({
          currentTags: nextTags,
          candidate: rawInput,
          allowCreate: props.allowCreate,
          options: normalizedOptions.value,
          max: resolvedMax.value,
        });
        if (added) {
          nextTags = added;
          publish(nextTags);
          setInputValue('', { trigger: 'blur' });
        }
      }

      isFocused.value = false;
      document.removeEventListener('mousedown', onDocumentMousedown, true);
      activeOptionIndex.value = -1;
      emit('blur', rawInput, nextTags);
      nextTick(recomputeVisibleCount);
    };

    const renderDefaultCollapsedItems: TagInputProps['collapsedItems'] = (_h, { collapsedSelectedItems, count }) => {
      const tooltipText = (collapsedSelectedItems || []).map(item => getTagDisplayText(String(item))).join(', ');
      return (
        <TTooltip
          content={tooltipText}
          placement='top'
          theme='default'
          zIndex={tooltipZIndex.value}
          overlayClassName='bklog-popover-stop bklog-tag-input__collapsed-tooltip'
        >
          <span
            class='bklog-tag-input__collapsed-wrap'
            onMouseenter={() => {
              tooltipZIndex.value = overlayRegistry.nextZIndex();
            }}
          >
            <TTag
              size={props.size}
              closable={false}
              title=''
              class='bklog-tag-input__collapsed-tag'
            >
              +{count}
            </TTag>
          </span>
        </TTooltip>
      );
    };

    const onDocumentMousedown = (e: MouseEvent) => {
      if (!isFocused.value) return;
      const target = e.target as Node | null;
      const controlEl = getControlElement();
      if (target && (controlEl?.contains(target) || optionListRef.value?.contains(target))) {
        return;
      }
      handleBlur(currentTags.value, { inputValue: resolvedInputValue.value });
      controlEl?.querySelector<HTMLInputElement>('input')?.blur();
    };

    const onControlFocusIn = (e: FocusEvent) => {
      handleFocus(currentTags.value, { e });
    };

    const onControlFocusOut = (e: FocusEvent) => {
      const controlEl = getControlElement();
      const relatedTarget = e.relatedTarget as Node | null;
      if (relatedTarget && (controlEl?.contains(relatedTarget) || optionListRef.value?.contains(relatedTarget))) {
        return;
      }
      handleBlur(currentTags.value, { inputValue: resolvedInputValue.value, e });
    };

    const unbindFocusListeners = () => {
      document.removeEventListener('mousedown', onDocumentMousedown, true);
      if (boundFocusEl) {
        boundFocusEl.removeEventListener('focusin', onControlFocusIn);
        boundFocusEl.removeEventListener('focusout', onControlFocusOut);
        boundFocusEl = null;
      }
    };

    const bindFocusListeners = () => {
      const controlEl = getControlElement();
      if (controlEl === boundFocusEl) return;
      unbindFocusListeners();
      if (controlEl) {
        controlEl.addEventListener('focusin', onControlFocusIn);
        controlEl.addEventListener('focusout', onControlFocusOut);
        boundFocusEl = controlEl;
      }
    };

    const setupObservers = () => {
      bindFocusListeners();
      hostObserver?.disconnect();
      controlObserver?.disconnect();
      if (typeof ResizeObserver === 'undefined') return;

      const observeTarget = hostRef.value ?? getControlElement();
      if (observeTarget) {
        hostObserver = new ResizeObserver(() => {
          const controlEl = getControlElement();
          if (controlEl) {
            triggerWidth.value = controlEl.getBoundingClientRect().width;
          }
          recomputeVisibleCount();
          if (dropdownVisible.value) {
            popupRef.value?.updatePopper?.();
          }
        });
        hostObserver.observe(observeTarget);
      }

      const controlEl = getControlElement();
      if (controlEl && controlEl !== observeTarget) {
        controlObserver = new ResizeObserver(() => {
          triggerWidth.value = controlEl.getBoundingClientRect().width;
          if (dropdownVisible.value) {
            popupRef.value?.updatePopper?.();
          }
        });
        controlObserver.observe(controlEl);
      }
    };

    onMounted(() => {
      setupObservers();
      nextTick(recomputeVisibleCount);
    });

    onBeforeUnmount(() => {
      unbindFocusListeners();
      hostObserver?.disconnect();
      controlObserver?.disconnect();
    });

    watch(
      () => [currentTags.value.join('\0'), isFocused.value, props.collapseTags, props.hasDeleteIcon],
      () => {
        nextTick(() => {
          recomputeVisibleCount();
          if (dropdownVisible.value) syncPopper();
        });
      },
    );

    watch(
      () => filteredOptions.value.length,
      len => {
        if (len === 0) {
          activeOptionIndex.value = -1;
        } else if (activeOptionIndex.value >= len) {
          activeOptionIndex.value = len - 1;
        }
        if (dropdownVisible.value) syncPopper();
      },
    );

    expose({
      clearInput: () => {
        setInputValue('');
      },
      focus: () => {
        getControlElement()?.querySelector<HTMLInputElement>('input')?.focus();
      },
      blur: () => {
        getControlElement()?.querySelector<HTMLInputElement>('input')?.blur();
      },
    });

    return () => {
      const {
        'ext-cls': extClsKebab,
        'allow-create': _allowCreateKebab,
        'allow-next-focus': _allowNextFocusKebab,
        'allow-auto-match': _allowAutoMatchKebab,
        'free-paste': _freePasteKebab,
        'content-width': _contentWidthKebab,
        'content-max-height': _contentMaxHeightKebab,
        'save-key': _saveKeyKebab,
        'display-key': _displayKeyKebab,
        'search-key': _searchKeyKebab,
        'tooltip-key': _tooltipKeyKebab,
        'is-async-list': _isAsyncListKebab,
        isAsyncList: _isAsyncList,
        'tag-tpl': _tagTplKebab,
        'has-delete-icon': _hasDeleteIconKebab,
        'max-data': _maxDataKebab,
        'paste-fn': _pasteFnKebab,
        'collapse-tags': _collapseTagsKebab,
        'popover-class-name': _popoverClassNameKebab,
        onInputchange: _onInputchange,
        onRemoveAll: _onRemoveAll,
        'on-inputchange': _onInputchangeKebab,
        'on-remove-all': _onRemoveAllKebab,
        class: attrClass,
        style: attrStyle,
        inputProps: attrInputProps,
        onPaste: attrOnPaste,
        ...restAttrs
      } = attrs as Record<string, unknown>;

      const effectiveMinCollapsedNum = props.collapseTags
        ? isFocused.value
          ? 0
          : dynamicVisibleCount.value
        : props.minCollapsedNum;

      const effectiveCollapsedItems =
        props.collapsedItems ??
        (props.collapseTags || effectiveMinCollapsedNum > 0 ? renderDefaultCollapsedItems : undefined);

      const resolvedTagProps = disableTagClose.value
        ? { ...(props.tagProps ?? {}), closable: false }
        : props.tagProps;

      const usePersistentClearIcon =
        props.collapseTags &&
        props.clearable &&
        !props.disabled &&
        !props.readonly &&
        (currentTags.value.length > 0 || resolvedInputValue.value.length > 0);

      const handlePaste =
        typeof attrOnPaste === 'function'
          ? (attrOnPaste as TagInputProps['onPaste'])
          : props.pasteFn || props.separator
            ? ({ e, pasteValue }: { e: ClipboardEvent; pasteValue: string }) => {
                e?.preventDefault?.();
                const merged = parsePastedTags({
                  currentTags: currentTags.value,
                  pasteValue,
                  pasteFn: props.pasteFn,
                  separator: props.separator,
                  max: resolvedMax.value,
                });
                if (merged) publish(merged);
              }
            : undefined;

      const mergedInputProps = {
        ...((attrInputProps as Record<string, unknown>) || {}),
        onFocus: (_value: string, context?: unknown) => {
          const origFocus = (attrInputProps as Record<string, any>)?.onFocus;
          origFocus?.(_value, context);
          handleFocus(currentTags.value, context);
        },
        onBlur: (inputVal: string, context?: { e?: FocusEvent }) => {
          const origBlur = (attrInputProps as Record<string, any>)?.onBlur;
          origBlur?.(inputVal, context);
          handleBlur(currentTags.value, { inputValue: inputVal, e: context?.e });
        },
        onKeydown: (_value: string, context?: { e?: KeyboardEvent }) => {
          const origKeydown = (attrInputProps as Record<string, any>)?.onKeydown;
          origKeydown?.(_value, context);
          if (context?.e) handleNativeKeydown(context.e);
        },
      };

      const renderTagNode = props.tagTpl
        ? (_h: unknown, { value }: { value: string | number }) => {
            const strVal = String(value);
            const option = optionMap.value.get(strVal);
            return props.tagTpl?.(option?.raw ?? { [props.saveKey]: strVal, [props.displayKey]: strVal });
          }
        : hasOptionsList.value
          ? (_h: unknown, { value }: { value: string | number }) => getTagDisplayText(String(value))
          : undefined;

      const tagInputNode = (
        <TTagInput
          ref={tagInputRef}
          {...restAttrs}
          class={normalizeClass([
            'bklog-tag-input__control',
            props.collapseTags ? undefined : [props.extCls, extClsKebab, attrClass],
          ])}
          style={props.collapseTags ? undefined : (attrStyle as any)}
          value={currentTags.value}
          inputValue={resolvedInputValue.value}
          placeholder={props.placeholder}
          disabled={props.disabled}
          readonly={props.readonly}
          clearable={usePersistentClearIcon ? false : props.clearable}
          size={props.size}
          status={props.status}
          max={resolvedMax.value}
          excessTagsDisplayType={props.collapseTags ? 'break-line' : props.excessTagsDisplayType}
          minCollapsedNum={effectiveMinCollapsedNum}
          collapsedItems={effectiveCollapsedItems}
          tag={renderTagNode as any}
          tagProps={resolvedTagProps}
          inputProps={mergedInputProps}
          suffixIcon={
            usePersistentClearIcon
              ? () => (
                  <span
                    role='button'
                    tabindex={-1}
                    class='bklog-tag-input__clear-icon bklog-popover-stop'
                    onMousedown={(e: MouseEvent) => {
                      e.preventDefault();
                      e.stopPropagation();
                    }}
                    onClick={handleClearClick}
                  >
                    <CloseCircleFilledIcon />
                  </span>
                )
              : undefined
          }
          onPaste={handlePaste}
          onChange={handleTagChange}
          onEnter={(value, context) => emit('enter', value, context)}
          onBlur={handleBlur}
          onFocus={handleFocus}
          onClick={context => handleFocus(currentTags.value, context)}
          onRemove={context => emit('remove', context)}
          onClear={context => {
            emit('removeAll', context);
            emit('remove-all', context);
            emit('clear', context);
          }}
          onInputChange={(value, context) => {
            setInputValue(String(value ?? ''), context);
            if (isFocused.value && hasOptionsList.value) {
              activeOptionIndex.value = -1;
              syncPopper();
            }
          }}
        >
          {slots}
        </TTagInput>
      );

      const resolvedPopupWidth = props.contentWidth
        ? `${props.contentWidth}px`
        : triggerWidth.value > 0
          ? `${Math.max(triggerWidth.value, 160)}px`
          : undefined;

      const interactiveNode = (
        <TPopup
          ref={popupRef}
          visible={dropdownVisible.value}
          disabled={!hasOptionsList.value}
          attach='body'
          placement='bottom-left'
          zIndex={popupZIndex.value}
          overlayClassName={normalizeClass(['bklog-tag-input__popup', 'bklog-popover-stop', props.popoverClassName])}
          overlayInnerStyle={{
            padding: '4px 0',
            width: resolvedPopupWidth,
            maxHeight: `${props.contentMaxHeight}px`,
            overflowY: 'auto',
          }}
          content={() => (
            <ul
              ref={optionListRef}
              class='bklog-tag-input__option-list bklog-popover-stop'
              role='listbox'
            >
              {filteredOptions.value.map((option, idx) => (
                <li
                  key={option.id}
                  role='option'
                  aria-selected={activeOptionIndex.value === idx}
                  class={[
                    'bklog-tag-input__option-item',
                    'bklog-popover-stop',
                    {
                      'is-active': activeOptionIndex.value === idx,
                      'has-custom-tpl': Boolean(props.tpl),
                    },
                  ]}
                  onMouseenter={() => {
                    activeOptionIndex.value = idx;
                  }}
                  onMousedown={(event: MouseEvent) => event.preventDefault()}
                  onClick={() => selectOption(option)}
                >
                  {props.tpl ? (
                    props.tpl(option.raw, h)
                  ) : (
                    <span class='bklog-tag-input__option-text'>{option.name}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        >
          {tagInputNode}
        </TPopup>
      );

      if (!props.collapseTags) {
        return interactiveNode;
      }

      return (
        <div
          ref={hostRef}
          class={normalizeClass([
            'bklog-tag-input-host',
            'bklog-tag-input--collapsible',
            { 'is-focused': isFocused.value },
            props.extCls,
            extClsKebab,
            attrClass,
          ])}
          style={attrStyle as any}
        >
          {interactiveNode}
          {!isFocused.value && currentTags.value.length > 1 && (
            <div
              ref={measureRef}
              class='bklog-tag-input__measure'
              aria-hidden='true'
            >
              {currentTags.value.map((tagVal, idx) => (
                <span
                  key={`${tagVal}-${idx}`}
                  class={['bklog-tag-input__measure-tag', { 'has-close': !disableTagClose.value }]}
                >
                  {getTagDisplayText(tagVal)}
                </span>
              ))}
              <span class='bklog-tag-input__measure-tag bklog-tag-input__measure-more'>
                +{currentTags.value.length}
              </span>
            </div>
          )}
        </div>
      );
    };
  },
});
