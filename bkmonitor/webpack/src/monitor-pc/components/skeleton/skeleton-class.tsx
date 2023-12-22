/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import { random } from '../../../monitor-common/utils/utils';

import type { ISkeleton } from './skeleton';

import './skeleton-class.scss';

export interface ISkeletonCompData {
  options: ISkeleton;
  visible: boolean;
  backgroundColor?: string;
  secondaryColor?: string;
  primaryOpacity?: number;
  secondaryOpacity?: number;
  speed?: number;
  animate?: boolean;
}
@Component
export default class SkeletonClassComp extends tsc<{}> {
  options: ISkeleton;
  visible = false;
  backgroundColor = '#f2f2f2';
  secondaryColor = '#e6e6e6';
  primaryOpacity = 1;
  secondaryOpacity = 1;
  speed = 1;
  animate = true;
  render(h) {
    const idClip = random(4);
    const idGradient = random(4);
    return (
      <svg
        class='skeleton-class-wrappper'
        style={{
          display: this.visible === false ? 'none' : 'block'
        }}
        viewBox={`0 0 ${this.options?.width} ${this.options?.height}`}
        version='1.1'
      >
        <rect
          style={{ fill: `url(#${idGradient})` }}
          clip-path={`url(#${idClip})`}
          x='0'
          y='0'
          width={this.options?.width}
          height={this.options?.height}
        />

        <defs>
          <clipPath id={idClip}>
            {(this.options?.skeletons).map(skeleton =>
              h(skeleton.type || 'rect', {
                attrs: skeleton
              })
            )}
          </clipPath>

          <linearGradient id={idGradient}>
            <stop
              offset='0%'
              stop-color={this.backgroundColor}
              stop-opacity={this.primaryOpacity}
            >
              {this.animate ? (
                <animate
                  attributeName='offset'
                  values='-2; 1'
                  dur={`${this.speed}s`}
                  repeatCount='indefinite'
                />
              ) : null}
            </stop>
            <stop
              offset='50%'
              stop-color={this.secondaryColor}
              stop-opacity={this.secondaryOpacity}
            >
              {this.animate ? (
                <animate
                  attributeName='offset'
                  values='-1.5; 1.5'
                  dur={`${this.speed}s`}
                  repeatCount='indefinite'
                />
              ) : null}
            </stop>
            <stop
              offset='100%'
              stop-color={this.backgroundColor}
              stop-opacity={this.primaryOpacity}
            >
              {this.animate ? (
                <animate
                  attributeName='offset'
                  values='-1; 2'
                  dur={`${this.speed}s`}
                  repeatCount='indefinite'
                />
              ) : null}
            </stop>
          </linearGradient>
        </defs>
      </svg>
    );
  }
}
