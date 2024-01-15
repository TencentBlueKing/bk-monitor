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

import { defineComponent, PropType, ref, watch } from 'vue';
// import { profileQuery } from '@api/modules/apm_profile';
import { Loading } from 'bkui-vue';
import { debounce } from 'throttle-debounce';

import { BaseDataType, ProfilingTableItem, ViewModeType } from '../../../../monitor-ui/chart-plugins/typings';
import { DirectionType, IQueryParams } from '../../../typings';

import ChartTitle from './chart-title/chart-title';
import FrameGraph from './flame-graph/flame-graph';
import TableGraph from './table-graph/table-graph';
import { PROFILING_QUERY_DATA } from './mock';

import './profiling-graph.scss';

export default defineComponent({
  name: 'ProfilingGraph',
  props: {
    queryParams: {
      type: Object as PropType<IQueryParams>,
      default: () => {}
    }
  },
  setup(props) {
    // 当前视图模式
    const activeMode = ref<ViewModeType>(ViewModeType.Combine);
    const textDirection = ref<DirectionType>('ltr');
    const isLoaing = ref(false);
    const tableData = ref<ProfilingTableItem[]>([]);
    const flameData = ref<BaseDataType>({
      name: '',
      children: undefined,
      id: ''
    });
    const unit = ref('');

    watch(
      [() => props.queryParams],
      debounce(16, async () => handleQuery()),
      {
        immediate: true,
        deep: true
      }
    );

    const handleQuery = async () => {
      try {
        // isLoaing.value = true;
        // const { queryParams } = props;
        // const params = Object.assign({}, queryParams);
        // const data = await profileQuery(params).catch(() => false);
        const data = PROFILING_QUERY_DATA;
        if (data) {
          unit.value = data.unit || '';
          tableData.value = data.table_data || [];
          flameData.value = data.flame_data as any;
        }
      } catch (e) {
        console.error(e);
        // isLoaing.value = false;
      }
    };
    /** 切换视图模式 */
    const handleModeChange = (val: ViewModeType) => {
      activeMode.value = val;
    };
    const handleTextDirectionChange = (val: DirectionType) => {
      textDirection.value = val;
    };

    return {
      tableData,
      flameData,
      unit,
      isLoaing,
      activeMode,
      textDirection,
      handleModeChange,
      handleTextDirectionChange
    };
  },
  render() {
    return (
      <Loading
        loading={this.isLoaing}
        class='profiling-graph'
      >
        <ChartTitle
          activeMode={this.activeMode}
          textDirection={this.textDirection}
          onModeChange={this.handleModeChange}
          onTextDirectionChange={this.handleTextDirectionChange}
        />
        <div class='profiling-graph-content'>
          {[ViewModeType.Combine, ViewModeType.Table].includes(this.activeMode) && (
            <TableGraph
              data={this.tableData}
              unit={this.unit}
              textDirection={this.textDirection}
            />
          )}
          {[ViewModeType.Combine, ViewModeType.Flame].includes(this.activeMode) && (
            <FrameGraph
              data={this.flameData}
              appName={'bkmonitor_production'}
              profileId={'3d0d77e0669cdb72'}
              start={1703747947993154}
              end={1703747948022443}
              bizId={2}
              showGraphTools={false}
              textDirection={this.textDirection}
            />
          )}
        </div>
      </Loading>
    );
  }
});
