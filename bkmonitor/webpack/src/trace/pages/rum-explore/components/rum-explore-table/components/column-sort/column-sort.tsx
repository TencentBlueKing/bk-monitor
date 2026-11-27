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
import { type PropType, computed, defineComponent, onBeforeUnmount, shallowRef, useTemplateRef } from 'vue';

import tippy, { type Instance, type SingleTarget } from 'tippy.js';
import { useI18n } from 'vue-i18n';

import './column-sort.scss';

/** 复合列可选择的排序分类。 */
export interface RumSortOption {
  /** 分类展示名 */
  label: string;
  /** 分类对应的字段名 */
  value: string;
}

/** 表头排序状态，空串表示未排序。 */
export type RumSortOrder = '' | 'asc' | 'desc';

/** 设计稿「表格排序」组件的双三角路径，容器 12px、图形 7.125 × 11.25。 */
const SORT_TRIANGLE_PATH: Record<Exclude<RumSortOrder, ''>, string> = {
  asc: 'M3.5625 0L0 4.60227H7.125L3.5625 0Z',
  desc: 'M0 6.64774L3.56238 11.25L7.125 6.64774Z',
};

export default defineComponent({
  name: 'RumColumnSort',
  props: {
    /** 当前排序状态，由调用方受控。 */
    sort: { type: String as PropType<RumSortOrder>, default: '' },
    /** 当前生效排序的分类字段，复合列弹层中作为初始选中项。 */
    sortField: { type: String, default: '' },
    /** 可排序分类：非空时点击打开分类排序弹层，为空时保持三态直切。 */
    sortOptions: { type: Array as PropType<RumSortOption[]>, default: () => [] },
  },
  emits: {
    /** 排序变更：order 为方向，field 为复合列选中的分类字段（单字段列为空）。 */
    sortChange: (order: RumSortOrder, _field?: string) => ['', 'asc', 'desc'].includes(order),
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const triggerRef = useTemplateRef<HTMLButtonElement>('triggerRef');
    const menuRef = useTemplateRef<HTMLDivElement>('menuRef');
    const popoverRef = shallowRef<Instance | null>(null);
    /** 弹层内当前选中的分类字段，未确认前不触发排序。 */
    const activeField = shallowRef('');
    /** 复合列才有分类可选，单字段列保持三态直切。 */
    const isComposite = computed(() => props.sortOptions.length > 0);
    /** 与 TDesign 表头一致的三态循环，第三次点击取消排序。 */
    const nextSort = computed<RumSortOrder>(() => {
      if (props.sort === 'asc') return 'desc';
      if (props.sort === 'desc') return '';
      return 'asc';
    });
    /** 弹层内当前分类实际生效的方向，用于高亮升序/降序按钮。 */
    const activeOrder = computed<RumSortOrder>(() => (props.sortField === activeField.value ? props.sort : ''));

    /** 点击弹层和触发器以外的区域时收起弹层。 */
    let outsideMousedown: ((event: MouseEvent) => void) | null = null;

    const destroyPopover = () => {
      if (outsideMousedown) {
        document.removeEventListener('mousedown', outsideMousedown, true);
        outsideMousedown = null;
      }
      const instance = popoverRef.value;
      popoverRef.value = null;
      instance?.destroy();
    };

    const openPopover = () => {
      const trigger = triggerRef.value;
      const contentEl = menuRef.value;
      if (!trigger || !contentEl) return;
      activeField.value = props.sortField || props.sortOptions[0]?.value || '';
      const instance = tippy(trigger as SingleTarget, {
        content: contentEl,
        trigger: 'manual',
        interactive: true,
        appendTo: () => document.body,
        placement: 'bottom-start',
        theme: 'light padding-0 rum-column-sort-popover',
        arrow: false,
        offset: [0, 4],
        animation: false,
        onHidden: hidden => {
          if (popoverRef.value === hidden) destroyPopover();
        },
      });
      popoverRef.value = instance;
      instance.show();
      outsideMousedown = event => {
        const target = event.target as Node;
        if (trigger.contains(target) || instance.popper.contains(target)) return;
        destroyPopover();
      };
      document.addEventListener('mousedown', outsideMousedown, true);
    };

    /** 阻止冒泡，避免内嵌到可排序表头时同时触发表头自身的点击排序。 */
    const handleClick = (event: MouseEvent) => {
      event.stopPropagation();
      if (!isComposite.value) {
        emit('sortChange', nextSort.value);
        return;
      }
      if (popoverRef.value) destroyPopover();
      else openPopover();
    };

    /** 选定方向后立即生效并关闭弹层，重复点击当前方向则取消排序。 */
    const applySort = (order: Exclude<RumSortOrder, ''>) => {
      emit('sortChange', activeOrder.value === order ? '' : order, activeField.value);
      destroyPopover();
    };

    onBeforeUnmount(destroyPopover);

    return { t, activeField, activeOrder, isComposite, triggerRef, menuRef, handleClick, applySort };
  },
  render() {
    return (
      <>
        <button
          ref='triggerRef'
          class='rum-column-sort'
          aria-label={this.t('排序')}
          type='button'
          onClick={this.handleClick}
        >
          <svg
            width='14'
            height='14'
            aria-hidden='true'
            fill='none'
            viewBox='0 0 12 12'
          >
            <g transform='translate(2.625 0.375)'>
              <path
                class={['sort-triangle', { 'is-active': this.sort === 'asc' }]}
                clip-rule='evenodd'
                d={SORT_TRIANGLE_PATH.asc}
                fill-rule='evenodd'
              />
              <path
                class={['sort-triangle', { 'is-active': this.sort === 'desc' }]}
                clip-rule='evenodd'
                d={SORT_TRIANGLE_PATH.desc}
                fill-rule='evenodd'
              />
            </g>
          </svg>
        </button>
        {this.isComposite && (
          <div style='display: none'>
            <div
              ref='menuRef'
              class='rum-column-sort-menu'
            >
              {this.sortOptions.map(option => (
                <label
                  key={option.value}
                  class='sort-menu-item'
                >
                  <input
                    class='sort-menu-radio'
                    checked={this.activeField === option.value}
                    type='radio'
                    onChange={() => (this.activeField = option.value)}
                  />
                  <span class='sort-menu-label'>{option.label}</span>
                </label>
              ))}
              <div class='sort-menu-footer'>
                <button
                  class={['sort-menu-button', { 'is-active': this.activeOrder === 'asc' }]}
                  type='button'
                  onClick={() => this.applySort('asc')}
                >
                  {this.t('升序')}
                </button>
                <button
                  class={['sort-menu-button', { 'is-active': this.activeOrder === 'desc' }]}
                  type='button'
                  onClick={() => this.applySort('desc')}
                >
                  {this.t('降序')}
                </button>
              </div>
            </div>
          </div>
        )}
      </>
    );
  },
});
