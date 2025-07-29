/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { type PropType, computed, defineComponent, inject, nextTick, onMounted, onUnmounted, ref } from 'vue';

import * as authorityMap from 'apm/pages/home/authority-map';
import _isEqual from 'lodash/isEqual';
import { traceDetail } from 'monitor-api/modules/apm_trace';

import SpanDetails from '../../../pages/main/span-details';
import { QUERY_TRACE_RELATION_APP } from '../../../store/constant';
import { useAuthorityStore } from '../../../store/modules/authority';
import { useTraceStore } from '../../../store/modules/trace';
import { useChildrenHiddenInject } from '../hooks';
import ListView from './list-view';

import type { Span, TNil, Trace } from '../typings';

import './virtualized-trace-view.scss';

type RowState = {
  bgColorIndex?: number;
  isDetail: boolean;
  span: Span;
  spanIndex: number;
};

const VirtualizedTraceViewProps = {
  registerAccessors: Function as PropType<(accesors: any) => void>,
  setSpanNameColumnWidth: Function as PropType<(width: number) => void>,
  setTrace: Function as PropType<(trace: TNil | Trace, uiFind: string | TNil) => void>,
  focusUiFindMatches: Function as PropType<(trace: Trace, uiFind: string | TNil, allowHide?: boolean) => void>,
  shouldScrollToFirstUiFindMatch: {
    type: Boolean,
  },
  uiFind: {
    type: String,
  },
  detailStates: {
    type: Object,
  },
  hoverIndentGuideIds: {
    type: Array as PropType<string[]>,
  },
  spanNameColumnWidth: {
    type: Number,
  },
  traceID: {
    type: String,
  },
  handleShowSpanDetail: Function as PropType<(span: Span) => void>,
};

export function generateRowStates(
  spans: Span[] | TNil,
  childrenHiddenIDs: Set<unknown>,
  detailStates: Record<string, any> | undefined
): RowState[] {
  if (!spans) {
    return [];
  }

  let collapseDepth = null;
  let rowStates: RowState[] = [];
  for (let i = 0; i < spans.length; i++) {
    const span = spans[i];
    const { spanID, depth } = span;
    let hidden = false;

    if (collapseDepth != null) {
      if (depth >= collapseDepth) {
        hidden = true;
      } else {
        collapseDepth = null;
      }
    }
    if (hidden) {
      continue;
    }
    if (childrenHiddenIDs.has(spanID)) {
      collapseDepth = depth + 1;
    }
    rowStates.push({
      span,
      isDetail: false,
      spanIndex: i,
    });
    if (detailStates?.has(spanID)) {
      rowStates.push({
        span,
        isDetail: true,
        spanIndex: i,
      });
    }
  }
  rowStates = handleSetBgColorIndex(rowStates);

  return rowStates;
}

/** 设置背景色层级 */
function handleSetBgColorIndex(list: RowState[]) {
  let bgColorIndex = 0;
  return list.map((item: RowState, index: number) => {
    if (index) {
      const curDepth = item.span.depth;
      const prevDepth = list[index - 1]?.span.depth;
      if (curDepth !== prevDepth) {
        // 与上一层层级不同则说明为间隔新区间
        bgColorIndex += 1;
      }
    }

    return { ...item, bgColorIndex };
  });
}

export const DEFAULT_HEIGHTS = {
  bar: 28,
  detail: 161,
  detailWithLogs: 197,
};

