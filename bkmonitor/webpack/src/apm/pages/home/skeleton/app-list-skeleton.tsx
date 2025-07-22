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

import './app-list-skeleton.scss';

interface IProps {
  count?: number;
}

@Component
export default class AppListSkeleton extends tsc<IProps> {
  @Prop({ type: Number, default: 10 }) count: number;
  render() {
    return (
      <div class='app-list-skeleton'>
        {new Array(this.count).fill(null).map((_, index) => (
          <div
            key={index}
            class='expan-header'
          >
            <div class='header-left'>
              <span class='icon-monitor icon-mc-triangle-down' />
              <div class='skeleton-01 skeleton-element' />
              <div class='skeleton-02 skeleton-element' />
              <div class='skeleton-03 skeleton-element' />
              <div class='skeleton-04 skeleton-element' />
              <div class='skeleton-05 skeleton-element' />
            </div>
            <div class='header-right'>
              <bk-button
                class='mr-8'
                size='small'
                theme='primary'
                outline
              >
                {this.$t('查看详情')}
              </bk-button>
              <bk-button
                class='mr-8'
                size='small'
              >
                {this.$t('配置')}
              </bk-button>
              <div class='more-btn'>
                <span class='icon-monitor icon-mc-more' />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }
}
