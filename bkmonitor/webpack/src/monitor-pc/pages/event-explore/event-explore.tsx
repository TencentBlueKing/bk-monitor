/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import EventExploreView from './components/event-explore-view';
import EventRetrievalHeader from './components/event-retrieval-header';
import EventRetrievalLayout from './components/event-retrieval-layout';

import './event-explore.scss';
Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);

@Component
export default class EventRetrievalNew extends tsc<object> {
  /** 请求接口公共请求参数 */
  get commonParams() {
    return {
      query_configs: [
        {
          data_source_label: 'bk_apm',
          data_type_label: 'event',
          table: 'k8s_event',
          filter_dict: {},
          where: [
            {
              condition: 'and',
              key: 'kind',
              method: 'eq',
              value: ['Job'],
            },
          ],
          query_string: '*',
          group_by: ['type'],
        },
      ],
      start_time: 1739499301,
      end_time: 1739502901,
    };
  }

  render() {
    return (
      <div class='event-explore'>
        <div class='left-favorite-panel' />
        <div class='right-main-panel'>
          <EventRetrievalHeader />
          <div class='event-retrieval-content'>
            <RetrievalFilter />
            <EventRetrievalLayout class='content-container'>
              <div
                class='dimension-filter-panel'
                slot='aside'
              />
              <div class='result-content-panel'>
                <EventExploreView commonParams={this.commonParams} />
              </div>
            </EventRetrievalLayout>
          </div>
        </div>
      </div>
    );
  }
}
