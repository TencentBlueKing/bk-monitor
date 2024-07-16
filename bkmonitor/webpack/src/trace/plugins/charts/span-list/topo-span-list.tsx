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

import { type PropType, computed, defineComponent } from 'vue';
import { ref } from 'vue';

import { useTraceStore } from '../../../store/modules/trace';
import { ETopoType } from '../../../typings';
import SpanList from './span-list';

import type { Span } from '../../../components/trace-view/typings';
import type { SpanListItem } from './span-list';
export default defineComponent({
  name: 'TopoSpanList',
  props: {
    type: {
      type: String as PropType<ETopoType>,
      default: ETopoType.time,
    },
    // 过滤的 Span Id 列表
    filterSpanIds: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    // 子标题
    subTitle: {
      type: String,
      required: false,
      default: '',
    },
    // 对比的 Span 列表
    compareSpanList: {
      type: Array as PropType<Span[]>,
      default: () => [],
    },
    // 对比状态
    isCompare: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['viewDetail', 'listChange'],
  setup(props, { emit }) {
    const store = useTraceStore();
    const triggerSpan = ref({});

    /** 原始SpanList */
    const originSpanList = computed<SpanListItem[]>(() => {
      let list = [];
      if (props.type === ETopoType.time) {
        list = props.isCompare && props.compareSpanList.length ? props.compareSpanList : store.traceTree?.spans || [];
      } else {
        list = store.serviceSpanList || [];
      }
      return transformSpanList(list, props.type);
    });

    /** 经过过滤的spanList */
    const localSpanList = computed<SpanListItem[]>(() => {
      if (props.filterSpanIds.length) {
        if (props.type === ETopoType.time) {
          return originSpanList.value.filter(item => props.filterSpanIds.includes(item.spanId));
        }
        return transformSpanList(
          store.traceData.original_data
            .filter(item => props.filterSpanIds.includes(item.span_id))
            .map(item => ({ ...triggerSpan.value, ...item, duration: item.elapsed_time })),
          ETopoType.service
        );
      }
      return originSpanList.value;
    });

    /** 转化spanList结构，保持一致性 */
    function transformSpanList(spanList = [], type: ETopoType): SpanListItem[] {
      if (type === ETopoType.time) {
        return (
          spanList.map(item => ({
            icon: item.icon,
            kind: item.kind,
            name: item.service_name,
            operationName: item.operationName,
            duration: item.duration,
            spanId: item.spanID,
            mark: item.mark,
            bgColor: item.bgColor,
            color: item.color,
            startTime: item.startTime,
          })) || []
        );
      }
      return spanList.map(item => ({
        icon: item.icon,
        kind: item.kind,
        name: item.service_name,
        operationName: item.operation_name,
        duration: item.duration,
        spanId: item.span_id,
        collapsed: item.collapsed || false,
        collapsedSpanNum: item.collapsed_span_num,
        spanIds: item.span_ids || [],
        color: item.color,
        startTime: item.start_time,
      }));
    }

    /** 查看详情 */
    function handleViewDetail(span: SpanListItem) {
      emit('viewDetail', span.spanId);
    }

    /** 切换spanList */
    function handleListChange(ids: string[], span: SpanListItem) {
      if (span) {
        const { name, operationName, icon, color } = originSpanList.value.find(item => item.spanId === span.spanId);
        triggerSpan.value = {
          service_name: name,
          operation_name: operationName,
          icon,
          color,
        };

        emit('listChange', ids, span.name);
      } else {
        triggerSpan.value = {};
        emit('listChange', ids);
      }
    }

    return {
      localSpanList,
      handleViewDetail,
      handleListChange,
    };
  },
  render() {
    return (
      <SpanList
        isCompare={this.isCompare}
        spanList={this.localSpanList}
        subTitle={this.subTitle}
        onListChange={this.handleListChange}
        onViewDetail={this.handleViewDetail}
      />
    );
  },
});
