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
import { defineComponent, onMounted, ref } from 'vue';

import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import { useTraceExploreStore } from '../../store/modules/explore';
import DimensionFilterPanel from './components/dimension-filter-panel';
import TraceExploreLayout from './components/trace-explore-layout';
import TraceExploreView from './trace-explore-view/trace-explore-view';

import './trace-explore.scss';
export default defineComponent({
  name: 'TraceExplore',
  props: {},
  setup() {
    const traceExploreLayoutRef = ref<InstanceType<typeof traceExploreLayoutRef>>();
    const store = useTraceExploreStore();

    console.log(store);

    const where = ref([]);
    const fieldList = ref([]);
    const loading = ref(false);
    const queryString = ref('');

    function handleCloseDimensionPanel() {}

    function handleConditionChange() {}

    function handleShowEventSourcePopover() {}

    onMounted(() => {
      setTimeout(() => {
        const data = [
          {
            name: 'time',
            alias: '数据上报时间（time）',
            type: 'date',
            is_option_enabled: true,
          },
          {
            name: 'event_name',
            alias: '事件名（event_name）',
            type: 'keyword',
            is_option_enabled: true,
          },
          {
            name: 'type',
            alias: '事件类型（type）',
            type: 'keyword',
            is_option_enabled: true,
          },
          {
            name: 'a.c',
            alias: 'a.c',
            type: 'keyword',
            is_option_enabled: true,
          },
          {
            name: 'a.b',
            alias: 'a.b',
            type: 'keyword',
            is_option_enabled: true,
          },
          {
            name: 'a.d.e',
            alias: 'a.d.e',
            type: 'keyword',
            is_option_enabled: true,
          },
          {
            name: 'a.d.f',
            alias: 'a.d.f',
            type: 'keyword',
            is_option_enabled: true,
          },
        ];

        fieldList.value = data;
      }, 300);
    });

    return {
      traceExploreLayoutRef,
      where,
      fieldList,
      loading,
      queryString,
      handleCloseDimensionPanel,
      handleConditionChange,
      handleShowEventSourcePopover,
    };
  },
  render() {
    return (
      <div class='trace-explore'>
        <div class='favorite-panel' />
        <div class='main-panel'>
          <div class='header-panel' />
          <div class='trace-explore-content'>
            {this.loading ? <div class='skeleton-element filter-skeleton' /> : <RetrievalFilter />}
            <TraceExploreLayout
              ref='traceExploreLayoutRef'
              class='content-container'
            >
              {{
                aside: () => (
                  <div class='dimension-filter-panel'>
                    <DimensionFilterPanel
                      condition={this.where}
                      list={this.fieldList}
                      listLoading={this.loading}
                      queryString={this.queryString}
                      onClose={this.handleCloseDimensionPanel}
                      onConditionChange={this.handleConditionChange}
                      onShowEventSourcePopover={this.handleShowEventSourcePopover}
                    />
                  </div>
                ),
                default: () => (
                  <div class='result-content-panel'>
                    <TraceExploreView />
                  </div>
                ),
              }}
            </TraceExploreLayout>
          </div>
        </div>
      </div>
    );
  },
});
