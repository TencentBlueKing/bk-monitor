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
import { type PropType, computed, defineComponent, shallowRef, watch } from 'vue';

import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import { EventRecordSourceType, type IEventRecordItem, type IEventRecordsResult } from '../typing';

import './event-records-message.scss';

export default defineComponent({
  name: 'EventRecordsMessage',
  props: {
    content: {
      type: String,
      default: '',
    },
    result: {
      type: Object as PropType<IEventRecordsResult>,
      required: true,
    },
  },
  setup(props) {
    const { t } = useI18n();
    /** 每次「展开更多」加载的条数 */
    const PAGE_SIZE = 5;
    const SOURCE_ICON_CLASS: Record<string, string> = {
      [EventRecordSourceType.BCS]: 'is-bcs',
      [EventRecordSourceType.BKCI]: 'is-bkci',
      [EventRecordSourceType.HOST]: 'is-host',
      [EventRecordSourceType.DEFAULT]: 'is-default',
    };

    const visibleCount = shallowRef(PAGE_SIZE);

    const visibleItems = computed(() => props.result.items.slice(0, visibleCount.value));
    const hasMore = computed(() => visibleCount.value < props.result.items.length);

    const formatEventTime = (timestamp: number) => dayjs.tz(timestamp).format('YYYY-MM-DD HH:mm:ss ZZ');

    const getSourceIconClass = (type: IEventRecordItem['source']['type']) =>
      SOURCE_ICON_CLASS[type] || SOURCE_ICON_CLASS[EventRecordSourceType.DEFAULT];

    const handleExpandMore = () => {
      visibleCount.value = Math.min(visibleCount.value + PAGE_SIZE, props.result.items.length);
    };

    // 结果切换时重置分页，避免沿用上一条消息的展开进度
    watch(
      () => props.result,
      () => {
        visibleCount.value = PAGE_SIZE;
      }
    );

    return {
      t,
      visibleItems,
      hasMore,
      formatEventTime,
      getSourceIconClass,
      handleExpandMore,
    };
  },
  render() {
    return (
      <div class='event-records-message'>
        {this.content ? <p class='event-records-message-text'>{this.content}</p> : null}
        <div class='event-records-card'>
          <div class='event-records-card-title'>{this.t('共 {n} 个事件', { n: this.result.total })}</div>
          <div class='event-records-card-list'>
            {this.visibleItems.map(item => (
              <div
                key={item.id}
                class='event-records-item'
              >
                <div class='event-records-item-header'>
                  <span class='event-records-source'>
                    <span
                      class={['event-records-source-icon', this.getSourceIconClass(item.source.type)]}
                      aria-hidden='true'
                    />
                    <span class='event-records-source-name'>{item.source.alias}</span>
                  </span>
                  <span class='event-records-item-title'>{item.eventName}</span>
                </div>
                <div class='event-records-item-fields'>
                  {item.fields.map(field => (
                    <div
                      key={`${item.id}-${field.key}`}
                      class='event-records-field'
                    >
                      <span class='event-records-field-key'>{this.t(field.key)}</span>
                      {field.url ? (
                        <a
                          class='event-records-field-value is-link'
                          href={field.url}
                          rel='noopener noreferrer'
                          target='_blank'
                        >
                          {field.value}
                        </a>
                      ) : (
                        <span class='event-records-field-value'>{field.value}</span>
                      )}
                    </div>
                  ))}
                </div>
                <div class='event-records-item-time'>{this.formatEventTime(item.time)}</div>
              </div>
            ))}
          </div>
          {this.hasMore && (
            <button
              class='event-records-expand'
              type='button'
              onClick={this.handleExpandMore}
            >
              <span>{this.t('展开更多')}</span>
              <i
                class='icon-monitor icon-double-down'
                aria-hidden='true'
              />
            </button>
          )}
        </div>
      </div>
    );
  },
});
