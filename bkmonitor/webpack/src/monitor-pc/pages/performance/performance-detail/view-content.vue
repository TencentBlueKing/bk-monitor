<!--
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
-->
<template>
  <div
    v-bkloading="{ isLoading: loading }"
    class="view-content"
  >
    <keep-alive>
      <dashboard-panels
        v-if="type === 'host'"
        :groups-data="groupsData"
        :variable-data="variableData"
        :compare-value="compareValue"
        :chart-type="chartType"
        :chart-option="chartOption"
        :keyword="keyword"
      />
      <process-content
        v-else
        :groups-data="groupsData"
        :variable-data="variableData"
        :compare-value="compareValue"
        :chart-type="chartType"
        :chart-option="chartOption"
        :keyword="keyword"
        @process-change="handleProcessChange"
      />
    </keep-alive>
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Vue } from 'vue-property-decorator';

import MonitorEcharts from 'monitor-ui/monitor-echarts/monitor-echarts.vue';

import DashboardPanels from './dashboard-panels.vue';
import ProcessContent from './view-content-process.vue';

import type { ICurNode } from '../../../store/modules/performance';
import type { ChartType, IHostGroup, IQueryOption, ViewType } from '../performance-type';

@Component({
  name: 'view-content',
  components: {
    MonitorEcharts,
    ProcessContent,
    DashboardPanels,
  },
})
export default class ViewContent extends Vue {
  // 视图类型
  @Prop({ default: 'host' }) readonly type: ViewType;
  // 视图样式
  @Prop({ default: 0 }) readonly chartType: ChartType;
  @Prop({ required: true }) readonly curNode: ICurNode;
  // 分组数据
  @Prop({ default: () => [], type: Array }) readonly groupsData: IHostGroup[];
  @Prop({ default: false }) readonly loading: boolean;
  @Prop({ default: '' }) readonly keyword: string;
  @Prop({ required: true }) readonly compareValue: IQueryOption;
  // 汇聚方法（节点类型会使用）
  @Prop({ default: '', type: String }) method!: string;

  private chartOption: any = {
    annotation: {
      show: true,
      list: ['strategy'],
    },
  };
  get variableData() {
    if (this.curNode.type === 'host') {
      return {
        $bk_target_ip: this.curNode.ip,
        $bk_target_cloud_id: this.curNode.cloudId,
        $process_name: this.curNode.processId,
      };
    }
    return {
      $bk_obj_id: this.curNode.bkObjId,
      $bk_inst_id: this.curNode.bkInstId,
      $method: this.method,
      $process_name: this.curNode.processId,
    };
  }
  @Emit('process-change')
  handleProcessChange(v) {
    return v;
  }
}
</script>
<style lang="scss" scoped>
.view-content {
  width: 100%;
  height: 100%;
  padding: 16px;
  overflow: auto;
  background: #fafbfd;
}
</style>
