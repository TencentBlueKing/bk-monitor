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
  <service-template
    ref="service"
    :get-default-data="getDefaultData"
    :get-search-table-data="getSearchTableData"
    :get-default-selections="getDefaultSelections"
    :template-table-config="clusterTableConfig"
    :template-options="clusterOptions"
    :service-template-placeholder="clusterTemplatePlaceholder"
    :left-panel-width="leftPanelWidth"
    @check-change="handleCheckChange"
  />
</template>
<script lang="ts">
import { Component, Emit, Prop, Ref, Vue } from 'vue-property-decorator';

import ServiceTemplate from './service-template.vue';

import type { ITableCheckData, ITableConfig, ITemplateDataOptions, SearchDataFuncType } from '../types/selector-type';

// 集群
@Component({
  name: 'cluster',
  components: {
    ServiceTemplate,
  },
})
export default class Cluster extends Vue {
  // 获取组件初始化数据
  @Prop({ type: Function, required: true }) private readonly getDefaultData!: Function;
  // 表格搜索数据
  @Prop({ type: Function, required: true }) private readonly getSearchTableData!: SearchDataFuncType;
  @Prop({ type: Function }) private readonly getDefaultSelections!: Function;
  @Prop({
    default: () => ({
      idKey: 'bk_inst_id',
      childrenKey: 'instances_count',
      labelKey: 'bk_inst_name',
    }),
    type: Object,
  })
  private readonly clusterOptions!: ITemplateDataOptions;
  // 表格字段配置
  @Prop({ default: () => [], type: Array }) private readonly clusterTableConfig!: ITableConfig[];
  @Prop({ default: '', type: String }) private readonly clusterTemplatePlaceholder!: string;
  @Prop({ default: 240, type: [Number, String] }) private readonly leftPanelWidth!: number | string;

  @Ref('service') private readonly serviceRef!: ServiceTemplate;

  @Emit('check-change')
  private handleCheckChange(data: ITableCheckData) {
    return data;
  }

  public handleGetDefaultSelections() {
    this.serviceRef?.handleGetDefaultSelections();
  }
}
</script>
