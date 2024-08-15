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

import './advanced-filter-skeleton.scss';

@Component
export default class AdvancedFilterSkeleton extends tsc<object> {
  render() {
    const domFn = (config, key) =>
      config.map((item, index) => (
        <div
          key={`${key}_${index}`}
          style={{
            marginTop: `${item.mt}px`,
          }}
          class='container-01'
        >
          <div
            style={{
              width: `${item.lw}px`,
              marginLeft: `${item.lml}px`,
            }}
            class='h-24 skeleton-element'
          />
          <div class='h-24 w-24 skeleton-element' />
        </div>
      ));
    return (
      <div class='advanced-filter-skeleton'>
        <div class='h-24 w-auto skeleton-element' />
        {domFn(
          [
            { lw: 106, lml: 12, mt: 8 },
            { lw: 119, lml: 12, mt: 4 },
            { lw: 70, lml: 12, mt: 4 },
          ],
          '1'
        )}
        <div class='h-24 w-auto mt-8 skeleton-element' />
        {domFn(
          [
            { lw: 106, lml: 12, mt: 8 },
            { lw: 119, lml: 36, mt: 4 },
            { lw: 70, lml: 36, mt: 4 },
            { lw: 89, lml: 36, mt: 4 },
            { lw: 106, lml: 12, mt: 4 },
            { lw: 70, lml: 36, mt: 4 },
            { lw: 95, lml: 36, mt: 4 },
            { lw: 95, lml: 36, mt: 4 },
          ],
          '2'
        )}
        <div class='h-24 w-auto mt-8 skeleton-element' />
        {domFn(
          [
            { lw: 106, lml: 12, mt: 8 },
            { lw: 119, lml: 12, mt: 4 },
            { lw: 70, lml: 12, mt: 4 },
          ],
          '3'
        )}
      </div>
    );
  }
}
