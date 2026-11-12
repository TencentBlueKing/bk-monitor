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

import { RUM_VIEW_LOADING_TYPE_ICONS } from '../../constants';

import type { RumViewLoadingType } from '../../typings';

import './timeline-view-axis.scss';

/**
 * 卡片左侧的时间轴：开始时间 + 类型图标，上下连线跨过卡片间距与相邻卡片相接。
 * 图标暂用统一的占位符，取值口径为 View 的 view.loading_type。
 */
export default defineComponent({
  name: 'TimelineViewAxis',
  props: {
    /** View 开始时间，HH:mm；折叠卡片不展示时间 */
    timeText: {
      type: String,
      default: '',
    },
    /** 折叠卡片隐藏的 View 数量，有值时用数字圆代替类型图标 */
    count: {
      type: Number as PropType<number | undefined>,
      default: undefined,
    },
    /** 卡片内含有异常时，类型图标改用红底白字 */
    hasError: {
      type: Boolean,
      default: false,
    },
    /** 路由类型（view.loading_type），当前图标为占位符，后续按该值映射图标 */
    loadingType: {
      type: String as PropType<'' | RumViewLoadingType>,
      default: '',
    },
  },
  setup(props) {
    return () => (
      <div class={{ 'timeline-view-axis': true, 'is-collapsed': props.count !== undefined }}>
        <div class='axis-connector is-top' />
        <div class='axis-content'>
          {props.timeText ? <span class='axis-time'>{props.timeText}</span> : null}
          <div class={['axis-icon', { 'is-error': props.hasError }]}>
            {RUM_VIEW_LOADING_TYPE_ICONS[props.loadingType] && (
              <i class={['icon-monitor', RUM_VIEW_LOADING_TYPE_ICONS[props.loadingType]]} />
            )}
            {props.count > 0 && <span class='axis-count'>{props.count}</span>}
          </div>
        </div>
        <div class='axis-connector is-bottom' />
      </div>
    );
  },
});
