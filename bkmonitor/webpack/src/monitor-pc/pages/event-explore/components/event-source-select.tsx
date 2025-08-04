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

import { ExploreSourceTypeEnum } from '../typing';

import './event-source-select.scss';

interface EventSourceSelectEvents {
  onSelect(source: ExploreSourceTypeEnum[]): void;
}

interface EventSourceSelectProps {
  list: { id: ExploreSourceTypeEnum; name: string }[];
  value: ExploreSourceTypeEnum[];
}

@Component
export default class EventSourceSelect extends tsc<EventSourceSelectProps, EventSourceSelectEvents> {
  @Prop({ default: () => [ExploreSourceTypeEnum.ALL], type: Array }) value!: ExploreSourceTypeEnum[];
  @Prop({ default: () => [] }) list!: EventSourceSelectProps['list'];

  localValue: ExploreSourceTypeEnum[] = [];

  /** 选中全部 */
  selectAll = false;

  iconMap = {
    [ExploreSourceTypeEnum.BCS]: 'icon-bcs',
    [ExploreSourceTypeEnum.BKCI]: 'icon-landun',
    [ExploreSourceTypeEnum.HOST]: 'icon-host',
    [ExploreSourceTypeEnum.DEFAULT]: 'icon-default',
  };

  @Watch('value', { immediate: true })
  handleValueChange(val: ExploreSourceTypeEnum[]) {
    this.selectAll = val.includes(ExploreSourceTypeEnum.ALL);
    if (this.selectAll) {
      this.localValue = [ExploreSourceTypeEnum.ALL, ...this.list.map(item => item.id)];
    } else {
      this.localValue = [...val];
    }
  }

  handleSelectAll(val: boolean) {
    this.selectAll = val;
    this.localValue = val ? [ExploreSourceTypeEnum.ALL, ...this.list.map(item => item.id)] : [];
    this.emitSelect();
  }

  handleSelect(source: ExploreSourceTypeEnum[]) {
    this.localValue = source;
    if (source.length === this.list.length) {
      this.selectAll = true;
      this.localValue.unshift(ExploreSourceTypeEnum.ALL);
    } else {
      this.selectAll = false;
    }
    this.emitSelect();
  }

  @Emit('select')
  emitSelect() {
    return this.localValue;
  }

  render() {
    return (
      <div class='event-source-select-list-xxxxxxx'>
        <div class='event-source-select-item'>
          <bk-checkbox
            value={this.selectAll}
            onChange={this.handleSelectAll}
          >
            <i class='icon-monitor icon-all' />
            <span class='name'>{this.$t('全部来源')}</span>
          </bk-checkbox>
        </div>
        {!!this.list.length && (
          <bk-checkbox-group
            v-model={this.localValue}
            onChange={this.handleSelect}
          >
            {this.list.map(item => (
              <div
                key={item.id}
                class='event-source-select-item'
              >
                <bk-checkbox value={item.id}>
                  <i class={['source-icon', this.iconMap[item.id]]} />
                  <span class='name'>{item.name}</span>
                </bk-checkbox>
              </div>
            ))}
          </bk-checkbox-group>
        )}
      </div>
    );
  }
}
