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
  <dynamic-topo
    ref="dynamicTopo"
    :get-default-data="getDefaultData"
    :get-search-table-data="getSearchTableData"
    :get-search-tree-data="getSearchTreeData"
    :result-width="resultWidth"
    :search-data-options="searchDataOptions"
    :tree-data-options="treeDataOptions"
    :limit="limit"
    :transform-to-children="false"
    :show-count="false"
    :dynamic-table-config="staticTableConfig"
    :get-default-selections="getDefaultSelections"
    :lazy-method="lazyMethod"
    :lazy-disabled="lazyDisabled"
    :default-expand-level="defaultExpandLevel"
    :expand-on-click="expandOnClick"
    :left-panel-width="leftPanelWidth"
    :tree-height="treeHeight"
    @check-change="handleTableCheckChange"
    @search-selection-change="handleSearchSelectionChange"
  />
</template>
<script lang="ts">
import { Component, Emit, Prop, Ref, Vue } from 'vue-property-decorator';

import DynamicTopo from './dynamic-topo.vue';

import type { ISearchDataOption, ITableCheckData, ITableConfig, SearchDataFuncType } from '../types/selector-type';

@Component({ name: 'static-topo', components: { DynamicTopo } })
export default class StaticTopo extends Vue {
  // 获取组件初始化数据
  @Prop({ type: Function, required: true }) private readonly getDefaultData!: Function;
  // 表格搜索数据
  @Prop({ type: Function, required: true }) private readonly getSearchTableData!: SearchDataFuncType;
  // 树搜索数据
  @Prop({ type: Function }) private readonly getSearchTreeData!: Function;
  @Prop({ type: Function }) private readonly getDefaultSelections!: Function;
  // 表格字段配置
  @Prop({ default: () => [], type: Array }) private readonly staticTableConfig!: ITableConfig[];
  // 每页数
  @Prop({ default: 20, type: Number }) private readonly limit!: number;
  // 搜索数据配置
  @Prop({ default: () => ({}), type: Object }) private readonly searchDataOptions!: ISearchDataOption;
  // 节点数据配置
  @Prop({ default: () => ({}), type: Object }) private readonly treeDataOptions!: any;
  // tree搜索结果面板默认宽度
  @Prop({ default: 'auto', type: [Number, String] }) private readonly resultWidth!: number | string;
  // 树懒加载方法
  @Prop({ type: Function }) private readonly lazyMethod!: Function;
  @Prop({ type: [Function, Boolean] }) private readonly lazyDisabled!: Function;
  @Prop({ default: 2, type: Number }) private readonly defaultExpandLevel!: number;
  @Prop({ default: false, type: Boolean }) private readonly expandOnClick!: boolean;
  @Prop({ default: 240, type: [Number, String] }) private readonly leftPanelWidth!: number | string;
  @Prop({ default: 300, type: [Number, String] }) private readonly treeHeight!: number | string;

  @Ref('dynamicTopo') private readonly dynamicTopoRef!: DynamicTopo;

  @Emit('check-change')
  private handleTableCheckChange(data: ITableCheckData) {
    return data;
  }
  @Emit('search-selection-change')
  private handleSearchSelectionChange(selections: any[]) {
    return selections;
  }

  public handleGetDefaultSelections() {
    this.dynamicTopoRef?.handleGetDefaultSelections();
  }
}
</script>