export default defineComponent({
  name: 'VirtualizedTraceView',
  props: VirtualizedTraceViewProps,
  emits: ['showSpanDetail'],
  setup(props) {
    const store = useTraceStore();
    const authorityStore = useAuthorityStore();
    const virtualizedTraceViewElm = ref();
    const listViewElm = ref(null);
    const curShowDetailSpanId = ref<string>('');
    const haveReadSpanIds = ref<string[]>([]);
    const showSpanDetails = ref(false);
    const spanDetails = ref<null | Span>(null);
    const activeTab = ref('BasicInfo');

    const childrenHiddenStore = useChildrenHiddenInject();
    const isFullscreen = inject('isFullscreen', false);

    const traceTree = computed(() => store.traceTree);
    const spans = computed(() => store.spanGroupTree);
    const getRowStates = computed<RowState[]>(() => {
      const { detailStates } = props;

      return traceTree.value
        ? generateRowStates(spans.value, childrenHiddenStore?.childrenHiddenIds.value, detailStates)
        : [];
    });

    onMounted(() => {
      document.addEventListener('keydown', handleEscKeydown);
    });

    onUnmounted(() => {
      document.removeEventListener('keydown', handleEscKeydown);
    });

    function handleEscKeydown(evt) {
      if (evt.code === 'Escape') showSpanDetails.value = false;
    }

    /** 点击span事件 */
    const handleSpanClick = (span: Span, isEventTab = false) => {
      curShowDetailSpanId.value = span.spanID;
      if (!haveReadSpanIds.value.includes(span.spanID)) {
        haveReadSpanIds.value.push(span.spanID);
      }
      showSpanDetails.value = true;
      spanDetails.value = span;
      activeTab.value = isEventTab ? 'Event' : 'BasicInfo';
    };

    /** 获取跨应用span */
    const getAcrossAppInfo = async (span: Span) => {
      const {
        app_name: appName,
        trace_id: traceId,
        bk_biz_id: bkBizId,
        permission,
        bk_app_code: appCode,
      } = span.cross_relation;
      if (!permission) {
        // 无权限查看跨应用
        handleApplyApp(appCode, bkBizId);
      } else {
        if (span.hasChildren) return; // 跨应用 span 已加载过

        store.setTraceLoaidng(true);
        const params = {
          app_name: appName,
          trace_id: traceId,
          bk_biz_id: bkBizId,
          [QUERY_TRACE_RELATION_APP]: store.traceViewFilters.includes(QUERY_TRACE_RELATION_APP),
        };
        const data = await traceDetail(params).catch(() => null);
        if (data) {
          store.setAcrossAppTraceInfo(data);
        }
        store.setTraceLoaidng(false);
      }
    };
    /** 申请应用权限 */
    const handleApplyApp = (id: number, bizId: number) => {
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const action_ids = authorityMap.VIEW_AUTH;
      const resources = [{ id, type: 'apm_application' }];
      authorityStore.getIntanceAuthDetail(action_ids, resources, bizId);
    };
    /** 展开分组折叠的节点 */
    const handleToggleCollapse = (groupID, status) => {
      nextTick(() => store.updateSpanGroupCollapse(groupID, status));
    };
    /** 点击上一跳/下一跳 */
    const handlePrevNextClicked = flag => {
      // 获取当前spanId, spanIndex
      const curSpanId = spanDetails.value?.span_id;
      const curSpanIndex = spans.value.findIndex(span => span.span_id === curSpanId);

      if (curSpanIndex === -1) return; // 找不到当前 span，直接返回

      if (flag === 'next') {
        // 展开节点
        spanDetails.value.hasChildren &&
          Boolean(childrenHiddenStore?.childrenHiddenIds.value.has(curSpanId)) &&
          childrenHiddenStore?.onChange(curSpanId || '');
        spanDetails.value = spans.value[curSpanIndex + 1];
      } else {
        // 上一跳
        spanDetails.value = spans.value
          .slice(0, curSpanIndex)
          .reverse()
          .find(({ depth }) => depth === spanDetails.value.depth || depth === spanDetails.value.depth - 1);
      }
    };

    return {
      virtualizedTraceViewElm,
      listViewElm,
      getRowStates,
      handleSpanClick,
      getAcrossAppInfo,
      haveReadSpanIds,
      showSpanDetails,
      isFullscreen,
      spanDetails,
      traceTree,
      spans,
      handlePrevNextClicked,
      handleToggleCollapse,
      activeTab,
    };
  },

  render() {
    const { spanNameColumnWidth } = this.$props;

    return (
      <div
        ref='virtualizedTraceViewElm'
        class='virtualized-trace-view-spans'
      >
        <ListView
          ref='listViewElm'
          activeSpanId={this.spanDetails?.span_id || ''}
          dataLength={this.getRowStates.length}
          detailStates={this.detailStates}
          haveReadSpanIds={this.haveReadSpanIds}
          // key={this.spans.length}
          itemsWrapperClassName='virtualized-trace-view-rows-wrapper'
          spanNameColumnWidth={spanNameColumnWidth}
          viewBuffer={300}
          viewBufferMin={100}
          windowScroller
          onGetCrossAppInfo={this.getAcrossAppInfo}
          onItemClick={this.handleSpanClick}
          onToggleCollapse={this.handleToggleCollapse}
        />
        <SpanDetails
          activeTab={this.activeTab}
          isFullscreen={this.isFullscreen}
          isShowPrevNextButtons={true}
          show={this.showSpanDetails}
          spanDetails={this.spanDetails as Span}
          onPrevNextClicked={flag => {
            this.handlePrevNextClicked(flag);
          }}
          onShow={v => (this.showSpanDetails = v)}
        />
      </div>
    );
  },
});
