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
import { defineComponent, useId } from 'vue';

import './ai-diagnosis.scss';

export default defineComponent({
  name: 'DiagnosisModuleSection',
  props: {
    anchor: {
      type: String,
      required: true,
    },
    title: {
      type: String,
      required: true,
    },
    icon: {
      type: String,
      default: '',
    },
    iconSrc: {
      type: String,
      default: '',
    },
    count: {
      type: Number,
    },
    summary: {
      type: String,
      default: '',
    },
    expanded: {
      type: Boolean,
      default: true,
    },
    contentId: {
      type: String,
      default: '',
    },
  },
  emits: {
    'update:expanded': (_expanded: boolean) => true,
    toggle: (_expanded: boolean) => true,
  },
  setup(props, { emit }) {
    const generatedContentId = props.contentId ? '' : `ai-diagnosis-module-${useId().replace(/[^\w-]/g, '-')}`;
    const handleToggle = (expanded: boolean) => {
      emit('update:expanded', expanded);
      emit('toggle', expanded);
    };
    return {
      resolvedContentId: props.contentId || generatedContentId,
      handleToggle,
    };
  },
  render() {
    return (
      <section
        id={this.anchor}
        class={['ai-diagnosis-module-section', { 'is-expanded': this.expanded }]}
      >
        <button
          class='ai-diagnosis-module-section__header'
          aria-controls={this.resolvedContentId}
          aria-expanded={this.expanded}
          type='button'
          onClick={() => this.handleToggle(!this.expanded)}
        >
          {(this.icon || this.iconSrc) && (
            <span class='ai-diagnosis-module-section__icon'>
              {this.iconSrc ? (
                <img
                  alt=''
                  src={this.iconSrc}
                />
              ) : (
                <i
                  class={this.icon}
                  aria-hidden='true'
                />
              )}
            </span>
          )}
          <span class='ai-diagnosis-module-section__title'>{this.title}</span>
          {this.count !== undefined && <span class='ai-diagnosis-module-section__count'>{this.count}</span>}
          {this.summary && <span class='ai-diagnosis-module-section__summary'>{this.summary}</span>}
          <i
            class='icon-monitor icon-arrow ai-diagnosis-module-section__arrow'
            aria-hidden='true'
          />
        </button>
        {this.expanded && (
          <div
            id={this.resolvedContentId}
            class='ai-diagnosis-module-section__content'
          >
            {this.$slots.default?.()}
          </div>
        )}
      </section>
    );
  },
});
