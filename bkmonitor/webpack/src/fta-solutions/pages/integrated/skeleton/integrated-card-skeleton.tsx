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

import './integrated-card-skeleton.scss';

const list = [
  {
    name: window.i18n.t('已安装'),
    child: 6,
  },
  {
    name: window.i18n.t('已停用'),
    child: 6,
  },
  {
    name: window.i18n.t('可用'),
    child: 6,
  },
];

@Component
export default class IntegratedCardSkeleton extends tsc<object> {
  render() {
    return (
      <div class='integrated-card-skeleton'>
        {list.map((item, index) => (
          <div
            key={index}
            class='wrap-item'
          >
            <div class='header-wrap'>
              <span class='bk-icon icon-angle-right' />
              <span class='name'>{item.name}</span>
              <span class='group-number'>(0)</span>
            </div>
            <div class='content-title'>
              <span class='title-tip' />
              {this.$t('事件插件')}
            </div>
            <div class='content-wrap'>
              {new Array(item.child).fill(null).map((_item, cindex) => (
                <div
                  key={cindex}
                  class='card-item'
                >
                  <div class='skeleton-element w-48 h-48 mt-28' />
                  <div class='skeleton-element w-86 h-20 mt-8' />
                  {/* <div class='bottom'>
                    <div class='skeleton-element w-39 h-16 mr-98' />
                    <div class='skeleton-element w-39 h-16' />
                  </div> */}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }
}
