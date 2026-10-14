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

import { Exception } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import TimelineFoldRow from './timeline-fold-row';
import TimelineSpanRow from './timeline-span-row';
import TimelineViewHeader from './timeline-view-header';

import type { IRumTimelineItemVM, IRumTimelineSpanVM, IRumTimelineViewVM } from '../../typings';

import './trace-context-panel.scss';

/** 骨架屏占位行数，与有锚点时的默认可见行数（折叠行 + 5 行 + 折叠行）接近 */
const SKELETON_ROW_COUNT = 6;

/**
 * 「链路上下文」tab 内容：当前 Span 所属 View 的全部 Span 链路。
 * 只负责加载 / 异常 / 空态与列表编排，数据与展开状态由 useTraceContext 提供。
 */
export default defineComponent({
  name: 'TraceContextPanel',
  props: {
    loading: {
      type: Boolean,
      default: false,
    },
    /** 接口失败 */
    error: {
      type: Boolean,
      default: false,
    },
    view: {
      type: Object as PropType<IRumTimelineViewVM | null>,
      default: null,
    },
    items: {
      type: Array as PropType<IRumTimelineItemVM[]>,
      default: () => [],
    },
  },
  emits: {
    expandFold: (_key: string) => true,
    toggleNode: (_spanId: string) => true,
    spanClick: (_span: IRumTimelineSpanVM) => true,
    traceClick: (_traceId: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    function renderSkeleton() {
      return (
        <div class='trace-context-card'>
          <div class='trace-context-skeleton-header'>
            <div class='skeleton-element skeleton-title' />
            <div class='skeleton-element skeleton-detail' />
          </div>
          <div class='trace-context-timeline'>
            {Array.from({ length: SKELETON_ROW_COUNT }, (_, index) => (
              <div
                key={index}
                class='trace-context-skeleton-row'
              >
                <div class='skeleton-element' />
              </div>
            ))}
          </div>
        </div>
      );
    }

    function renderItems() {
      if (!props.items.length) {
        return (
          <Exception
            class='trace-context-empty'
            description={t('暂无数据')}
            scene='part'
            type='empty'
          />
        );
      }
      return props.items.map(item =>
        item.kind === 'fold' ? (
          <TimelineFoldRow
            key={item.data.key}
            data={item.data}
            onExpand={key => emit('expandFold', key)}
          />
        ) : (
          <TimelineSpanRow
            key={item.data.spanId}
            data={item.data}
            onSpanClick={span => emit('spanClick', span)}
            onToggle={spanId => emit('toggleNode', spanId)}
            onTraceClick={traceId => emit('traceClick', traceId)}
          />
        )
      );
    }

    function renderContent() {
      if (props.loading) return renderSkeleton();
      if (props.error) {
        return (
          <Exception
            class='trace-context-empty'
            description={t('查询链路上下文失败，请稍后重试')}
            scene='part'
            type='500'
          />
        );
      }
      if (!props.view) {
        return (
          <Exception
            class='trace-context-empty'
            description={t('暂无链路上下文数据')}
            scene='part'
            type='empty'
          />
        );
      }
      return (
        <div class='trace-context-card'>
          <TimelineViewHeader data={props.view} />
          <div class='trace-context-timeline'>{renderItems()}</div>
        </div>
      );
    }

    return () => <div class='rum-trace-context'>{renderContent()}</div>;
  },
});
