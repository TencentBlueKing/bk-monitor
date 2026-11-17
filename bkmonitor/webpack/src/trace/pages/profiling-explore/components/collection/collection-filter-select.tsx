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
import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { Input, Loading, Select, Tag } from 'bkui-vue';
import { AngleDown, Close } from 'bkui-vue/lib/icon';
import { useI18n } from 'vue-i18n';

import './collection-filter-select.scss';

interface SelectInstance {
  isPopoverShow?: { value: boolean };
  // 与组件库 trigger 的点击行为一致（刷新候选项 + 聚焦面板搜索框 + 开关面板）
  handleTogglePopover?: () => void;
  hidePopover?: () => void;
  showPopover?: () => void;
}

type SelectValue = Array<number | string> | number | string;

interface TriggerOption {
  label: string;
  value: string;
}

/**
 * 触发器用插槽自渲染，外观与交互沿用 bk-select 默认触发器；
 * 区别是触发器内的输入只用于创建候选外的自定义值，不再触发远程搜索，
 * 远程搜索只由下拉面板内的搜索框触发（inputSearch 固定为 false）
 */
export default defineComponent({
  name: 'CollectionFilterSelect',
  props: {
    modelValue: {
      type: [Array, Number, String] as PropType<SelectValue>,
      default: '',
    },
    multiple: Boolean,
    // tag：已选值以标签展示；default：已选值以逗号拼接展示
    multipleMode: {
      type: String as PropType<'default' | 'tag'>,
      default: 'default',
    },
    // 未指定时保持 undefined：触发器占位由 triggerPlaceholder 兜底，搜索框交给 bk-select 兜底
    placeholder: {
      type: String,
      default: undefined,
    },
    searchPlaceholder: {
      type: String,
      default: undefined,
    },
    loading: Boolean,
    scrollLoading: Boolean,
    remoteMethod: {
      type: Function as PropType<(keyword: string) => Promise<void> | void>,
      default: undefined,
    },
    // 已选值的展示文案：选项未渲染时组件库会把 label 退化成原始 value，这里按 value 兜底
    optionLabels: {
      type: Object as PropType<Record<string, string>>,
      default: () => ({}),
    },
  },
  emits: {
    change: (_value: SelectValue) => true,
    'scroll-end': () => true,
  },
  setup(props, { emit, slots }) {
    const { t } = useI18n();
    // 触发器输入框内容：回车才创建自定义值，不作为下拉的搜索关键字
    const customValue = shallowRef('');
    const hovered = shallowRef(false);
    const selectRef = shallowRef<SelectInstance>();
    // 触发器由本组件渲染，不经过 bk-select 的占位兜底，空态文案在这里补齐
    const triggerPlaceholder = computed(() => props.placeholder || t('请选择'));
    const values = computed<Array<number | string>>(() => {
      if (Array.isArray(props.modelValue)) return props.modelValue;
      return props.modelValue === '' ? [] : [props.modelValue];
    });

    function setSelectRef(instance: unknown) {
      selectRef.value = (instance || undefined) as SelectInstance;
    }

    // 已选值展示文案：外部给出的可读文案优先，避免回填时直接显示原始 value
    function labelOf(item: TriggerOption) {
      return props.optionLabels?.[String(item.value)] || item.label;
    }

    function emitChange(next: SelectValue) {
      customValue.value = '';
      emit('change', next);
    }

    // 回车创建候选外的值，交互与 allowCreate 一致
    function commitCustomValue() {
      const value = customValue.value.trim();
      if (!value) return;
      if (values.value.some(item => String(item) === value)) {
        customValue.value = '';
        return;
      }
      emitChange(props.multiple ? [...values.value, value] : value);
      // 单选创建后立即收起面板，多选保持展开便于连续添加
      if (!props.multiple) selectRef.value?.hidePopover?.();
    }

    function removeValue(value: string) {
      const next = values.value.filter(item => String(item) !== String(value));
      emitChange(props.multiple ? next : '');
    }

    function clearValue(event: Event) {
      event.stopPropagation();
      emitChange(props.multiple ? [] : '');
      selectRef.value?.hidePopover?.();
    }

    function handleToggle(visible: boolean) {
      // 面板收起时丢弃未提交的输入，避免触发器残留自定义文本
      if (!visible) customValue.value = '';
    }

    // 触发器点击自行开关面板：不依赖外层 .bk-select-trigger 的事件冒泡，
    // 避免触发器内部部分区域（输入框、图标）点击后无响应
    function handleTriggerClick(event: MouseEvent) {
      event.stopPropagation();
      const instance = selectRef.value;
      if (!instance) return;
      if (instance.handleTogglePopover) {
        instance.handleTogglePopover();
        return;
      }
      if (instance.isPopoverShow?.value) instance.hidePopover?.();
      else instance.showPopover?.();
    }

    function renderSuffixIcon() {
      if (props.loading) {
        // 复用箭头的定位容器，保证加载态与箭头位置一致
        return (
          <span class='angle-down'>
            <Loading
              mode='spin'
              size='mini'
              theme='primary'
              loading
            />
          </span>
        );
      }
      if (hovered.value && values.value.length) {
        return (
          <Close
            class='clear-icon'
            onClick={clearValue}
          />
        );
      }
      return <AngleDown class='angle-down' />;
    }

    function renderTrigger({ selected }: { selected: TriggerOption[] }) {
      const toggles = {
        onMouseenter: () => (hovered.value = true),
        onMouseleave: () => (hovered.value = false),
      };
      if (props.multipleMode === 'tag') {
        return (
          <div
            class='bk-select-tag bk-select-tag--default'
            onClick={handleTriggerClick}
            {...toggles}
          >
            <div class='bk-select-tag-wrapper'>
              {selected.map(item => (
                <Tag
                  key={item.value}
                  closable
                  onClose={() => removeValue(item.value)}
                >
                  {labelOf(item)}
                </Tag>
              ))}
              <input
                class='bk-select-tag-input'
                placeholder={selected.length ? '' : triggerPlaceholder.value}
                value={customValue.value}
                onInput={event => (customValue.value = (event.target as HTMLInputElement).value)}
                onKeydown={event => {
                  if (event.key === 'Enter') commitCustomValue();
                }}
              />
            </div>
            {renderSuffixIcon()}
          </div>
        );
      }
      return (
        <div
          class='collection-filter-trigger'
          onClick={handleTriggerClick}
          {...toggles}
        >
          <span class='collection-filter-selected'>{selected.map(labelOf).join(',')}</span>
          <Input
            v-slots={{ suffix: renderSuffixIcon }}
            modelValue={customValue.value}
            placeholder={selected.length ? '' : triggerPlaceholder.value}
            stopPropagation={false}
            onEnter={commitCustomValue}
            onUpdate:modelValue={value => (customValue.value = String(value))}
          />
        </div>
      );
    }

    return {
      customValue,
      hovered,
      setSelectRef,
      emitChange,
      clearValue,
      commitCustomValue,
      removeValue,
      handleToggle,
      handleTriggerClick,
      renderSuffixIcon,
      renderTrigger,
      defaultSlot: slots.default,
    };
  },
  render() {
    return (
      <Select
        ref={this.setSelectRef}
        class='profiling-collection-filter-bk-select'
        v-slots={{
          default: () => this.defaultSlot?.(),
          trigger: this.renderTrigger,
        }}
        inputSearch={false}
        loading={this.loading}
        modelValue={this.modelValue}
        multiple={this.multiple}
        multipleMode={this.multipleMode}
        placeholder={this.placeholder}
        remoteMethod={this.remoteMethod}
        scrollLoading={this.scrollLoading}
        searchPlaceholder={this.searchPlaceholder}
        customContent
        filterable
        onChange={this.emitChange}
        onScroll-end={() => this.$emit('scroll-end')}
        onToggle={this.handleToggle}
      />
    );
  },
});
