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
import { defineComponent, onMounted, shallowRef } from 'vue';

import { listApplicationInfo } from 'monitor-api/modules/apm_meta';

import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import { useTraceExploreStore } from '../../store/modules/explore';
import DimensionFilterPanel from './components/dimension-filter-panel';
import TraceExploreHeader from './components/trace-explore-header';
import TraceExploreLayout from './components/trace-explore-layout';
import TraceExploreView from './components/trace-explore-view/trace-explore-view';

import type { IApplicationItem } from './typing';

import './trace-explore.scss';
export default defineComponent({
  name: 'TraceExplore',
  props: {},
  setup() {
    const traceExploreLayoutRef = shallowRef<InstanceType<typeof traceExploreLayoutRef>>();
    const store = useTraceExploreStore();

    const applicationList = shallowRef<IApplicationItem[]>([]);
    const isShowFavorite = shallowRef(true);

    function handleFavoriteShowChange(isShow: boolean) {
      isShowFavorite.value = isShow;
    }

    console.log(store);

    const where = shallowRef([]);
    const fieldList = shallowRef([]);
    const loading = shallowRef(false);
    const queryString = shallowRef('');

    async function getApplicationList() {
      const data = await listApplicationInfo().catch(() => []);
      applicationList.value = data;
    }

    function handleCloseDimensionPanel() {
      traceExploreLayoutRef.value.handleClickShrink(false);
    }

    function handleConditionChange() {}

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

      getApplicationList();
    });

    return {
      traceExploreLayoutRef,
      applicationList,
      isShowFavorite,
      where,
      fieldList,
      loading,
      queryString,
      handleFavoriteShowChange,
      handleCloseDimensionPanel,
      handleConditionChange,
    };
  },
  render() {
    return (
      <div class='trace-explore'>
        <div class='favorite-panel' />
        <div class='main-panel'>
          <div class='header-panel'>
            <TraceExploreHeader
              isShowFavorite={this.isShowFavorite}
              list={this.applicationList}
              onFavoriteShowChange={this.handleFavoriteShowChange}
            />
          </div>
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
