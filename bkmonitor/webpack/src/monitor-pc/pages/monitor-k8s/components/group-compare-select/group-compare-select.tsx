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

import CompareTime from './compare-time';
import GroupBy from './group-by';
import { ETypeSelect } from './utils';

import './group-compare-select.scss';

@Component
export default class GroupCompareSelect extends tsc<object> {
  typeSelects = {
    [ETypeSelect.compare]: {
      name: window.i18n.tc('对比'),
      width: 96,
    },
    [ETypeSelect.group]: {
      name: 'Group by',
      width: 129,
    },
  };
  typeSelected = ETypeSelect.compare;

  handleChange() {
    this.typeSelected = this.typeSelected === ETypeSelect.compare ? ETypeSelect.group : ETypeSelect.compare;
    return this.typeSelected;
  }

  render() {
    return (
      <div class='common-page___group-compare-select'>
        <div
          style={{
            width: `${this.typeSelects[this.typeSelected].width}px`,
          }}
          class='select-type-wrap'
          onClick={this.handleChange}
        >
          <span class='select-type-name'>{this.typeSelects[this.typeSelected].name}</span>
          <span class='contrast-switch'>
            <i class='icon-monitor icon-switch' />
          </span>
        </div>
        <div class='group-compare-wrap'>
          {this.typeSelected === ETypeSelect.compare ? <CompareTime /> : <GroupBy />}
        </div>
      </div>
    );
  }
}
