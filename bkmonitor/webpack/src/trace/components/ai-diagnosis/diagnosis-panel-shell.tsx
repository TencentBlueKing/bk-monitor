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
import { type PropType, defineComponent, getCurrentInstance, onBeforeUnmount, shallowRef, useId } from 'vue';

import { useI18n } from 'vue-i18n';

import './ai-diagnosis.scss';

export interface DiagnosisPanelAnchor {
  id: string;
  label: string;
}

export default defineComponent({
  name: 'DiagnosisPanelShell',
  props: {
    title: {
      type: String,
      default: '',
    },
    anchors: {
      type: Array as PropType<DiagnosisPanelAnchor[]>,
      default: () => [],
    },
    allExpanded: {
      type: Boolean,
      default: true,
    },
    anchorMenuId: {
      type: String,
      default: '',
    },
  },
  emits: {
    locate: (_anchor: string) => true,
    'update:allExpanded': (_expanded: boolean) => true,
    'toggle-all': (_expanded: boolean) => true,
    close: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const isAnchorMenuOpen = shallowRef(false);
    const anchorRef = shallowRef<HTMLElement | null>(null);
    const menuRef = shallowRef<HTMLElement | null>(null);
    const generatedAnchorMenuId = props.anchorMenuId
      ? ''
      : `ai-diagnosis-anchor-menu-${useId().replace(/[^\w-]/g, '-')}`;
    let detachOutside = () => {};
    const isElement = (value: unknown): value is HTMLElement =>
      typeof HTMLElement !== 'undefined' && value instanceof HTMLElement;
    const setAnchor = (element: unknown) => {
      anchorRef.value = isElement(element) ? element : null;
    };
    const setMenu = (element: unknown) => {
      menuRef.value = isElement(element) ? element : null;
    };
    const closeAnchorMenu = () => {
      isAnchorMenuOpen.value = false;
      detachOutside();
      detachOutside = () => {};
    };
    const bindOutside = () => {
      if (typeof document === 'undefined') return;
      const onPointerDown = (event: Event) => {
        const target = event.target;
        if (target instanceof Node && (anchorRef.value?.contains(target) || menuRef.value?.contains(target))) {
          return;
        }
        closeAnchorMenu();
      };
      document.addEventListener('pointerdown', onPointerDown, true);
      detachOutside = () => document.removeEventListener('pointerdown', onPointerDown, true);
    };
    if (getCurrentInstance()) onBeforeUnmount(() => detachOutside());
    const handleLocate = (anchor: string) => {
      closeAnchorMenu();
      emit('locate', anchor);
    };
    const handleToggleAll = (expanded: boolean) => {
      emit('update:allExpanded', expanded);
      emit('toggle-all', expanded);
    };
    return {
      t,
      isAnchorMenuOpen,
      resolvedAnchorMenuId: props.anchorMenuId || generatedAnchorMenuId,
      handleLocate,
      handleToggleAll,
      setAnchor,
      setMenu,
      handleClose: () => emit('close'),
      handleAnchorMenuToggle: () => {
        if (isAnchorMenuOpen.value) {
          closeAnchorMenu();
          return;
        }
        isAnchorMenuOpen.value = true;
        bindOutside();
      },
      handleKeydown: (event: KeyboardEvent) => {
        if (event.key === 'Escape') closeAnchorMenu();
      },
    };
  },
  render() {
    return (
      <aside
        class='ai-diagnosis-panel-shell'
        aria-label={this.title || this.t('AI 诊断')}
        onKeydown={this.handleKeydown}
      >
        <header class='ai-diagnosis-panel-shell__header'>
          <h2 class='ai-diagnosis-panel-shell__title'>{this.title || this.t('AI 诊断')}</h2>
          <div class='ai-diagnosis-panel-shell__tools'>
            <button
              ref={this.setAnchor}
              class='ai-diagnosis-panel-shell__tool'
              v-tippy={{ content: this.t('快捷定位'), placement: 'top', delay: 200, appendTo: () => document.body }}
              aria-controls={this.resolvedAnchorMenuId}
              aria-expanded={this.isAnchorMenuOpen}
              aria-label={this.t('快捷定位')}
              type='button'
              onClick={this.handleAnchorMenuToggle}
            >
              <i
                class='icon-monitor icon-content'
                aria-hidden='true'
              />
            </button>
            <button
              class='ai-diagnosis-panel-shell__tool'
              v-tippy={{
                content: this.allExpanded ? this.t('全部收起') : this.t('全部展开'),
                placement: 'top',
                delay: 200,
                appendTo: () => document.body,
              }}
              aria-label={this.allExpanded ? this.t('全部收起') : this.t('全部展开')}
              type='button'
              onClick={() => this.handleToggleAll(!this.allExpanded)}
            >
              <i
                class='icon-monitor icon-expand'
                aria-hidden='true'
              />
            </button>
            <button
              class='ai-diagnosis-panel-shell__tool'
              v-tippy={{ content: this.t('关闭'), placement: 'top', delay: 200, appendTo: () => document.body }}
              aria-label={this.t('关闭')}
              type='button'
              onClick={this.handleClose}
            >
              <i
                class='icon-monitor icon-close'
                aria-hidden='true'
              />
            </button>
          </div>
          {this.isAnchorMenuOpen && this.anchors.length > 0 && (
            <nav
              id={this.resolvedAnchorMenuId}
              ref={this.setMenu}
              class='ai-diagnosis-panel-shell__anchor-menu'
            >
              {this.anchors.map(anchor => (
                <button
                  key={anchor.id}
                  type='button'
                  onClick={() => this.handleLocate(anchor.id)}
                >
                  {anchor.label}
                </button>
              ))}
            </nav>
          )}
        </header>
        <div class='ai-diagnosis-panel-shell__body'>{this.$slots.default?.()}</div>
        {this.$slots.chat && <div class='ai-diagnosis-panel-shell__chat'>{this.$slots.chat()}</div>}
      </aside>
    );
  },
});
