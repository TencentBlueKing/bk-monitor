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

import { RumTimelineSortEnum } from '../../constants';
import TimelineRangeMarker from './timeline-range-marker';
import TimelineViewAxis from './timeline-view-axis';
import TimelineViewHidden from './timeline-view-hidden';
import TraceContextPanel from './trace-context-panel';

import type {
  IRumTimelineCardItemVM,
  IRumTimelineSpanVM,
  IRumTimelineViewVM,
  RumTimelineSortType,
} from '../../typings';

import './timeline-view-list.scss';

/**
 * 时间轴列表：首尾起止横幅 + 每行左侧时间轴 + View 卡片。
 * 会话时间轴与会话内 View 的链路上下文共用，差异只在传入的卡片与文案。
 */
export default defineComponent({
  name: 'TimelineViewList',
  props: {
    /** 排序后的展示列表：View 卡片或折叠中间 View 的隐藏卡片 */
    cardItems: {
      type: Array as PropType<IRumTimelineCardItemVM[]>,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
    /** 接口失败 */
    error: {
      type: Boolean,
      default: false,
    },
    /** 筛选生效时卡片默认展开，保证命中项可见 */
    hasFilter: {
      type: Boolean,
      default: false,
    },
    /** 当前详情的 span 类型，透传给卡片头部判断是否展示「View 详情」 */
    spanType: {
      type: String,
    },
    /** 检索维度，决定起止横幅的文案 */
    scope: {
      type: String as PropType<'session' | 'view'>,
      required: true,
    },
    /** 排序方向：只影响首尾横幅的位置，排序由数据层完成 */
    sort: {
      type: String as PropType<RumTimelineSortType>,
      default: RumTimelineSortEnum.ASC,
    },
    /** 开始日期，为空时不展示开始横幅 */
    beginText: {
      type: String,
      default: '',
    },
    /** 总时长文本，为空时不展示结束横幅 */
    endText: {
      type: String,
      default: '',
    },
  },
  emits: {
    expandFold: (_key: string) => true,
    expandHidden: () => true,
    toggleNode: (_spanId: string) => true,
    spanClick: (_span: IRumTimelineSpanVM) => true,
    traceClick: (_traceId: string) => true,
    viewClick: (_view: IRumTimelineViewVM) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    function renderEmpty() {
      if (props.loading) {
        return (
          <TraceContextPanel
            error={false}
            items={[]}
            spanType={props.spanType}
            view={null}
            loading
          />
        );
      }
      if (props.error) {
        return (
          <Exception
            class='detail-empty'
            description={t('查询链路上下文失败，请稍后重试')}
            scene='part'
            type='500'
          />
        );
      }
      return (
        <Exception
          class='detail-empty'
          description={props.hasFilter ? t('无匹配的 Span') : t('暂无时间轴数据')}
          scene='part'
          type='empty'
        />
      );
    }

    return () => {
      if (!props.cardItems.length) return renderEmpty();
      /** 倒序时时间由晚到早，结束横幅随之上移到头部、开始横幅落到尾部 */
      const isAsc = props.sort === RumTimelineSortEnum.ASC;
      const beginMarker = props.beginText ? (
        <TimelineRangeMarker
          dateText={props.beginText}
          placement={isAsc ? 'head' : 'tail'}
          scope={props.scope}
          type='begin'
        />
      ) : null;
      const endMarker = props.endText ? (
        <TimelineRangeMarker
          durationText={props.endText}
          placement={isAsc ? 'tail' : 'head'}
          scope={props.scope}
          type='end'
        />
      ) : null;
      return (
        <div class='rum-timeline'>
          {isAsc ? beginMarker : endMarker}
          {props.cardItems.map(item => (
            <div
              key={item.kind === 'hidden' ? 'hidden' : item.card.key}
              class='rum-timeline-row'
            >
              <TimelineViewAxis
                count={item.kind === 'hidden' ? item.count : undefined}
                hasError={item.kind === 'hidden' ? false : item.card.view.errorCount > 0}
                loadingType={item.kind === 'hidden' ? '' : item.card.view.loadingTypeValue}
                timeText={item.kind === 'hidden' ? '' : item.card.timeText}
              />
              <div class='rum-timeline-main'>
                {item.kind === 'hidden' ? (
                  <TimelineViewHidden
                    count={item.count}
                    onExpand={() => emit('expandHidden')}
                  />
                ) : (
                  <TraceContextPanel
                    defaultExpanded={props.hasFilter}
                    error={props.error}
                    items={item.card.items}
                    loading={props.loading}
                    spanType={props.spanType}
                    view={item.card.view}
                    onExpandFold={key => emit('expandFold', key)}
                    onSpanClick={span => emit('spanClick', span)}
                    onToggleNode={spanId => emit('toggleNode', spanId)}
                    onTraceClick={traceId => emit('traceClick', traceId)}
                    onViewClick={view => emit('viewClick', view)}
                  />
                )}
              </div>
            </div>
          ))}
          {isAsc ? endMarker : beginMarker}
        </div>
      );
    };
  },
});
