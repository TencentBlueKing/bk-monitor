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
    ref="leftWrapper"
    v-bkloading="{ isLoading }"
    class="dynamic-topo"
  >
    <div
      class="dynamic-topo-left"
      :style="{ width: isNaN(leftPanelWidth) ? leftPanelWidth : `${leftPanelWidth}px` }"
    >
      <topo-search
        v-model="treeKeyword"
        :search-method="searchTreeMethod"
        :placeholder="$t('搜索拓扑节点')"
        :result-width="resultWidth"
        :options="searchDataOptions"
        :default-selection-ids="defaultSelectionIds"
        @show="handleSearchPanelShow"
        @check-change="handleCheckChange"
        @select-search="handleSelectSearch"
      />
      <topo-tree
        v-if="nodes.length"
        ref="tree"
        class="topo-tree"
        :default-checked-nodes="defaultCheckedNodes"
        :options="treeDataOptions"
        :nodes="nodes"
        :show-count="showCount"
        :lazy-method="lazyMethod"
        :lazy-disabled="lazyDisabled"
        :default-expand-level="defaultExpandLevel"
        :expand-on-click="expandOnClick"
        :height="treeHeight"
        @select-change="handleSelectChange"
      />
    </div>
    <div class="dynamic-topo-right ml10">
      <ip-list-table
        ref="table"
        :get-search-table-data="getTableData"
        :ip-list-table-config="dynamicTableConfig"
        :ip-list-placeholder="dynamicTablePlaceholder"
        :get-default-selections="getDefaultSelections"
        :disabled-loading="isLoading"
        :empty-text="emptyText"
        @check-change="handleTableCheckChange"
      />
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import { resize } from '../common/observer-directive';
import TopoSearch from '../components/topo-search.vue';
import TopoTree from '../components/topo-tree.vue';
import IpListTable from './ip-list.vue';

import type {
  IipListParams,
  ISearchData,
  ISearchDataOption,
  ITableCheckData,
  ITableConfig,
  ITreeNode,
  SearchDataFuncType,
} from '../types/selector-type';
import type { TranslateResult } from 'vue-i18n';

@Component({
  name: 'dynamic-topo',
  components: {
    TopoTree,
    TopoSearch,
    IpListTable,
  },
  directives: {
    resize,
  },
})
export default class DynamicTopo extends Vue {
  // 获取组件初始化数据
  @Prop({ type: Function, required: true }) private readonly getDefaultData!: Function;
  // 表格搜索数据
  @Prop({ type: Function, required: true }) private readonly getSearchTableData!: SearchDataFuncType;
  // 树搜索数据（为空时使用默认搜索方法）
  @Prop({ type: Function }) private readonly getSearchTreeData!: Function;
  // 表格行是否勾选回调
  @Prop({ type: Function }) private readonly getDefaultSelections!: Function;
  // 搜索面板item是否勾选回调
  @Prop({ type: Function }) private readonly getSearchResultSelections!: Function;
  // 树懒加载方法
  @Prop({ type: Function }) private readonly lazyMethod!: Function;
  @Prop({ type: [Function, Boolean] }) private readonly lazyDisabled!: Function;
  @Prop({ default: false, type: Boolean }) private readonly expandOnClick!: boolean;

  // tree搜索结果面板默认宽度
  @Prop({ default: 'auto', type: [Number, String] }) private readonly resultWidth!: number | string;
  @Prop({ default: 300, type: [Number, String] }) private readonly treeHeight!: number | string;
  // 搜索数据配置
  @Prop({ default: () => ({}), type: Object }) private readonly searchDataOptions!: ISearchDataOption;
  // 节点数据配置
  @Prop({ default: () => ({}), type: Object }) private readonly treeDataOptions!: any;
  // 每页数
  @Prop({ default: 20, type: Number }) private readonly limit!: number;
  // 表格字段配置
  @Prop({ default: () => [], type: Array }) private readonly dynamicTableConfig!: ITableConfig[];
  @Prop({ default: '', type: String }) private readonly dynamicTablePlaceholder!: string;
  // 选中父节点时获取让子节点选中
  @Prop({ default: true, type: Boolean }) private readonly transformToChildren!: boolean;
  // 默认checked节点
  @Prop({ default: () => [], type: Array }) private readonly defaultCheckedNodes!: string | string[];
  @Prop({ default: false, type: Boolean }) private readonly showCount!: boolean;
  @Prop({ default: 2, type: Number }) private readonly defaultExpandLevel!: number;
  @Prop({ default: 240, type: [Number, String] }) private readonly leftPanelWidth!: number | string;

  @Ref('table') private readonly tableRef!: IpListTable;
  @Ref('leftWrapper') private readonly leftWrapperRef!: HTMLElement;
  @Ref('tree') private readonly treeRef!: TopoTree;

