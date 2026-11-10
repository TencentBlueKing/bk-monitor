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

import './timeline-range-marker.scss';

/** 时间轴首尾的起止横幅：开始标记 + 开始日期 / 结束标记 + 时长，文案随检索维度变化 */
export default defineComponent({
  name: 'TimelineRangeMarker',
  props: {
    /** 标记类型：开始 / 结束 */
    type: {
      type: String as PropType<'begin' | 'end'>,
      required: true,
    },
    /** 横幅在时间轴中的位置：正序时开始标记在头部、结束标记在尾部，倒序互换 */
    placement: {
      type: String as PropType<'head' | 'tail'>,
      required: true,
    },
    /** 检索维度：会话时间轴与会话内 View 的时间轴使用不同文案 */
    scope: {
      type: String as PropType<'session' | 'view'>,
      required: true,
    },
    /** 开始日期，如 8月3日 周一 */
    dateText: {
      type: String,
      default: '',
    },
    /** 总时长文本 */
    durationText: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    return () => {
      const isBegin = props.type === 'begin';
      const isHead = props.placement === 'head';
      const keypath = isBegin ? '{0} 会话开始日' : '会话结束 · 总时长 {0}';
      return (
        <div class={['timeline-range-marker', props.type, isHead ? 'is-head' : 'is-tail']}>
          <div class='marker-axis'>
            {isHead ? null : <div class='marker-connector' />}
            <div class='marker-icon'>
              <i class={['marker-shape', isBegin ? 'is-play' : 'is-stop']} />
            </div>
            {isHead ? <div class='marker-connector' /> : null}
          </div>
          <div class='marker-message'>
            <i18n-t
              keypath={keypath}
              tag='span'
            >
              {isBegin ? <span>{props.dateText}</span> : <span class='marker-strong'>{props.durationText}</span>}
            </i18n-t>
          </div>
        </div>
      );
    };
  },
});
