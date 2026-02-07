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

import { computed, defineComponent, shallowRef } from 'vue';

import { Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { fieldTypeMap } from 'trace/components/retrieval-filter/utils';
import { formatTime } from 'trace/utils/utils';
import { useI18n } from 'vue-i18n';
import JsonPretty from 'vue-json-pretty';

import { DimensionsTypeEnum, eventChartMap } from './typing';

import './event-table-expand-content.scss';

const TabEnum = {
  JSON: 'json',
  KV: 'kv',
} as const;
type ETab = (typeof TabEnum)[keyof typeof TabEnum];

export default defineComponent({
  name: 'EventTableExpandContent',
  props: {
    data: {
      type: Object,
      default: () => ({}),
    },
    timezone: {
      type: Array,
      default: () => [],
    },
  },
  setup(props) {
    const { t } = useI18n();
    const activeTab = shallowRef<ETab>(TabEnum.KV);
    const isKVTab = computed(() => activeTab.value === TabEnum.KV);

    const kvList = computed(() => {
      const list = [];
      for (const key in props.data?.origin_data || {}) {
        if (key === 'time') {
          list.push({
            k: key,
            v: formatTime(+props.data?.origin_data[key]),
            type: 'date',
          });
        } else {
          list.push({
            k: key,
            v: props.data?.origin_data[key],
            type: typeof props.data?.origin_data[key] === 'number' ? 'integer' : 'keyword',
          });
        }
      }
      return list;
    });

    const handleTabChange = (tab: ETab) => {
      activeTab.value = tab;
    };

    const handleCopy = (value: Record<string, any>) => {
      copyText(JSON.stringify(value), msg => {
        Message({
          message: msg,
          theme: 'error',
        });
        return;
      });
      Message({
        message: t('复制成功'),
        theme: 'success',
      });
    };

    return {
      isKVTab,
      kvList,
      handleCopy,
      handleTabChange,
    };
  },
  render() {
    const renderValue = value => {
      if (Array.isArray(value)) {
        return value.join(', ');
      }
      return value;
    };

    return (
      <div
        class={[
          'alarm-center-detail-panel-relation-event-table-expand-content',
          `expand-content-status-${eventChartMap[this.data?.type?.value || DimensionsTypeEnum.DEFAULT]}`,
        ]}
      >
        <div class='view-header'>
          <div class='header-tabs'>
            <span
              class={{ active: this.isKVTab }}
              onClick={() => this.handleTabChange(TabEnum.KV)}
            >
              KV
            </span>
            <span
              class={{ active: !this.isKVTab }}
              onClick={() => this.handleTabChange(TabEnum.JSON)}
            >
              JSON
            </span>
          </div>
        </div>
        <div
          class='view-content kv-view-content'
          v-show={this.isKVTab}
        >
          <div class='content-operation'>
            <i onClick={() => this.handleCopy(this.data?.origin_data || {})}>
              <i
                class='icon-monitor icon-mc-copy'
                v-bk-tooltips={{ content: this.$t('复制'), distance: 5 }}
              />
            </i>
          </div>
          <div class='explore-kv-list'>
            {this.kvList.map((item, index) => (
              <div
                key={`kv-list-item-${index}`}
                class='kv-list-item'
              >
                <div class='item-label'>
                  <span
                    style={{
                      background: fieldTypeMap[item.type]?.bgColor || fieldTypeMap.other.bgColor,
                      color: fieldTypeMap[item.type]?.color || fieldTypeMap.other.color,
                    }}
                    class='option-icon'
                  >
                    <span class={[fieldTypeMap[item.type]?.icon || fieldTypeMap.other.icon, 'option-icon-icon']} />
                  </span>
                  {item.k}
                </div>
                <div class='item-value'>{renderValue(item.v || '--')} </div>
              </div>
            ))}
          </div>
        </div>
        <div
          class='view-content json-view-content'
          v-show={!this.isKVTab}
        >
          <div class='content-operation'>
            <i
              class='icon-monitor icon-mc-copy'
              v-bk-tooltips={{ content: this.$t('复制'), distance: 5 }}
            />
          </div>
          <JsonPretty data={this.data?.origin_data || {}} />
        </div>
      </div>
    );
  },
});
