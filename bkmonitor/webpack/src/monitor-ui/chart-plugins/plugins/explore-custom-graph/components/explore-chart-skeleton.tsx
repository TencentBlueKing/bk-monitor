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

import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './explore-chart-skeleton.scss';

@Component
export default class ExploreChartSkeleton extends tsc<object> {
  itemPercentList = [0.2, 0.7, 0.45, 0.57, 0.2, 0.4, 0.76, 0.34];
  skeletonItemRender(percent: number, isFill = true) {
    return (
      <div
        style={{ height: `${percent * 100}%` }}
        class={`explore-chart-skeleton-item ${isFill ? 'skeleton-element' : ''}`}
      />
    );
  }
  render() {
    return (
      <div class='explore-chart-skeleton'>
        <div class='explore-chart-skeleton-header'>
          <div class='skeleton-header-container'>
            <div class='header-trigger'>
              <div
                style={{ width: '16px', height: '100%' }}
                class='skeleton-element'
              />
              <div
                style={{ width: '220px', height: '100%' }}
                class='skeleton-element'
              />
            </div>
            <div class='header-custom'>
              <div
                style={{ width: '200px', height: '100%' }}
                class='skeleton-element'
              />
              <div
                style={{ width: '110px', height: '100%' }}
                class='skeleton-element'
              />
            </div>
          </div>
        </div>
        <div class='explore-chart-skeleton-content'>
          {this.itemPercentList.map(v => [this.skeletonItemRender(1, false), this.skeletonItemRender(v)])}
          {this.skeletonItemRender(1, false)}
        </div>
        <div class='explore-chart-skeleton-bottom'>
          <div
            style={{ width: '26px', height: '100%' }}
            class='skeleton-element'
          />
        </div>
      </div>
    );
  }
}
