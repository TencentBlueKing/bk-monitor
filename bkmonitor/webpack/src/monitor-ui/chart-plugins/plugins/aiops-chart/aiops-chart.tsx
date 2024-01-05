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
import { Component, Emit, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import echarts from 'echarts';

import loadingIcon from '../../icons/spinner.svg';
import { PanelModel } from '../../typings';
import LineChart from '../time-series/time-series';

import './aiops-chart.scss';

interface IProps {
  panels: PanelModel[];
  onDimensionsOfSeries?: (dimensions: string[]) => string[];
  clearErrorMsg?: () => void;
  errorMsgFn?: (mgs: string) => void;
}
interface IDataZoomTimeRange {
  timeRange: any[];
}
@Component
export default class AiopsChart extends tsc<IProps> {
  /** aiops 联动时间 */
  @InjectReactive('dataZoomTimeRange') dataZoomTimeRange: IDataZoomTimeRange;
  @Prop({ required: true, type: Array }) panels: PanelModel[];
  @Prop({ default: () => {}, type: Function }) clearErrorMsg: () => void;
  @Prop({ default: () => {}, type: Function }) errorMsgFn: (mgs: string) => void;

  loadingList: [boolean, boolean] = [false, false];
  insideList: [boolean, boolean] = [false, false];

  customTimeRange = null;

  mounted() {
    this.handleConnectEchart();
  }

  handleConnectEchart() {
    // 等待所以子视图实例创建完进行视图示例的关联 暂定5000ms 后期进行精细化配置
    setTimeout(() => {
      echarts.connect(this.panels?.[0]?.dashboardId);
    }, 5000);
  }
  handleChangeLoading(val: boolean, index: number) {
    this.$set(this.loadingList, index, val);
  }
  handleInside(val: boolean, index) {
    this.$set(this.insideList, index, val);
  }
  // this.zoomTimeRangeFlag = false;
  handleDataZoom(startTime, endTime) {
    // this.zoomTimeRangeFlag = true;
    this.customTimeRange = [startTime, endTime];
    if (this.dataZoomTimeRange?.timeRange) {
      this.dataZoomTimeRange.timeRange = startTime && endTime ? [startTime, endTime] : [];
    }
  }
  @Watch('dataZoomTimeRange.timeRange')
  handleChangeTimeRang(val) {
    this.customTimeRange = val;
  }
  handleDblClick() {
    this.customTimeRange = null;
  }
  @Emit('dimensionsOfSeries')
  handleDimensionsOfSeries(dimensions: string[]) {
    return dimensions;
  }
  render() {
    return (
      <div class='aiops-chart-wrap'>
        {this.panels.map((panel, index) => (
          <div
            class='aiops-chart-item'
            onMouseenter={() => this.handleInside(true, index)}
            onMouseleave={() => this.handleInside(false, index)}
          >
            {this.loadingList[index] && (
              <img
                class='loading-icon'
                src={loadingIcon}
                alt=''
              ></img>
            )}
            <LineChart
              panel={panel}
              customTimeRange={this.customTimeRange}
              customMenuList={['screenshot', 'explore', 'set', 'area']}
              onLoading={val => this.handleChangeLoading(val, index)}
              onErrorMsg={this.errorMsgFn}
              clearErrorMsg={this.clearErrorMsg}
              showHeaderMoreTool={this.insideList[index]}
              onDataZoom={this.handleDataZoom}
              onDblClick={this.handleDblClick}
              onDimensionsOfSeries={this.handleDimensionsOfSeries}
            />
          </div>
        ))}
      </div>
    );
  }
}
