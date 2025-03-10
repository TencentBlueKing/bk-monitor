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
import { Component, Ref, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import _ from 'lodash';
import { makeMap } from 'monitor-common/utils/make-map';

import './edit-offset.scss';

interface IProps {
  value: string[];
}

interface IEmit {
  onChange: (value: string[]) => void;
}

@Component
export default class CompareWay extends tsc<IProps, IEmit> {
  @Prop({ type: Array, default: () => [] }) readonly value: IProps['value'];

  @Ref('popoverRef') popoverRef: any;

  offsetList = Object.freeze([
    {
      id: '1h',
      name: this.$t('1小时前'),
    },
    {
      id: '1d',
      name: this.$t('昨天'),
    },
    {
      id: '7d',
      name: this.$t('上周'),
    },
    {
      id: '30d',
      name: this.$t('1 月前'),
    },
  ]);

  localValue: string[] = [];
  tempEditValue: string[] = [];

  get resultList() {
    const valueMap = makeMap(this.localValue);
    return _.filter(this.offsetList, item => valueMap[item.id]);
  }

  triggerChange() {
    this.$emit('change', [...this.localValue]);
  }

  handleBeginEdit() {
    this.tempEditValue = [...this.localValue];
  }
  handleEndEdit() {
    this.localValue = [...this.tempEditValue];
    this.triggerChange();
  }

  handleRemove(id: string) {
    this.localValue = _.filter(this.localValue, item => item !== id);
    this.triggerChange();
  }

  mounted() {
    this.popoverRef.showHandler();
  }

  render() {
    return (
      <div class='compare-type-time-edit-offset'>
        <div class='result-list'>
          {this.resultList.map(item => (
            <div
              key={item.id}
              class='offset-tag'
            >
              {item.name}
              <i
                class='icon-monitor icon-mc-close remove-btn'
                onClick={() => this.handleRemove(item.id)}
              />
            </div>
          ))}
        </div>
        <bk-popover
          ref='popoverRef'
          tippy-options={{
            placement: 'bottom-start',
            arrow: false,
            distance: 8,
            onHidden: this.handleEndEdit,
            onShow: this.handleBeginEdit,
          }}
          theme='light compare-type-time-edit-offset'
          trigger='click'
        >
          <div class='append-btn'>
            <i class='icon-monitor icon-a-1jiahao' />
          </div>
          <div
            class='wrapper'
            slot='content'
          >
            <bk-checkbox-group v-model={this.tempEditValue}>
              {this.offsetList.map(offsetItem => (
                <div
                  key={offsetItem.id}
                  class='time-item'
                >
                  <bk-checkbox value={offsetItem.id}>{offsetItem.name}</bk-checkbox>
                </div>
              ))}
              {/* <div class='time-item'>
                <bk-checkbox />
                {this.$t('自定义')}
                <bk-date-picker
                  style='width: 128px; margin-left: 12px;'
                  transfer={true}
                />
              </div> */}
            </bk-checkbox-group>
          </div>
        </bk-popover>
      </div>
    );
  }
}
