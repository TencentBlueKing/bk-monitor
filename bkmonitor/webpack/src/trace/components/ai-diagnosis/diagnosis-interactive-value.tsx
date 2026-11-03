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
import { type PropType, defineComponent, getCurrentInstance, onBeforeUnmount, shallowRef, Teleport } from 'vue';

import { useI18n } from 'vue-i18n';

import type { DiagnosisAddToChatPayload, DiagnosisDetailAction, DiagnosisInteractiveContent } from './view-types';

import './ai-diagnosis.scss';

const isHtmlElement = (value: unknown): value is HTMLElement =>
  typeof HTMLElement !== 'undefined' && value instanceof HTMLElement;

const displayText = (value: DiagnosisInteractiveContent['value']) => {
  if (value === null) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value, null, 2);
};

export default defineComponent({
  name: 'DiagnosisInteractiveValue',
  props: {
    content: {
      type: Object as PropType<DiagnosisInteractiveContent>,
      required: true,
    },
  },
  emits: {
    detail: (_action: DiagnosisDetailAction) => true,
    'add-to-chat': (_payload: DiagnosisAddToChatPayload) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const menuVisible = shallowRef(false);
    const menuStyle = shallowRef<Record<string, string>>({});
    const rootRef = shallowRef<HTMLElement | null>(null);
    const menuRef = shallowRef<HTMLElement | null>(null);
    const setRoot = (element: unknown) => {
      rootRef.value = isHtmlElement(element) ? element : null;
    };
    const setMenu = (element: unknown) => {
      menuRef.value = isHtmlElement(element) ? element : null;
    };
    let detachOutsideListener = () => {};
    const detachOutside = () => {
      detachOutsideListener();
      detachOutsideListener = () => {};
    };
    const closeMenu = () => {
      menuVisible.value = false;
      detachOutside();
    };
    const bindOutside = () => {
      if (typeof document === 'undefined') return;
      const onPointerDown = (event: Event) => {
        const target = event.target;
        if (target instanceof Node && (rootRef.value?.contains(target) || menuRef.value?.contains(target))) {
          return;
        }
        closeMenu();
      };
      const onScroll = () => closeMenu();
      document.addEventListener('pointerdown', onPointerDown, true);
      window.addEventListener('scroll', onScroll, true);
      detachOutsideListener = () => {
        document.removeEventListener('pointerdown', onPointerDown, true);
        window.removeEventListener('scroll', onScroll, true);
      };
    };
    if (getCurrentInstance()) onBeforeUnmount(detachOutside);
    return {
      t,
      menuVisible,
      menuStyle,
      setRoot,
      setMenu,
      closeMenu,
      handleAddToChat: (event?: MouseEvent) => {
        event?.stopPropagation();
        emit('add-to-chat', {
          content: props.content,
          reference: props.content.chatReference,
        });
        closeMenu();
      },
      handleDetail: (event?: MouseEvent) => {
        event?.stopPropagation();
        if (props.content.detailAction) emit('detail', props.content.detailAction);
        closeMenu();
      },
      toggleMenu: (event?: MouseEvent) => {
        event?.stopPropagation();
        if (menuVisible.value) {
          closeMenu();
          return;
        }
        const trigger = event?.currentTarget;
        if (isHtmlElement(trigger) && typeof window !== 'undefined') {
          const rect = trigger.getBoundingClientRect();
          const menuHeight = 68;
          const openUpward = window.innerHeight - rect.bottom < menuHeight && rect.top > menuHeight;
          menuStyle.value = {
            position: 'fixed',
            top: openUpward ? `${rect.top - menuHeight}px` : `${rect.bottom + 4}px`,
            left: `${Math.max(8, Math.min(rect.left, window.innerWidth - 112))}px`,
            zIndex: '4000',
          };
        } else {
          menuStyle.value = {};
        }
        menuVisible.value = true;
        bindOutside();
      },
    };
  },
  render() {
    const canAddToChat = this.content.addToChat !== false;
    const canViewDetail = ['drawer', 'link'].includes(this.content.detailAction?.type || '');
    const hasAction = canAddToChat || canViewDetail;
    const renderContent = () => {
      if (this.content.format === 'markdown' && this.$slots.markdown) {
        return this.$slots.markdown({ content: this.content, value: this.content.value });
      }
      if (this.content.format === 'json') {
        if (this.$slots.json) return this.$slots.json({ content: this.content, value: this.content.value });
        return <pre class='ai-diagnosis-interactive-value__json'>{displayText(this.content.value)}</pre>;
      }
      return (
        this.$slots.default?.({ content: this.content, value: this.content.value }) || displayText(this.content.value)
      );
    };

    return (
      <span
        ref={this.setRoot}
        class={['ai-diagnosis-interactive-value', { 'has-action': hasAction, 'is-open': this.menuVisible }]}
      >
        {hasAction ? (
          <button
            class='ai-diagnosis-interactive-value__trigger'
            aria-expanded={this.menuVisible}
            type='button'
            onClick={this.toggleMenu}
          >
            {renderContent()}
          </button>
        ) : (
          <span class='ai-diagnosis-interactive-value__content'>{renderContent()}</span>
        )}
        {hasAction && this.menuVisible && (
          <Teleport to='body'>
            <span
              ref={this.setMenu}
              style={this.menuStyle}
              class='ai-diagnosis-interactive-value__menu'
            >
              {canViewDetail && (
                <button
                  class='ai-diagnosis-interactive-value__action'
                  type='button'
                  onClick={this.handleDetail}
                >
                  <i
                    class='icon-monitor icon-fenxiang icon-float'
                    aria-hidden='true'
                  />
                  {this.t('查看详情')}
                </button>
              )}
              {canAddToChat && (
                <button
                  class='ai-diagnosis-interactive-value__action'
                  type='button'
                  onClick={this.handleAddToChat}
                >
                  <i
                    class='icon-monitor icon-add-chat'
                    aria-hidden='true'
                  />
                  {this.t('添加到聊天')}
                </button>
              )}
            </span>
          </Teleport>
        )}
      </span>
    );
  },
});
