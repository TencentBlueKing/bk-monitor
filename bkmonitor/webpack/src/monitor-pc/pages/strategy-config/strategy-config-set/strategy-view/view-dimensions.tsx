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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from '../../../../../monitor-common/utils';

import './view-dimensions.scss';

interface IMenu {
  id: string | number;
  name: string;
  readonly?: boolean;
  disabled?: boolean;
  hidden?: boolean;
}

interface IDimensionOption {
  id: string;
  name: string;
  show: boolean;
  list: IMenu[];
}

interface IProps {
  dimensionData: IDimensionOption;
  value: object;
  onChange?: (v: object) => void;
}

@Component
export default class ViewDimensions extends tsc<IProps> {
  // 维度列表
  @Prop({ default: () => [], type: Array }) dimensionData!: IDimensionOption[];
  @Prop({ default: () => ({}), type: Object }) value: object;

  localValues = {};

  @Watch('dimensionData', { immediate: true })
  handleWatchDimensionData(value: IDimensionOption[]) {
    value.forEach(item => {
      if (!!item.name && !this.localValues?.[item.id]) {
        this.localValues[item.id] = '';
      }
    });
  }

  @Debounce(300)
  @Emit('change')
  handleSelectChange() {
    return JSON.parse(JSON.stringify(this.localValues));
  }

  created() {
    if (!Object.keys(this.localValues).length) {
      this.localValues = this.value;
    } else {
      Object.keys(this.value).forEach(key => {
        this.localValues[key] = this.value[key];
      });
    }
  }

  handleItemChange(item: IDimensionOption, v: string) {
    this.$set(this.localValues, item.id, v);
    this.handleSelectChange();
  }

  render() {
    return (
      <div class='strategy-view-dimensions-component'>
        {this.dimensionData
          .filter(item => !!item.name)
          .map(item => (
            <div
              class='dimensions-panel-item'
              key={item.id}
            >
              <div class='item-title'>{item.name}</div>
              <div class='item-content'>
                <bk-select
                  class='item-content-select'
                  value={this.localValues[item.id]}
                  allowCreate
                  searchable
                  size='small'
                  onChange={v => this.handleItemChange(item, v)}
                >
                  {item.list.map(l => (
                    <bk-option
                      key={l.id}
                      id={l.id}
                      name={l.id}
                    ></bk-option>
                  ))}
                </bk-select>
              </div>
            </div>
          ))}
      </div>
    );
  }
}
