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
import type { PropType } from 'vue';
import { computed, defineComponent } from 'vue';

import { Tag } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import { getStatusInfo } from '../../../utils';

import type { ActionDetail } from '../../../typings/action-detail';

import './action-detail-info.scss';
export default defineComponent({
  name: 'ActionDetailInfo',
  props: {
    detail: {
      type: Object as PropType<ActionDetail>,
      default: null,
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const { t } = useI18n();

    const renderActionName = () => {
      return (
        <div class='action-name'>
          <span>{props.detail?.action_name || '--'}</span>
        </div>
      );
    };

    const renderOperator = () => {
      return props.detail?.operator?.length
        ? props.detail?.operator.map((v, index, arr) => [
            <bk-user-display-name
              key={`user-display-${v}`}
              user-id={v}
            />,
            index !== arr.length - 1 ? <span key={`span-colon-${v}`}>{';'}</span> : null,
          ])
        : '--';
    };

    const renderStatus = () => {
      const statusInfo = getStatusInfo(props.detail?.status, props.detail?.failure_type);
      return <Tag class={statusInfo.status}>{statusInfo.text}</Tag>;
    };

    const renderContent = () => {
      const content = props.detail?.content;
      const arrContent = content?.text?.split('$');
      const link = arrContent?.[1] || '';

      return (
        <div class='info-jtnr'>
          {arrContent?.[0] || ''}
          {link ? (
            <span
              class='info-jtnr-link'
              onClick={() => content?.url && window.open(content.url)}
            >
              <span class='icon-monitor icon-copy-link' />
              {link}
            </span>
          ) : undefined}
          {arrContent?.[2] || ''}
        </div>
      );
    };

    const infoItems = computed(() => {
      return [
        [
          { label: t('套餐名称'), id: 'action_name', value: renderActionName },
          { label: t('告警目标'), id: 'bk_target_display', value: props.detail?.bk_target_display || '--' },
        ],
        [
          {
            label: t('套餐类型'),
            id: 'action_plugin_type_display',
            value: props.detail?.action_plugin_type_display || '--',
          },
          { label: t('处理时长'), id: 'duration', value: props.detail?.duration || '--' },
        ],
        [
          { label: t('负责人'), id: 'operator', value: renderOperator },
          { label: t('执行对象'), id: 'operate_target_string', value: props.detail?.operate_target_string || '--' },
        ],
        [
          {
            label: t('开始时间'),
            id: 'create_time',
            value: dayjs.tz(props.detail?.create_time * 1000).format('YYYY-MM-DD HH:mm:ss'),
          },
          { label: t('执行状态'), id: 'status', value: renderStatus },
        ],
        [
          {
            label: t('结束时间'),
            id: 'update_time',
            value: dayjs.tz(props.detail?.update_time * 1000).format('YYYY-MM-DD HH:mm:ss'),
          },
          { label: t('触发信号'), id: 'signal_display', value: props.detail?.signal_display },
        ],
        [
          {
            label: t('具体内容'),
            id: 'content',
            value: renderContent,
          },
        ],
      ];
    });

    return {
      infoItems,
    };
  },
  render() {
    return (
      <div class='action-detail-info'>
        <div class='action-detail-info-title'>{this.$t('处理详情')}</div>
        <div class='action-detail-info-content'>
          {this.infoItems.map((row, index) => (
            <div
              key={index}
              class='info-content-row'
            >
              {row.map(col => (
                <div
                  key={col.id}
                  class='info-content-col'
                >
                  <div class='info-content-col-label'>{col.label}</div>
                  {this.loading ? (
                    <div class='info-content-col-value-skeleton skeleton-element' />
                  ) : (
                    <div class='info-content-col-value'>
                      {typeof col.value === 'function' ? col.value() : col.value}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  },
});
