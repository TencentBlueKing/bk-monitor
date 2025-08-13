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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone } from 'monitor-common/utils/utils';

import StrategyMetricWrap from './strategy-metric-wrap';

interface IEventFn {
  onShowChange: Function;
}

interface IStrategyMetricEvent {
  isShow: boolean;
  scenarioList: any;
}

@Component({
  name: 'StrategyMetricEvent',
})
export default class StrategyMetricEvent extends tsc<IStrategyMetricEvent, IEventFn> {
  @Prop({ default: false, type: Boolean }) isShow: boolean;
  @Prop({ default: () => [], type: Array }) scenarioList: any;

  // 获取侧栏数据
  get getLeftList() {
    const list = deepClone(this.scenarioList);
    const res = list.reduce((total, cur) => {
      const child = cur.children || [];
      total = total.concat(child);
      return total;
    }, []);
    const map = {
      application_check: 10,
    };
    res.forEach(item => {
      this.$set(item, 'count', map[item.id] || 0);
    });
    return res;
  }

  // tab数据
  get getTabList() {
    return [
      { id: 1, name: '系统事件', count: 0 },
      { id: 2, name: '自定义事件', count: 0 },
    ];
  }

  @Emit('show-change')
  showChange(v) {
    return v;
  }

  test() {}

  render() {
    return (
      <div>
        <StrategyMetricWrap
          isShow={this.isShow}
          left-select={this.test}
          leftList={this.getLeftList}
          tabList={this.getTabList}
          onShowChange={this.test}
        >
          test
        </StrategyMetricWrap>
      </div>
    );
  }
}
