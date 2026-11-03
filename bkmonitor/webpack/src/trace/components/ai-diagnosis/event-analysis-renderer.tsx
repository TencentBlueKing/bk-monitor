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
import { type PropType, defineComponent, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import DiagnosisCollapseCard from './diagnosis-collapse-card';
import { useDiagnosisCardsState } from './use-diagnosis-cards-state';
import bcsSourceIcon from '@/static/img/ai-diagnosis/source-bcs.svg';
import itsmSourceIcon from '@/static/img/ai-diagnosis/source-itsm.svg';

import type { DiagnosisInteraction, EventAnalysisGroupViewModel, EventAnalysisViewModel } from './types';

export default defineComponent({
  name: 'EventAnalysisRenderer',
  props: {
    items: {
      type: Array as PropType<Array<EventAnalysisGroupViewModel | EventAnalysisViewModel>>,
      default: () => [],
    },
    summary: {
      type: String,
      default: '',
    },
    expandedIds: {
      type: Array as PropType<string[]>,
      default: undefined,
    },
    expandAll: {
      type: Boolean,
      default: undefined,
    },
  },
  emits: {
    interaction: (_interaction: DiagnosisInteraction) => true,
    prompt: (_prompt: string) => true,
    'update:expandedIds': (_expandedIds: string[]) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const expandedGroups = shallowRef<string[]>([]);
    const getGroups = () => props.items.filter((item): item is EventAnalysisGroupViewModel => 'items' in item);
    const cardsState = useDiagnosisCardsState({
      getCardIds: () => props.items.flatMap(item => ('items' in item ? item.items.map(event => event.id) : [item.id])),
      getControlledExpandedIds: () => props.expandedIds,
      getDefaultExpandedIds: () =>
        props.items.flatMap(item => ('items' in item ? item.items.slice(0, 1).map(event => event.id) : [item.id])),
      getExpandAll: () => props.expandAll,
      onUpdate: expandedIds => emit('update:expandedIds', expandedIds),
      onInteraction: interaction => emit('interaction', interaction),
    });
    watch(
      () => [props.expandAll, props.items] as const,
      ([expandAll]) => {
        expandedGroups.value = expandAll === false ? [] : getGroups().map(group => group.id);
      },
      { immediate: true }
    );
    return {
      t,
      expandedGroups,
      ...cardsState,
      handlePrompt: (prompt: string) => emit('prompt', prompt),
      toggleGroup: (id: string) => {
        expandedGroups.value = expandedGroups.value.includes(id)
          ? expandedGroups.value.filter(groupId => groupId !== id)
          : [...expandedGroups.value, id];
      },
    };
  },
  render() {
    const groups: EventAnalysisGroupViewModel[] = this.items.map((item, index) =>
      'items' in item
        ? item
        : {
            fields: {
              eventName: this.t('事件名称'),
              time: this.t('发生时间'),
              reason: this.t('事件内容'),
            },
            id: `event-group-${item.id}`,
            items: [item],
            source: 'other',
            title: item.title || this.t('事件分组 {0}', [index + 1]),
          }
    );
    return (
      <div class='ai-diagnosis-domain-renderer ai-diagnosis-event'>
        {this.summary && (
          <div class='ai-diagnosis-domain-summary'>
            <strong>{this.t('事件分析总结：')}</strong>
            <span>{this.summary}</span>
          </div>
        )}
        {groups.map(group => {
          const groupExpanded =
            this.expandedGroups.includes(group.id) || (this.expandAll !== false && group.id.startsWith('event-group-'));
          const countText =
            group.total === undefined
              ? ''
              : this.t('(共 {0} {1}事件，展示 Top{2} 如下)', [
                  group.total,
                  group.unit || this.t('个'),
                  group.top || group.items.length,
                ]);
          return (
            <section
              key={group.id}
              class={['ai-diagnosis-event__group', { 'is-expanded': groupExpanded }]}
            >
              <div
                class='ai-diagnosis-event__group-header'
                onClick={() => this.toggleGroup(group.id)}
              >
                <button
                  class='ai-diagnosis-event__group-toggle'
                  aria-expanded={groupExpanded}
                  type='button'
                  onClick={(event: MouseEvent) => {
                    event.stopPropagation();
                    this.toggleGroup(group.id);
                  }}
                >
                  <i
                    class='icon-monitor icon-arrow-solid-right ai-diagnosis-event__group-arrow'
                    aria-hidden='true'
                  />
                  {group.source === 'bcs' || group.source === 'itsm' ? (
                    <img
                      class='ai-diagnosis-event__source-icon'
                      alt=''
                      src={group.source === 'bcs' ? bcsSourceIcon : itsmSourceIcon}
                    />
                  ) : (
                    <i
                      class='icon-monitor icon-event ai-diagnosis-event__source-icon'
                      aria-hidden='true'
                    />
                  )}
                  <strong>{group.title}</strong>
                  {countText && (
                    <span>
                      {countText
                        .split(/(\d+|Top\d+)/g)
                        .map((part, index) =>
                          /^\d+$|^Top\d+$/.test(part) ? <strong key={index}>{part}</strong> : part
                        )}
                    </span>
                  )}
                </button>
                {typeof group.total === 'number' ? (
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
                      this.handlePrompt(this.t('{0}这 {1} 个事件分别是什么？', [group.title, group.total]));
                    }}
                  >
                    <i
                      class='icon-monitor icon-fenxiang'
                      aria-hidden='true'
                    />
                  </button>
                ) : null}
              </div>
              {groupExpanded && (
                <div class='ai-diagnosis-event__group-content'>
                  <div class='ai-diagnosis-event__rail'>
                    {group.items.map((item, index) => (
                      <DiagnosisCollapseCard
                        key={item.id}
                        v-slots={{
                          action: () =>
                            item.interaction ? (
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
                                  this.handleInteraction(item.interaction);
                                }}
                              >
                                <i
                                  class='icon-monitor icon-fenxiang'
                                  aria-hidden='true'
                                />
                              </button>
                            ) : null,
                        }}
                        card={{
                          id: item.id,
                          index: index + 1,
                          interaction: item.interaction,
                          rows: Object.entries(group.fields).flatMap(([key, label]) => {
                            const fallback: Record<string, string | undefined> = {
                              eventName: item.eventName,
                              reason: item.reason,
                              time: item.time,
                            };
                            const value = item.values?.[key] ?? fallback[key];
                            return value === undefined || value === '' ? [] : [{ key, label, value }];
                          }),
                          title: item.title || item.eventName || this.t('事件 {0}', [index + 1]),
                        }}
                        expanded={this.isExpanded(item.id)}
                        onInteraction={this.handleInteraction}
                        onToggle={expanded => this.handleToggle(item.id, expanded)}
                      />
                    ))}
                  </div>
                </div>
              )}
            </section>
          );
        })}
      </div>
    );
  },
});
