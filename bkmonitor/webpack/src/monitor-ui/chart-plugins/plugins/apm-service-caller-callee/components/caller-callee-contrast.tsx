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
/** 主被调 - 右侧对比模式栏 */
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { type IDataItem, type IListItem, type IServiceConfig, EParamsMode } from '../type';
import ContrastView from './common-comp/contrast-view';
import GroupByView from './common-comp/group-by-view';

import './caller-callee-contrast.scss';
interface ICallerCalleeContrastEvent {
  onContrastDatesChange?: (val: string[]) => void;
  onGroupByChange?: (val: string[]) => void;
  onGroupFilter?: () => void;
  onLimitChange?: (val: number) => void;
  onMethodChange?: (val: string) => void;
  onMetricCalType?: (val: string) => void;
  onTypeChange?: (val: EParamsMode) => void;
}
interface ICallerCalleeContrastProps {
  contrastDates?: string[];
  groupBy?: string[];
  limit?: number;
  method?: string;
  metricCalType?: string;
  paramsMode?: EParamsMode;
  searchList: IServiceConfig[];
  supportedCalculationTypes?: IListItem[];
  supportedMethods?: IListItem[];
  timeStrShow?: IDataItem;
}
@Component({
  name: 'CallerCalleeContrast',
  components: {},
})
export default class CallerCalleeContrast extends tsc<ICallerCalleeContrastProps, ICallerCalleeContrastEvent> {
  @Prop({ required: true, type: Array, default: () => [] }) searchList: IServiceConfig[];
  @Prop({ type: Array, default: () => [] }) supportedCalculationTypes: IListItem[];
  @Prop({ type: Array, default: () => [] }) supportedMethods: IListItem[];
  @Prop({ type: Array, default: () => [] }) contrastDates: string[];
  @Prop({ type: Array, default: () => [] }) groupBy: string[];
  @Prop({ type: String, default: '' }) method: string;
  @Prop({ type: Number, default: 0 }) limit: number;
  @Prop({ type: String, default: '' }) metricCalType: string;
  @Prop({ type: String, default: EParamsMode.contrast }) paramsMode: EParamsMode;
  @Prop({ type: Object, default: () => {} }) timeStrShow: IDataItem;
  active = EParamsMode.contrast;
  config = [
    {
      key: EParamsMode.contrast,
      label: window.i18n.t('对比'),
      width: 96,
    },
    {
      key: EParamsMode.group,
      label: 'Group by',
      width: 129,
    },
  ];

  get activeConfig() {
    return this.config.find(item => item.key === this.active);
  }

  @Watch('paramsMode', { immediate: true })
  handleWatchParamsMode(val: EParamsMode) {
    if (this.active !== val) {
      this.active = val;
    }
  }

  @Emit('typeChange')
  handleChange() {
    this.active = this.active === EParamsMode.contrast ? EParamsMode.group : EParamsMode.contrast;
    return this.active;
  }

  handleContrastDatesChange(val: string[]) {
    this.$emit('contrastDatesChange', val);
  }
  handleGroupByChange(val: string[]) {
    this.$emit('groupByChange', val);
  }

  @Emit('metricCalType')
  handleChangeMetricCalType(val) {
    return val;
  }
  @Emit('methodChange')
  handleChangeMethod(val) {
    return val;
  }
  @Emit('limitChange')
  handleChangeLimit(val) {
    return val;
  }

  render() {
    return (
      <div class='caller-callee-contrast'>
        <div
          style={`width:${this.activeConfig.width}px`}
          class='contrast-left'
          onClick={this.handleChange}
        >
          <span class='contrast-label'>{this.activeConfig.label}</span>
          <span class='contrast-switch'>
            <i class='icon-monitor icon-switch' />
          </span>
        </div>
        <div class='contrast-right'>
          {this.active === 'contrast' ? (
            <ContrastView
              timeStrShow={this.timeStrShow}
              value={this.contrastDates}
              onChange={this.handleContrastDatesChange}
            />
          ) : (
            <GroupByView
              groupBy={this.groupBy}
              limit={this.limit}
              method={this.method}
              metricCalType={this.metricCalType}
              searchList={this.searchList}
              supportedCalculationTypes={this.supportedCalculationTypes}
              supportedMethods={this.supportedMethods}
              onChange={this.handleGroupByChange}
              onLimitChange={this.handleChangeLimit}
              onMethodChange={this.handleChangeMethod}
              onMetricCalType={this.handleChangeMetricCalType}
            />
          )}
        </div>
      </div>
    );
  }
}
