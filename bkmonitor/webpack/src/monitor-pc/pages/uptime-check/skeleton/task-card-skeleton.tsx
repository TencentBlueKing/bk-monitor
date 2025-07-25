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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './task-card-skeleton.scss';

interface IProps {
  num?: number;
  type?: number;
}

@Component
export default class TaskCardSkeleton extends tsc<IProps> {
  @Prop({ type: Number, default: 1 }) type: number;
  @Prop({ type: Number, default: 2 }) num: number;

  renderType() {
    if (this.type === 1) {
      return (
        <div class='uptime-check-task-card-skeleton-01'>
          <div class='head'>
            <div class='head-ring skeleton-element' />
            <div class='head-right'>
              <div class='skeleton-element h-16 w-84' />
              <div class='head-right-bottom'>
                <div class='skeleton-element h-16 w-54 mr-4' />
                <div class='skeleton-element h-16 w-54 mr-4' />
                <div class='skeleton-element h-16 w-54' />
              </div>
            </div>
          </div>
          <div class='bottom'>
            <div class='bottom-item'>
              <div class='bottom-item-head'>
                <div class='skeleton-element h-16 w-84' />
                <div class='skeleton-element h-16 w-27' />
              </div>
              <div class='skeleton-element w-auto h-3 mt-6' />
            </div>
            <div class='bottom-item'>
              <div class='bottom-item-head'>
                <div class='skeleton-element h-16 w-60' />
                <div class='skeleton-element h-16 w-27' />
              </div>
              <div class='skeleton-element w-auto h-3 mt-6' />
            </div>
            <div class='bottom-item'>
              <div class='bottom-item-head'>
                <div class='skeleton-element h-16 w-73' />
                <div class='skeleton-element h-16 w-27' />
              </div>
              <div class='skeleton-element w-auto h-3 mt-6' />
            </div>
          </div>
        </div>
      );
    }
    return (
      <div class='uptime-check-task-card-skeleton-02'>
        <div class='header'>
          <div class='skeleton-element h-22 w-88' />
          <div class='skeleton-element h-16 w-177 mt-6' />
        </div>
        <div class='bottom'>
          <div class='skeleton-element h-82 w-110 mr-32' />
          <div class='skeleton-element h-82 w-110' />
        </div>
      </div>
    );
  }

  render() {
    return this.renderType();
  }
}
