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
import { Component, Ref, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import customEscalationViewStore from '@store/modules/custom-escalation-view';

import SelectPanel from './select-panel';

import './index.scss';

interface IProps {
  value: {
    field: string;
    split: boolean;
  }[];
  splitable: boolean;
}

interface IEmit {
  onChange: (value: IProps['value']) => void;
}

@Component
export default class AggregateDimensions extends tsc<IProps, IEmit> {
  @Prop({ type: Array, required: true }) readonly value: IProps['value'];
  @Prop({ type: Boolean, default: false }) readonly splitable: IProps['splitable'];

  @Ref('rootRef') rootRef: HTMLElement;
  @Ref('wrapperRef') wrapperRef: HTMLElement;

  get currentSelectedMetricList() {
    return customEscalationViewStore.currentSelectedMetricList;
  }

  localValue: Readonly<IProps['value']> = [];
  isWholeLine = false;

  get demensionList() {
    const demenesionNameMap = {};
    return this.currentSelectedMetricList.reduce<{ name: string }[]>((result, item) => {
      item.dimensions.forEach(demesionItem => {
        if (!demenesionNameMap[demesionItem.name]) {
          result.push(demesionItem);
          demenesionNameMap[demesionItem.name] = true;
        }
      });
      return result;
    }, []);
  }

  @Watch('value', { immediate: true })
  valueChange() {
    this.localValue = [...this.value];
  }

  triggerChange() {
    this.$emit('change', this.localValue);
  }

  handleChange(value: IProps['value']) {
    this.localValue = Object.freeze(value);
    this.triggerChange();
  }

  handleRemove(index: number) {
    const localValue = [...this.localValue];
    localValue.splice(index, 1);
    this.localValue = Object.freeze(localValue);
    this.triggerChange();
  }

  resizeLayout() {
    const resizeObserver = new ResizeObserver(() => {
      const totalWrapperWidth = this.rootRef.parentElement.clientWidth;
      const itemsTotalWidth = Array.from(this.rootRef.parentElement.children).reduce((acc, childEle) => {
        const childItem = childEle === this.rootRef ? this.wrapperRef : childEle;
        return acc + childItem.clientWidth;
      }, 0);
      this.isWholeLine = totalWrapperWidth < itemsTotalWidth + 80;
    });
    resizeObserver.observe(this.wrapperRef);
    this.$once('hook:beforeDestroy', () => {
      resizeObserver.disconnect();
    });
  }

  mounted() {
    this.resizeLayout();
  }

  render() {
    return (
      <div
        ref='rootRef'
        style={{
          width: this.isWholeLine ? '100%' : 'auto',
        }}
        class='new-metric-view-group-by'
      >
        <div
          ref='wrapperRef'
          class='wrapper'
        >
          <div class='label'>{this.$t('聚合维度')}</div>
          <div class='value-wrapper'>
            {this.localValue.map((item, index) => (
              <div
                key={item.field}
                class='value-item'
              >
                {item.split && <i class='icon-monitor icon-chaitu split-flag' />}
                {item.field}
                <i
                  class='icon-monitor icon-mc-close'
                  onClick={() => this.handleRemove(index)}
                />
              </div>
            ))}
          </div>
          <SelectPanel
            style='margin-left: 6px'
            data={this.demensionList}
            splitable={this.splitable}
            value={this.localValue as IProps['value']}
            onChange={this.handleChange}
          />
        </div>
      </div>
    );
  }
}
