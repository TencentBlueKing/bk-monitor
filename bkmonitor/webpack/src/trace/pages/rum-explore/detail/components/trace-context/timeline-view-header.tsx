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
import { defineComponent } from 'vue';
import type { PropType } from 'vue';

import { useI18n } from 'vue-i18n';

import type { IRumTimelineViewVM } from '../../typings';

import './timeline-view-header.scss';

/** 链路上下文顶部的 View 头部：路由标题、路由类型、CLS、请求数、操作数与停留时长 */
export default defineComponent({
  name: 'TimelineViewHeader',
  props: {
    data: {
      type: Object as PropType<IRumTimelineViewVM>,
      required: true,
    },
  },
  setup(props) {
    const { t } = useI18n();

    /** 数字加粗的统计项，如「42 个请求」 */
    function renderMetric(key: string, keypath: string, value: number | string) {
      return (
        <i18n-t
          key={key}
          keypath={keypath}
          tag='span'
        >
          <span class='metric-value'>{value}</span>
        </i18n-t>
      );
    }

    return () => {
      const { data } = props;
      const metrics = [
        data.cls ? (
          <span
            key='cls'
            style={{ color: data.cls.color }}
            class='view-cls'
            v-bk-tooltips={{ content: data.cls.tip }}
          >
            {data.cls.text}
          </span>
        ) : null,
        renderMetric('request', '{0} 个请求', data.requestCount),
        renderMetric('action', '{0} 个操作', data.actionCount),
        data.durationText ? renderMetric('duration', '停留 {0}', data.durationText) : null,
      ].filter(Boolean);

      return (
        <div class='timeline-view-header'>
          <div class='view-title-row'>
            <span
              class='view-title'
              v-overflow-tips
            >
              {data.title}
            </span>
            {data.isCurrent ? <span class='current-span-tag'>{t('当前 Span')}</span> : null}
          </div>
          <div class='view-detail'>
            {data.loadingType ? <span class='view-loading-type'>{data.loadingType}</span> : null}
            {/* 每个统计项前带分隔点，没有路由类型标签时首项不带 */}
            {metrics.map((metric, index) => [index > 0 || data.loadingType ? <i class='view-dot' /> : null, metric])}
          </div>
        </div>
      );
    };
  },
});
