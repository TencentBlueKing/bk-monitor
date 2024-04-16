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

import './basic-info-skeleton.scss';

@Component
export default class BasicInfoSkeleton extends tsc<{}> {
  render() {
    return (
      <div class='event-detail-basic-info-skeleton'>
        <div class='w--100 h-24 skeleton-element'></div>
        <div class='container-01'>
          <div class='container-01-left'>
            <div class='top-wrap'>
              <div class='container-01-left-left'>
                {new Array(4).fill(null).map((_item, index) => (
                  <div
                    class='w--100 h-20 mr-80 mt-10 skeleton-element'
                    key={index}
                  ></div>
                ))}
              </div>
              <div class='container-01-left-right'>
                {new Array(4).fill(null).map((_item, index) => (
                  <div
                    class='w--100 h-20 mr-80 mt-10 skeleton-element'
                    key={index}
                  ></div>
                ))}
              </div>
            </div>
            <div class='bottom-wrap'>
              {new Array(3).fill(null).map((_item, index) => (
                <div
                  class='w--100 h-20 mr-80 mt-10 skeleton-element'
                  key={index}
                ></div>
              ))}
            </div>
          </div>
          <div class='container-01-right'>
            <div class='w-158 h-100 skeleton-element'></div>
          </div>
        </div>
      </div>
    );
  }
}
