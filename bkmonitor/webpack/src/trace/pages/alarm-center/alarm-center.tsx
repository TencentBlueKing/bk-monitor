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
import { defineComponent, useTemplateRef } from 'vue';
import { shallowRef } from 'vue';

import TraceExploreLayout from '../trace-explore/components/trace-explore-layout';
import AlarmAnalysis from './components/alarm-analysis';
import AlarmCenterHeader from './components/alarm-center-header';
import AlarmRetrievalFilter from './components/alarm-retrieval-filter/alarm-retrieval-filter';
import QuickFiltering from './components/quick-filtering';

import './alarm-center.scss';
export default defineComponent({
  name: 'AlarmCenter',
  setup() {
    const isCollapsed = shallowRef(false);
    const layoutRef = useTemplateRef<InstanceType<typeof TraceExploreLayout>>('layoutRef');
    const groupList = shallowRef([
      {
        id: 'test',
        name: '测试',
        type: 'icon',
        children: [
          {
            id: 'test1',
            name: '测试1',
            icon: 'icon-gaojingfenpai',
            count: 10,
            children: [
              { id: 'test2', name: '测试2' },
              { id: 'test4', name: '测试4' },
            ],
          },
          { id: 'test3', name: '测试3', count: 5 },
        ],
      },
      {
        id: 'aa',
        name: 'aa',
        type: 'rect',
        children: [{ id: 'bb', name: 'bb', color: '#E71818', count: 8 }],
      },
    ]);

    const handleCloseFilter = () => {
      layoutRef.value?.handleClickShrink(false);
    };

    return {
      isCollapsed,
      groupList,
      handleCloseFilter,
    };
  },
  render() {
    return (
      <div class='alarm-center'>
        <AlarmCenterHeader class='alarm-center-header' />
        <AlarmRetrievalFilter class='alarm-center-filters' />
        <div class='alarm-center-content'>
          <TraceExploreLayout
            ref='layoutRef'
            v-slots={{
              aside: () => {
                return (
                  <div class='quick-filtering'>
                    <QuickFiltering
                      groupList={this.groupList}
                      onClose={this.handleCloseFilter}
                    />
                  </div>
                );
              },
              default: () => {
                return (
                  <div class='filter-content'>
                    <div class='alarm-analysis'>
                      <AlarmAnalysis />
                    </div>
                  </div>
                );
              },
            }}
            initialDivide={208}
            maxWidth={800}
            minWidth={160}
          />
        </div>
      </div>
    );
  },
});
