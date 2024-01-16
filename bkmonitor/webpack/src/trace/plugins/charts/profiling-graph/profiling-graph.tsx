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

import { defineComponent, inject, PropType, Ref, ref, watch } from 'vue';
import { Exception, Loading } from 'bkui-vue';
import { debounce } from 'throttle-debounce';

// import { query } from '../../../../monitor-api/modules/apm_profile';
import { BaseDataType, ProfilingTableItem, ViewModeType } from '../../../../monitor-ui/chart-plugins/typings';
// import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { ToolsFormData } from '../../../pages/profiling/typings';
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
      default: () => ({})
    }
  },
  setup(props) {
    const toolsFormData = inject<Ref<ToolsFormData>>('toolsFormData');

    const empty = ref(true);
    // 当前视图模式
    const activeMode = ref<ViewModeType>(ViewModeType.Combine);
    const textDirection = ref<DirectionType>('ltr');
    const isLoading = ref(false);
    const tableData = ref<ProfilingTableItem[]>([]);
    const flameData = ref<BaseDataType>({
      name: '',
      children: undefined,
      id: ''
    });
    const unit = ref('');
    const highlightId = ref(-1);
    const filterKeyword = ref('');

    watch(
      [() => props.queryParams],
      debounce(16, async () => handleQuery()),
      {
        immediate: true,
        deep: true
      }
    );
    watch(
      () => toolsFormData.value.timeRange,
      () => {
        handleQuery();
      },
      {
        deep: true
      }
    );

    const handleQuery = async () => {
      try {
        isLoading.value = true;
        highlightId.value = -1;
        // const { queryParams } = props;
        // const [start, end] = handleTransformToTimestamp(toolsFormData.value.timeRange);
        // const params = Object.assign({}, queryParams, {
        //   start,
        //   end
        // });
        // const data = await query(params).catch(() => false);
        const data = PROFILING_QUERY_DATA;
        if (data) {
          unit.value = data.unit || '';
          tableData.value = data.table_data || [];
          flameData.value = data.flame_data;
          empty.value = false;
        } else {
          empty.value = true;
        }
        isLoading.value = false;
      } catch (e) {
        console.error(e);
        isLoading.value = false;
        empty.value = true;
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
      empty,
      tableData,
      flameData,
      unit,
      isLoading,
      activeMode,
      textDirection,
      handleModeChange,
      handleTextDirectionChange,
      highlightId,
      filterKeyword
    };
  },
  render() {
    return (
      <Loading
        loading={this.isLoading}
        class='profiling-graph'
      >
        <ChartTitle
          activeMode={this.activeMode}
          textDirection={this.textDirection}
          onModeChange={this.handleModeChange}
          onTextDirectionChange={this.handleTextDirectionChange}
          onKeywordChange={val => (this.filterKeyword = val)}
        />
        {this.empty ? (
          <Exception
            type='empty'
            description={this.$t('暂无数据')}
          />
        ) : (
          <div class='profiling-graph-content'>
            {[ViewModeType.Combine, ViewModeType.Table].includes(this.activeMode) && (
              <TableGraph
                data={this.tableData}
                unit={this.unit}
                textDirection={this.textDirection}
                highlightId={this.highlightId}
                filterKeyword={this.filterKeyword}
                onUpdateHighlightId={id => (this.highlightId = id)}
              />
            )}
            {[ViewModeType.Combine, ViewModeType.Flame].includes(this.activeMode) && (
              <FrameGraph
                textDirection={this.textDirection}
                showGraphTools={false}
                data={this.flameData}
                highlightId={this.highlightId}
                filterKeywords={[this.filterKeyword]}
                onUpdateHighlightId={id => (this.highlightId = id)}
              />
            )}
          </div>
        )}
      </Loading>
    );
  }
});
