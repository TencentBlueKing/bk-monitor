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

import type { IRumTimelineSpanVM } from '../../typings';

import './timeline-span-row.scss';

/** 子级每层相对父级的缩进 */
const LEVEL_INDENT = 16;

/** 链路上下文里的一行 Span：时间、类型标签、名称，行尾为关联 Trace、状态码与耗时 */
export default defineComponent({
  name: 'TimelineSpanRow',
  props: {
    data: {
      type: Object as PropType<IRumTimelineSpanVM>,
      required: true,
    },
  },
  emits: {
    toggle: (_spanId: string) => true,
    spanClick: (_span: IRumTimelineSpanVM) => true,
    traceClick: (_traceId: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    const handleTitleClick = () => {
      /** 当前 Span 的详情就在本抽屉里，不再重复打开 */
      if (props.data.isCurrent) return;
      emit('spanClick', props.data);
    };

    return () => {
      const { data } = props;
      return (
        <div class={{ 'timeline-span-row': true, 'is-current': data.isCurrent }}>
          <div class='row-main'>
            <span class='row-time'>{data.timeText}</span>
            <span class='row-toggle'>
              {data.expandable ? (
                <i
                  class={{ 'icon-monitor icon-mc-triangle-down toggle-icon': true, 'is-expanded': data.expanded }}
                  onClick={() => emit('toggle', data.spanId)}
                />
              ) : null}
            </span>
            <span
              style={{ backgroundColor: data.tag.bgColor, marginLeft: `${data.level * LEVEL_INDENT}px` }}
              class='row-type-tag'
            >
              {data.tag.icon ? (
                <img
                  class='type-tag-icon'
                  alt=''
                  src={data.tag.icon}
                />
              ) : null}
              <span class='type-tag-label'>{data.tag.label}</span>
            </span>
            <span class='row-title-wrap'>
              <span
                class={{ 'row-title': true, 'is-clickable': !data.isCurrent }}
                v-overflow-tips
                onClick={handleTitleClick}
              >
                {data.title}
              </span>
              {data.isCurrent ? <span class='current-span-tag'>{t('当前 Span')}</span> : null}
            </span>
          </div>
          <div class='row-extra'>
            {data.traceId ? (
              <span
                class='row-trace-link'
                onClick={() => emit('traceClick', data.traceId)}
              >
                <i class='icon-monitor icon-dingwei1' />
                {t('关联 Trace')}
              </span>
            ) : null}
            {data.statusCode ? (
              <span
                style={{ color: data.statusCode.color, backgroundColor: data.statusCode.bgColor }}
                class='row-status-code'
              >
                {data.statusCode.text}
              </span>
            ) : null}
            <span class='row-duration'>{data.durationText}</span>
          </div>
        </div>
      );
    };
  },
});
