/* eslint-disable @typescript-eslint/no-require-imports */
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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './alarm-group-select.scss';

interface IOption {
  id: number | string;
  name: string;
}
interface IProps {
  loading?: boolean;
  options?: IOption[];
  value?: (number | string)[];
  onChange?: (v: (number | string)[]) => void;
  onRefresh?: () => void;
  onTagclick?: (v: number | string) => void;
}
@Component
export default class AlarmGroupSelect extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) value: (number | string)[];
  @Prop({ type: Array, default: () => [] }) options: IOption[];
  @Prop({ type: Boolean, default: false }) loading: boolean;

  localValue: string[] = [];
  tags = [];

  @Watch('value', { immediate: true })
  handleValueChange(v) {
    if (JSON.stringify(this.localValue) !== JSON.stringify(v)) {
      this.localValue = JSON.parse(JSON.stringify(v));
      this.handleSelected(this.localValue);
    }
  }
  @Watch('options', { immediate: true })
  handleOptions(v) {
    if (v.length) {
      this.handleSelected(this.localValue);
    }
  }

  handleSelected(value: (number | string)[]) {
    let tags = [];
    if (value.length) {
      this.options.forEach(item => {
        if (value.includes(item.id)) {
          tags.push({
            id: item.id,
            name: item.name,
          });
        }
      });
    } else {
      tags = [];
    }
    this.tags = tags;
    this.$emit('change', value);
  }

  handleTagClick(event: Event, id: number | string) {
    event?.stopPropagation?.();
    this.$emit('tagclick', id);
  }

  handleAddAlarmGroup() {
    const url = `${location.origin}${location.pathname}?bizId=${this.$store.getters.bizId}#/alarm-group/add`;
    window.open(url);
  }

  handleRefresh() {
    if (this.loading) {
      return;
    }
    this.$emit('refresh');
  }

  handleDelTag(event: Event, index: number) {
    event.stopPropagation();
    this.tags.splice(index, 1);
    this.localValue = this.tags.map(item => item.id);
    this.$emit('change', this.localValue);
  }

  render() {
    return (
      <div class='alarm-dispatch-alarm-group-select-component'>
        <bk-select
          v-model={this.localValue}
          ext-popover-cls={'alarm-dispatch-alarm-group-select-component-pop'}
          multiple
          searchable
          onSelected={this.handleSelected}
        >
          <div
            class='tag-list'
            slot='trigger'
          >
            {this.tags.length > 0 ? (
              this.tags.map((item, index) => (
                <div
                  key={item.id}
                  class='tag-list-item'
                  title={item.name}
                  onClick={e => this.handleTagClick(e, item.id)}
                >
                  <span class='item-name'>{item.name}</span>
                  <span
                    class='icon-monitor icon-mc-close'
                    onClick={e => this.handleDelTag(e, index)}
                  />
                </div>
              ))
            ) : (
              <span class='placeholder'>{this.$t('选择告警组')}</span>
            )}
          </div>
          <div
            class='extension-wrap'
            slot='extension'
          >
            <div
              class='add-wrap'
              onClick={this.handleAddAlarmGroup}
            >
              <span class='icon-monitor icon-jia' />
              <span>{this.$t('新增告警组')}</span>
            </div>
            <div
              class='loading-wrap'
              onClick={this.handleRefresh}
            >
              {this.loading ? (
                <img
                  class='status-loading'
                  alt=''
                  src={require('../../../static/images/svg/spinner.svg')}
                />
              ) : (
                <span class='icon-monitor icon-mc-retry' />
              )}
            </div>
          </div>
          {this.options.map(item => (
            <bk-option
              id={item.id}
              key={item.id}
              name={item.name}
            />
          ))}
        </bk-select>
      </div>
    );
  }
}