  private isLoading = false;
  private treeKeyword = '';
  private emptyText: TranslateResult = window.i18n.t('暂无数据');

  // 数据相关属性
  private nodes: ITreeNode[] = [];
  private selections: any[] = [];
  private parentNode: ITreeNode | null = null;
  private defaultSelectionIds: (number | string)[] = [];
  private searchPanelData: any[] = [];

  @Watch('defaultCheckedNodes')
  private handleDefaultCheckedNodesChange(data: string | string[]) {
    this.treeRef?.handleSetChecked(data);
  }

  @Watch('selections')
  private handleSelectionChange() {
    // this.emptyText = !!this.selections.length ? this.$t('查无数据') : this.$t('选择');
  }

  private created() {
    // this.emptyText = this.$t('选择');
    this.handleGetDefaultData();
  }

  private async handleGetDefaultData() {
    try {
      this.isLoading = true;
      const data = await this.getDefaultData();
      this.nodes = data || [];
    } catch (err) {
      console.log(err);
    } finally {
      this.isLoading = false;
    }
  }

  // 搜索结果勾选事件
  @Emit('search-selection-change')
  private handleCheckChange(data: ITableCheckData) {
    setTimeout(() => {
      this.tableRef.handleGetDefaultSelections();
    }, 50);
    return data;
    // this.selections = selections
    // this.tableRef.handleGetDefaultData('selection-change')
  }

  // 树select事件
  private handleSelectChange(treeNode: ITreeNode) {
    if (this.transformToChildren) {
      const { childrenKey = 'children' } = this.treeDataOptions;
      this.selections = treeNode.data[childrenKey]?.length
        ? treeNode.data[childrenKey]
        : treeNode.children.map(node => node.data);
      this.parentNode = treeNode;
    } else {
      this.selections = [treeNode.data];
      this.parentNode = treeNode.parent || null;
    }

    this.tableRef.handleGetDefaultData('selection-change');
  }

  private handleSearchPanelShow() {
    if (this.getSearchResultSelections) {
      const { idKey = 'id' } = this.searchDataOptions;
      this.defaultSelectionIds = this.searchPanelData.reduce<(number | string)[]>((pre, next) => {
        !!this.getSearchResultSelections(next) && pre.push(next[idKey]);
        return pre;
      }, []);
    }
  }

  // 树搜索
  private async searchTreeMethod(treeKeyword: string) {
    try {
      if (this.getSearchTreeData) {
        this.searchPanelData = await this.getSearchTreeData({ treeKeyword });
      }
      this.searchPanelData = this.defaultTreeSearchMethod(this.nodes, '', treeKeyword);
      this.handleSearchPanelShow();
      return this.searchPanelData;
    } catch (err) {
      console.log(err);
      return {
        total: 0,
        data: [],
      };
    }
  }
  // 树默认搜索方法(结果是打平的数据)
  private defaultTreeSearchMethod(nodes: any[], parent: string, treeKeyword: string) {
    const { nameKey = 'name', childrenKey = 'children' } = this.treeDataOptions;
    const { pathKey = 'node_path' } = this.searchDataOptions;
    return nodes.reduce<any[]>((pre, next) => {
      if (next[nameKey].includes(treeKeyword)) {
        pre.push(next);
      }
      if (next[childrenKey]?.length) {
        pre.push(...this.defaultTreeSearchMethod(next[childrenKey], next[nameKey], treeKeyword));
      }
      if (!next[pathKey]) {
        next[pathKey] = parent ? `${parent} / ${next[nameKey]}` : next[nameKey];
      }
      return pre;
    }, []);
  }

  private async getTableData(params: IipListParams, type?: string) {
    try {
      const reqParams = {
        selections: this.selections,
        parentNode: this.parentNode,
        ...params,
      };
      return await this.getSearchTableData(reqParams, type);
    } catch (err) {
      console.log(err);
      return {
        total: 0,
        data: [],
      };
    }
  }

  @Emit('check-change')
  private handleTableCheckChange(data: ITableCheckData) {
    return data;
  }

  public handleGetDefaultSelections() {
    this.tableRef?.handleGetDefaultSelections();
  }

  /* 选中搜索结果 */

  handleSelectSearch(item: ISearchData) {
    this.treeRef?.handleSetSelected(item.id as any, true);
  }
}
</script>
<style lang="scss" scoped>
.dynamic-topo {
  display: flex;
  color: #63656e;

  &-left {
    display: flex;
    flex-direction: column;
    // flex-basis: 240px;
    .topo-tree {
      margin: 12px 0;
      overflow: auto;
    }
  }

  &-right {
    flex: 1;
    // border-left: 1px solid #dcdee5;
    padding-left: 10px;
    overflow: auto;
  }
}
</style>
