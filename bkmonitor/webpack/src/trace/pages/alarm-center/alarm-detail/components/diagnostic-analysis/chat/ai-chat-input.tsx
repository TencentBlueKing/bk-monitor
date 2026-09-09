/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { computed, defineComponent, shallowRef } from 'vue';
import { useI18n } from 'vue-i18n';

import './ai-chat-input.scss';

export default defineComponent({
  name: 'AiChatInput',
  props: {
    pending: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    send: (question: string) => typeof question === 'string',
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const value = shallowRef('');
    const isFocus = shallowRef(false);

    const canSend = computed(() => Boolean(value.value.trim()) && !props.pending);

    const handleSend = () => {
      if (!canSend.value) return;
      emit('send', value.value.trim());
      value.value = '';
    };

    /** Enter 发送，Shift + Enter 换行 */
    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
      event.preventDefault();
      handleSend();
    };

    return {
      t,
      value,
      isFocus,
      canSend,
      handleSend,
      handleKeydown,
    };
  },
  render() {
    return (
      <div class={['ai-chat-input', { 'is-focus': this.isFocus }]}>
        <textarea
          class='ai-chat-input-textarea'
          v-model={this.value}
          disabled={this.pending}
          placeholder={this.t('输入你想了解的问题，继续追问')}
          rows={2}
          onBlur={() => {
            this.isFocus = false;
          }}
          onFocus={() => {
            this.isFocus = true;
          }}
          onKeydown={this.handleKeydown}
        />
        <div class='ai-chat-input-toolbar'>
          <span class='ai-chat-input-tips'>{this.t('Enter 发送，Shift + Enter 换行')}</span>
          <button
            class={['ai-chat-input-send', { 'is-active': this.canSend }]}
            disabled={!this.canSend}
            type='button'
            onClick={this.handleSend}
          >
            <svg
              height='16'
              viewBox='0 0 16 16'
              width='16'
            >
              <path
                d='M14.5 8 2 2.5l2 5.5-2 5.5z'
                fill='none'
                stroke='currentColor'
                stroke-linejoin='round'
                stroke-width='1.2'
              />
              <path
                d='M4 8h10.5'
                fill='none'
                stroke='currentColor'
                stroke-linecap='round'
                stroke-width='1.2'
              />
            </svg>
          </button>
        </div>
      </div>
    );
  },
});
