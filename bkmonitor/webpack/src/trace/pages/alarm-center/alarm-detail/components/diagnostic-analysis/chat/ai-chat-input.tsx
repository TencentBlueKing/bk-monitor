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

import { storeToRefs } from 'pinia';

import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

import type { IChatContextItem } from '@/store/modules/alarm-center-detail';

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
    const alarmCenterDetailStore = useAlarmCenterDetailStore();
    const { chatContexts } = storeToRefs(alarmCenterDetailStore);
    const value = shallowRef('');
    const isFocus = shallowRef(false);

    const canSend = computed(() => Boolean(value.value.trim() || chatContexts.value.length) && !props.pending);

    /** 按划词区域分组，组内保持添加顺序 */
    const contextGroups = computed(() => {
      const groups: { category: string; items: IChatContextItem[] }[] = [];
      for (const item of chatContexts.value) {
        const category = item.category || t('其他');
        const group = groups.find(target => target.category === category);
        if (group) group.items.push(item);
        else groups.push({ category, items: [item] });
      }
      return groups;
    });

    /** 左侧划词添加的引用作为提问的前置上下文，按区域分组一起发出去后清空 */
    const handleSend = () => {
      if (!canSend.value) return;
      const quotes = contextGroups.value.map(group =>
        [
          `【${group.category}】`,
          ...group.items.map(item => {
            // 对象名与分类同名时不重复标注，例如告警问题正文
            const label = item.label && item.label !== group.category ? `${item.label}：` : '';
            return `- ${label}${item.text}`;
          }),
        ].join('\n')
      );
      // 各分类之间空一行，问题单独成段
      const content = [...quotes, value.value.trim()].filter(Boolean).join('\n\n');
      emit('send', content);
      value.value = '';
      alarmCenterDetailStore.clearChatContexts();
    };

    const handleRemoveContext = (id: string) => {
      alarmCenterDetailStore.removeChatContext(id);
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
      contextGroups,
      handleSend,
      handleKeydown,
      handleRemoveContext,
    };
  },
  render() {
    return (
      <div class={['ai-chat-input', { 'is-focus': this.isFocus }]}>
        {this.contextGroups.length ? (
          <div class='ai-chat-input-contexts'>
            {this.contextGroups.map(group => (
              <div
                key={group.category}
                class='ai-chat-input-context-group'
              >
                <div class='context-group-title'>{group.category}</div>
                {group.items.map(item => (
                  <div
                    key={item.id}
                    class='ai-chat-input-context'
                  >
                    {item.label && item.label !== group.category ? (
                      <span class='context-label'>{item.label}</span>
                    ) : undefined}
                    <span class='context-text'>{item.text}</span>
                    <i
                      class='icon-monitor icon-mc-close context-remove'
                      onClick={() => this.handleRemoveContext(item.id)}
                    />
                  </div>
                ))}
              </div>
            ))}
          </div>
        ) : undefined}
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
