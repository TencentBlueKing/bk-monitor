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
import dayjs from 'dayjs';
import { copyText } from 'monitor-common/utils/utils';
import { xssFilter } from 'monitor-common/utils/xss';
import { useAppStore } from 'trace/store/modules/app';
import { useI18n } from 'vue-i18n';
import JsonPretty from 'vue-json-pretty';

import './event-table-expand-content.scss';

// 事件状态
const statusMap = {
  RECOVERED: window.i18n.t('已恢复'),
  ABNORMAL: window.i18n.t('未恢复'),
  CLOSED: window.i18n.t('已失效'),
};

// 事件级别
const levelMap = {
  1: window.i18n.t('致命'),
  2: window.i18n.t('预警'),
  3: window.i18n.t('提醒'),
};

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
  setup(props) {
    const { t } = useI18n();
    const appStore = useAppStore();
    const activeTab = shallowRef<ETab>(TabEnum.KV);
    const isKVTab = computed(() => activeTab.value === TabEnum.KV);

    const kvList = computed(() => {
      if (props.data) {
        const { data } = props;
        return [
          {
            k: t('事件ID'),
            v: data.id,
          },
          {
            k: t('异常时间'),
            v: dayjs.tz(data.anomaly_time * 1000).format('YYYY-MM-DD HH:mm'),
          },
          {
            k: t('告警名称'),
            v: data.alert_name,
          },
          {
            k: t('事件状态'),
            v: statusMap[data.status],
          },
          {
            k: t('分类'),
            v: data.category_display,
          },
          {
            k: t('空间ID'),
            v: appStore.bizList.find(item => item.bk_biz_id === data.bk_biz_id)?.space_id || data.bk_biz_id,
          },
          {
            k: t('告警内容'),
            v: data.description,
          },
          {
            k: t('策略ID'),
            v: data.strategy_id || '--',
          },
          {
            k: t('负责人'),
            v: data?.assignee?.length
              ? data?.assignee.map((v, index, arr) => [
                  <span key={`span-assignee-${v}`}>{v}</span>,
                  index !== arr.length - 1 ? <span key={`span-colon-${v}`}>{','}</span> : null,
                ])
              : '--',
          },
          {
            k: t('平台事件ID'),
            v: data.id,
          },
          {
            k: t('事件级别'),
            v: `${levelMap[data.severity]}`,
          },
          {
            k: t('插件ID'),
            v: data.plugin_id,
          },
          {
            k: t('事件时间'),
            v: dayjs.tz(data.time * 1000).format('YYYY-MM-DD HH:mm:ss'),
          },
          {
            k: t('维度'),
            v: data.tags?.length ? (
              <span
                v-bk-tooltips={{
                  content: (
                    <div>
                      {data.tags?.map((item, index) => {
                        return <div key={index}>{`${xssFilter(item.key)}：${xssFilter(item.value)}`}</div>;
                      }) || ''}
                    </div>
                  ),
                }}
              >
                {data.tags.map((item, index) => (
                  <span key={`span-tag-${index}`}>{`${item.key}：${item.value}`} </span>
                ))}
              </span>
            ) : (
              '--'
            ),
          },
          {
            k: t('指标项'),
            v: data.metric?.join('; ') || '--',
          },
          {
            k: t('目标类型'),
            v: data.target_type || '--',
          },
          {
            k: t('事件目标'),
            v: data.target || '--',
          },
        ];
      }
      return [];
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
    return (
      <div
        class={[
          'alarm-center-detail-panel-relation-event-table-expand-content',
          `expand-content-status-${this.data.severity}`,
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
            <i
              class='icon-monitor icon-mc-copy'
              v-bk-tooltips={{ content: this.$t('复制'), distance: 5 }}
              onClick={() => this.handleCopy(this.data)}
            />
          </div>
          <div class='explore-kv-list'>
            {this.kvList.map((item, index) => (
              <div
                key={`kv-list-item-${index}`}
                class='kv-list-item'
              >
                <div class='item-label'>{item.k}</div>
                <div class='item-value'>{item.v}</div>
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
