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

import JsonPretty from 'vue-json-pretty';

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
  },
  setup() {
    const activeTab = shallowRef<ETab>(TabEnum.JSON);
    const isKVTab = computed(() => activeTab.value === TabEnum.KV);

    const handleTabChange = (tab: ETab) => {
      activeTab.value = tab;
    };
    return {
      isKVTab,
      handleTabChange,
    };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-relation-event-table-expand-content'>
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
            <i
              class='icon-monitor icon-mc-copy'
              v-bk-tooltips={{ content: this.$t('复制'), distance: 5 }}
            />
          </div>
          <div class='explore-kv-list'>
            {new Array(10).fill(null).map((_, index) => (
              <div
                key={index}
                class='kv-list-item'
              >
                <div class='item-label'>键</div>
                <div class='item-value'>值</div>
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
          <JsonPretty data={this.data} />
        </div>
      </div>
    );
  },
});
