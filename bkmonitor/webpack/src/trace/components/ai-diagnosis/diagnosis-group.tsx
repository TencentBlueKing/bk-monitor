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
import { type PropType, defineComponent, useId } from 'vue';

import { useI18n } from 'vue-i18n';

import DiagnosisInteractiveValue from './diagnosis-interactive-value';

import type {
  DiagnosisAddToChatPayload,
  DiagnosisDetailAction,
  DiagnosisGroupViewModel,
  DiagnosisPromptAction,
} from './view-types';

import './ai-diagnosis.scss';

export default defineComponent({
  name: 'DiagnosisGroup',
  props: {
    expanded: {
      type: Boolean,
      default: true,
    },
    group: {
      type: Object as PropType<DiagnosisGroupViewModel>,
      required: true,
    },
  },
  emits: {
    'add-to-chat': (_payload: DiagnosisAddToChatPayload) => true,
    detail: (_action: DiagnosisDetailAction) => true,
    prompt: (_action: DiagnosisPromptAction) => true,
    toggle: (_expanded: boolean) => true,
    'update:expanded': (_expanded: boolean) => true,
  },
  setup(_, { emit }) {
    const { t } = useI18n();
    const contentId = `ai-diagnosis-group-${useId().replace(/[^\w-]/g, '-')}`;
    const handleToggle = (expanded: boolean) => {
      emit('update:expanded', expanded);
      emit('toggle', expanded);
    };
    return {
      t,
      contentId,
      handleToggle,
      handleAddToChat: (payload: DiagnosisAddToChatPayload) => emit('add-to-chat', payload),
      handleDetail: (action: DiagnosisDetailAction) => emit('detail', action),
      emitPrompt: (action: DiagnosisPromptAction) => emit('prompt', action),
    };
  },
  render() {
    return (
      <section class={['ai-diagnosis-event__group', { 'is-expanded': this.expanded }]}>
        <div
          class='ai-diagnosis-event__group-header'
          onClick={() => this.handleToggle(!this.expanded)}
        >
          <button
            class='ai-diagnosis-event__group-toggle'
            aria-controls={this.contentId}
            aria-expanded={this.expanded}
            type='button'
            onClick={(event: MouseEvent) => {
              event.stopPropagation();
              this.handleToggle(!this.expanded);
            }}
          >
            <i
              class='icon-monitor icon-arrow-solid-right ai-diagnosis-event__group-arrow'
              aria-hidden='true'
            />
            {this.group.iconSrc ? (
              <img
                class='ai-diagnosis-event__source-icon'
                alt=''
                src={this.group.iconSrc}
              />
            ) : (
              <i
                class='icon-monitor icon-event ai-diagnosis-event__source-icon'
                aria-hidden='true'
              />
            )}
            <strong>{this.group.title}</strong>
            {!this.group.totalContent && this.group.totalText && (
              <span>
                {this.group.totalText
                  .split(/(Top\d+|\d+)/)
                  .map((part, index) => (/^(?:Top)?\d+$/.test(part) ? <strong key={index}>{part}</strong> : part))}
              </span>
            )}
          </button>
          {this.group.totalContent && (
            <DiagnosisInteractiveValue
              content={this.group.totalContent}
              onAdd-to-chat={this.handleAddToChat}
              onDetail={this.handleDetail}
            />
          )}
          {this.group.promptAction && (
            <button
              class='ai-diagnosis-renderer__action'
              v-tippy={{
                content: this.t('查看详情'),
                placement: 'top',
                delay: 200,
                appendTo: () => document.body,
              }}
              aria-label={this.t('查看详情')}
              type='button'
              onClick={(event: MouseEvent) => {
                event.stopPropagation();
                this.emitPrompt(this.group.promptAction);
              }}
            >
              <i
                class='icon-monitor icon-mc-duanxin'
                aria-hidden='true'
              />
            </button>
          )}
        </div>
        {this.expanded && (
          <div
            id={this.contentId}
            class='ai-diagnosis-event__group-content'
          >
            <div class='ai-diagnosis-event__rail'>{this.$slots.default?.({ group: this.group })}</div>
          </div>
        )}
      </section>
    );
  },
});
