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

import MyFavorites from './components/my-favorites';
import RecentAlarmEvents from './components/recent-alarm-events';
// import HomeAlarmChart from './components/home-alarm-chart';
import HomeSelect from './components/home-select';
import { testData } from './testData';

import './new-home.scss';

@Component({
  name: 'NewHome',
})
export default class NewHome extends tsc<object> {
  data = [
    {
      name: 'Monitor】componentNodeExporterRestart ',
      bk_biz_name: '蓝鲸',
    },
    {
      name: '容器实战(BCS-K8S-25973)',
      bk_biz_name: '王者荣耀',
    },
    {
      name: '1732613611426664637',
      bk_biz_name: '蓝鲸',
      type: 'strategy',
    },
    {
      name: '99b658b5392b3fbc9fd1a588dc965711',
      bk_biz_name: '王者荣耀',
      type: 'strategy',
    },
    {
      name: '1.1.2.1.44',
      bk_biz_name: '王者荣耀',
      type: 'host',
      sub: '（demo/demo_k8s/k8s)',
    },
  ];
  config = {
    name: '全部策略',
    tips: [
      {
        status: 'deleted',
        label: 'Monitor】componentDaemonsetRestart',
      },
      {
        status: 'stop',
        label: 'Monitor】componentDaemonsetRestart',
      },
    ],
  };
  handleGetAlertDateHistogram() {
    return testData;
  }
  render() {
    return (
      <div class='monitor-new-home'>
        <div class='new-home-bg' />
        <div class='new-home-content'>
          <HomeSelect
            historyList={this.data}
            searchList={testData}
          />
          <div class='new-home-tool'>
            <MyFavorites />
          </div>
          <div class='new-home-alarm-list'>
            <RecentAlarmEvents />
          </div>
        </div>
      </div>
    );
  }
}
