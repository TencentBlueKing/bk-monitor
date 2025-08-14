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

import './filter-list.scss';

interface FilterSkeletonProps {
  bodyCountPerGroup?: number; // 每个组体中条目的数量
  groupCount?: number; // 总共的组体数量
  titleCount?: number; // 可配置的标题数量
}
@Component
export default class FilterSkeleton extends tsc<FilterSkeletonProps> {
  @Prop({ default: 4 }) readonly titleCount!: number;
  @Prop({ default: 5 }) readonly bodyCountPerGroup!: number;
  @Prop({ default: 4 }) readonly groupCount!: number;

  createTitle() {
    return <span class='skeleton-element item-title' />;
  }

  createBody() {
    return <span class='skeleton-element item-content' />;
  }

  createGroup(bodyCount: number) {
    return (
      <div class='item-group'>
        {this.createTitle()}
        {[...Array(bodyCount)].map(() => this.createBody())}
      </div>
    );
  }

  render() {
    return (
      <div class='filter-panel-skeleton'>
        {[...Array(this.groupCount)].map(() => this.createGroup(this.bodyCountPerGroup))}
      </div>
    );
  }
}
