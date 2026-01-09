/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import CycleInput from 'monitor-pc/components/cycle-input/cycle-input';

import './index.scss';

interface IProps {
  showLabel?: boolean;
  value?: number | string;
  onChange?: (val: number | string) => void;
}

@Component
export default class IntervalCreator extends tsc<IProps> {
  /* 是否展示左侧标签 */
  @Prop({ default: true }) showLabel: boolean;
  @Prop({ default: 60 }) value: number | string;
  interval: number | string = 'auto';

  @Watch('value', { immediate: true })
  handleValueChange(val: number | string) {
    this.interval = val;
  }

  @Emit('change')
  handleIntervalChange(val) {
    this.interval = val;
    return val;
  }

  render() {
    return (
      <div class='new-metric-view-interval'>
        {this.showLabel && <div class='interval-label'>{this.$slots?.label || this.$t('汇聚周期')}</div>}
        <CycleInput
          class='form-interval'
          v-model={this.interval}
          hasExpanded={true}
          needAuto={false}
          onChange={(v: number) => this.handleIntervalChange(v)}
        />
      </div>
    );
  }
}
