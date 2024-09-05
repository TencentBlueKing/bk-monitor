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

import './resource-topo-skeleton.scss';
@Component
export default class ResourceTopoSkeleton extends tsc<object> {
  render() {
    return (
      <div class='resource-topo-skeleton'>
        <svg
          width='208px'
          height='520px'
          version='1.1'
          viewBox='0 0 208 520'
          xmlns='http://www.w3.org/2000/svg'
          xmlns:xlink='http://www.w3.org/1999/xlink'
        >
          <defs>
            <linearGradient
              id='gradient-fill'
              x1='0%'
              x2='100%'
              y1='0%'
              y2='0%'
            >
              <stop
                offset='0%'
                stop-color='rgba(0, 0, 0, 0.06)'
              />
              <stop
                offset='50%'
                stop-color='rgba(0, 0, 0, 0.15)'
              />
              <stop
                offset='100%'
                stop-color='rgba(0, 0, 0, 0.06)'
              />
              <animate
                attributeName='x1'
                dur='1.4s'
                repeatCount='indefinite'
                values='0%;100%'
              />
              <animate
                attributeName='x2'
                dur='1.4s'
                repeatCount='indefinite'
                values='100%;200%'
              />
            </linearGradient>
            <linearGradient
              id='gradient-path'
              x1='0%'
              x2='100%'
              y1='0%'
              y2='0%'
            >
              <stop
                offset='0%'
                stop-color='rgba(0, 0, 0, 0.16)'
              />
              <stop
                offset='50%'
                stop-color='rgba(0, 0, 0, 0.45)'
              />
              <stop
                offset='100%'
                stop-color='rgba(0, 0, 0, 0.16)'
              />
              <animate
                attributeName='x1'
                dur='1.4s'
                repeatCount='indefinite'
                values='0%;100%'
              />
              <animate
                attributeName='x2'
                dur='1.4s'
                repeatCount='indefinite'
                values='100%;200%'
              />
            </linearGradient>
          </defs>
          <g
            fill='none'
            fill-rule='evenodd'
            stroke='none'
            stroke-width='1'
          >
            <g>
              <g
                stroke='url(#gradient-path)'
                transform='translate(20, 40)'
              >
                <line
                  stroke='#C4C6CC'
                  x1='84'
                  x2='84'
                  y1='90.5703125'
                  y2='163'
                />
                <line
                  stroke='#C4C6CC'
                  x1='83.5'
                  x2='83.9635281'
                  y1='191.5'
                  y2='253'
                />
                <path d='M0,202 C0,224.282247 84,227.653333 83.9640664,248' />
                <path
                  d='M1.8189894e-12,96 C1.8189894e-12,128.454577 84,133.364638 83.9640664,163'
                  transform='translate(41.982, 129.5) scale(1, -1) translate(-41.982, -129.5)'
                />
                <path
                  d='M84,202 C84,224.282247 168,227.653333 167.964066,248'
                  transform='translate(125.982, 225) scale(-1, 1) translate(-125.982, -225)'
                />
                <path
                  d='M84,96 C84,128.454577 168,133.364638 167.964066,163'
                  transform='translate(125.982, 129.5) scale(-1, -1) translate(-125.982, -129.5)'
                />
                <line
                  stroke='#C4C6CC'
                  x1='83.5'
                  x2='83.5'
                  y1='287.5'
                  y2='345.5'
                />
                <line
                  stroke='#C4C6CC'
                  x1='84'
                  x2='84.5'
                  y1='0'
                  y2='55.5'
                />
                <line
                  stroke='#C4C6CC'
                  x1='83.9635281'
                  x2='83.5'
                  y1='383'
                  y2='439.5'
                />
              </g>
              <g transform='translate(84, 0)'>
                <circle
                  cx='20'
                  cy='20'
                  fill='#FFFFFF'
                  r='19'
                  stroke='url(#gradient-fill)'
                  stroke-width='2'
                />
                <circle
                  cx='20'
                  cy='20'
                  fill='url(#gradient-fill)'
                  fill-rule='nonzero'
                  r='12'
                />
              </g>
              <g transform='translate(84, 96)'>
                <circle
                  cx='20'
                  cy='20'
                  fill='#FFFFFF'
                  r='19'
                  stroke='url(#gradient-fill)'
                  stroke-width='2'
                />
                <circle
                  cx='20'
                  cy='20'
                  fill='url(#gradient-fill)'
                  fill-rule='nonzero'
                  r='12'
                />
              </g>
              <g transform='translate(84, 192)'>
                <circle
                  cx='20'
                  cy='20'
                  fill='#FFFFFF'
                  r='19'
                  stroke='url(#gradient-fill)'
                  stroke-width='2'
                />
                <circle
                  cx='20'
                  cy='20'
                  fill='url(#gradient-fill)'
                  fill-rule='nonzero'
                  r='12'
                />
              </g>
              <g transform='translate(84, 288)'>
                <circle
                  cx='20'
                  cy='20'
                  fill='#FFFFFF'
                  r='19'
                  stroke='url(#gradient-fill)'
                  stroke-width='2'
                />
                <circle
                  cx='20'
                  cy='20'
                  fill='url(#gradient-fill)'
                  fill-rule='nonzero'
                  r='12'
                />
              </g>
              <g transform='translate(84, 384)'>
                <circle
                  cx='20'
                  cy='20'
                  fill='#FFFFFF'
                  r='19'
                  stroke='url(#gradient-fill)'
                  stroke-width='2'
                />
                <circle
                  cx='20'
                  cy='20'
                  fill='url(#gradient-fill)'
                  fill-rule='nonzero'
                  r='12'
                />
              </g>
              <g transform='translate(84, 480)'>
                <circle
                  cx='20'
                  cy='20'
                  fill='#FFFFFF'
                  r='19'
                  stroke='url(#gradient-fill)'
                  stroke-width='2'
                />
                <circle
                  cx='20'
                  cy='20'
                  fill='url(#gradient-fill)'
                  fill-rule='nonzero'
                  r='12'
                />
              </g>
              <g transform='translate(0, 203)'>
                <circle
                  cx='20'
                  cy='20'
                  fill='#FFFFFF'
                  r='19'
                  stroke='url(#gradient-fill)'
                  stroke-width='2'
                />
                <circle
                  cx='20'
                  cy='20'
                  fill='url(#gradient-fill)'
                  fill-rule='nonzero'
                  r='12'
                />
              </g>
              <g transform='translate(168, 203)'>
                <circle
                  cx='20'
                  cy='20'
                  fill='#FFFFFF'
                  r='19'
                  stroke='url(#gradient-fill)'
                  stroke-width='2'
                />
                <circle
                  cx='20'
                  cy='20'
                  fill='url(#gradient-fill)'
                  fill-rule='nonzero'
                  r='12'
                />
              </g>
            </g>
          </g>
        </svg>
      </div>
    );
  }
}
