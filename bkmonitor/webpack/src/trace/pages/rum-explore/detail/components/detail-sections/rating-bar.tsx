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

import { RATING_FALLBACK_META, RATING_META } from '../../constants';

import type { IRumRatingBarVM } from '../../typings';

import './rating-bar.scss';

/** Web Vitals 指标评级条：指标值 + 评级标签 + 等宽分段的阈值刻度 */
export default defineComponent({
  name: 'RumRatingBar',
  props: {
    data: {
      type: Object as PropType<IRumRatingBarVM | null>,
      default: null,
    },
  },
  setup(props) {
    return () => {
      const { data } = props;
      if (!data) return null;
      const hitMeta = RATING_META[data.rating] || RATING_FALLBACK_META;
      return (
        <div class='rum-rating-bar'>
          <div class='rating-summary'>
            <span class='rating-metric'>{data.metricLabel}</span>
            <div class='rating-value-row'>
              <span
                style={{ color: hitMeta.color }}
                class='rating-value'
              >
                {data.valueText}
              </span>
              <span
                style={{ color: hitMeta.color, backgroundColor: hitMeta.badgeBgColor }}
                class='rating-badge'
              >
                <span
                  style={{ backgroundColor: hitMeta.color }}
                  class='badge-dot'
                />
                {data.ratingAlias}
              </span>
            </div>
          </div>
          <div class='rating-track-wrap'>
            <div class='rating-track'>
              {data.segments.map(segment => (
                <span
                  key={segment.rating}
                  style={{ backgroundColor: segment.color }}
                  class='track-segment'
                />
              ))}
              {/* 指针用 div：与 track-segment 的 span 区分元素类型，避免被 :last-of-type 命中 */}
              <div
                style={{ left: `${data.thumbPercent}%` }}
                class='track-thumb'
              >
                <i class='icon-monitor icon-dingwei1' />
              </div>
            </div>
            <div class='rating-scale'>
              {data.segments.map(segment => (
                <div
                  key={segment.rating}
                  class='scale-item'
                >
                  <span
                    style={{ color: (RATING_META[segment.rating] || RATING_FALLBACK_META).color }}
                    class='scale-label'
                  >
                    {segment.label}
                  </span>
                  {segment.threshold ? <span class='scale-threshold'>{segment.threshold}</span> : null}
                </div>
              ))}
            </div>
          </div>
        </div>
      );
    };
  },
});
