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
    class="service-template"
    v-bkloading="{ isLoading }"
  >
    <div
      class="service-template-left"
      :style="{ width: isNaN(leftPanelWidth) ? leftPanelWidth : `${leftPanelWidth}px` }"
    >
      <bk-input
        clearable
        right-icon="bk-icon icon-search"
        :placeholder="serviceTemplatePlaceholder"
        v-model="searchValue"
        @change="handleTemplateSearchChange"
      />
      <!-- 全选 -->
      <div
        v-if="!!searchValue"
        class="select-all"
      >
        <span
          class="btn"
          @click="handleAllSelected"
        >{{ isSelectAll ? $t('清除全选') : $t('全选') }}</span>
      </div>
      <bk-virtual-scroll
        :list="currentTemplateData"
        :item-height="32"
        class="template-list"
      >
        <template #default="{ data }">
          <li
            class="template-list-item"
            :class="{ active: selectionIds.includes(data[templateOptions.idKey]) }"
            @click="handleTemplateClick(data)"
          >
            <div class="item-name">
              <bk-checkbox :checked="selectionIds.includes(data[templateOptions.idKey])" />
              <span
                class="label"
                :title="data[templateOptions.labelKey]"
              >
                {{ data[templateOptions.labelKey] }}
              </span>
            </div>
            <div class="item-count">
              <span class="count">{{ getChildrenCount(data) || 0 }}</span>
            </div>
          </li>
        </template>
      </bk-virtual-scroll>
    </div>
    <div class="service-template-right ml20">
      <ip-list-table
        ref="table"
        :get-search-table-data="getTableData"
        :ip-list-table-config="templateTableConfig"
        :show-selection-column="false"
        :disabled-loading="isLoading"
        :empty-text="emptyText"
      />
    </div>
  </div>
</template>
<script lang="ts">
import type { TranslateResult } from 'vue-i18n';
import { Component, Emit, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import { Debounce, defaultSearch } from '../common/util';
import IpSelectorTable from '../components/ip-selector-table.vue';
import type {
  ITableCheckData,
  ITableConfig,
  ITemplateDataOptions,
  IipListParams,
  SearchDataFuncType,
} from '../types/selector-type';

import IpListTable from './ip-list.vue';

// 服务模板
@Component({
  name: 'service-template',
  components: {
    IpSelectorTable,
    IpListTable,
  },
})
export default class ServiceTemplate extends Vue {
  // 获取组件初始化数据
  @Prop({ type: Function, required: true }) private readonly getDefaultData!: Function;
  // 表格搜索数据
  @Prop({ type: Function, required: true }) private readonly getSearchTableData!: SearchDataFuncType;
  @Prop({ type: Function }) private readonly getSearchTemplateData!: Function;
  @Prop({ type: Function }) private readonly getDefaultSelections!: Function;

  @Prop({ default: '', type: String }) private readonly serviceTemplatePlaceholder!: string;
  @Prop({
    default: () => ({
      idKey: 'bk_inst_id',
      childrenKey: 'instances_count',
      labelKey: 'bk_inst_name',
    }),
    type: Object,
  })
  private readonly templateOptions!: ITemplateDataOptions;
  // 表格字段配置
  @Prop({ default: () => [], type: Array }) private readonly templateTableConfig!: ITableConfig[];
  @Prop({ default: 240, type: [Number, String] }) private readonly leftPanelWidth!: number | string;

  @Ref('table') private readonly tableRef!: IpListTable;

  private searchValue = '';
  private tplData: any[] = [];
  // 默认为true是为了阻止 IpListTable 组件loading
  private isLoading = true;
  private selectionIds: (string | number)[] = [];
  private emptyText: TranslateResult = window.i18n.t('暂无数据');

  private isSelectAll = false;

  private get currentTemplateData() {
    if (this.getSearchTemplateData) {
      return this.tplData;
    }
    return defaultSearch(this.tplData, this.searchValue);
  }

  //   @Watch('selections')
  //   private handleSelectionChange() {
  //     this.tableRef.handleGetDefaultData()
  //   }
  @Watch('selectionIds')
  private handleSelectionIdsChange() {
    // this.emptyText = !!this.selectionIds.length ? this.$t('查无数据') : this.$t('选择');
  }

  private created() {
    // this.emptyText = this.$t('选择');
  }

  private mounted() {
    this.handleGetDefaultData();
  }

  private async handleGetDefaultData() {
    try {
      this.isLoading = true;
      const data = await this.getDefaultData();
      this.tplData = data || [];
      this.handleGetDefaultSelections();
      this.selectionIds.length && this.tableRef && this.tableRef.handleGetDefaultData('selection-change');
    } catch (err) {
      console.log(err);
      return [];
    } finally {
      this.isLoading = false;
    }
  }

  @Debounce(300)
  private async handleTemplateSearchChange() {
    if (this.getSearchTemplateData) {
      try {
        const data = await this.getSearchTemplateData({ searchValue: this.searchValue });
        this.tplData = data || [];
      } catch (err) {
        console.log(err);
        this.tplData = [];
      }
    }
    this.$nextTick(() => {
      this.getAllSelectedStatus();
    });
  }

  private async getTableData(params: IipListParams, type?: string) {
    try {
      const { idKey = 'bk_inst_id' } = this.templateOptions;
      const selections = this.tplData.filter(item => this.selectionIds.includes(item[idKey]));
      const reqParams = {
        selections,
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

  private handleTemplateClick(item: any) {
    const { idKey = 'bk_inst_id' } = this.templateOptions;
    const itemId = item[idKey];
    const index = this.selectionIds.findIndex(id => id === itemId);
    if (index > -1) {
      this.selectionIds.splice(index, 1);
    } else {
      this.selectionIds.push(itemId);
    }
    this.handleCheckChange();
    this.tableRef?.handleGetDefaultData('selection-change');
    this.getAllSelectedStatus();
  }

  @Emit('check-change')
  private handleCheckChange(): ITableCheckData {
    const { idKey = 'bk_inst_id' } = this.templateOptions;
    return {
      selections: this.tplData.filter(item => this.selectionIds.includes(item[idKey])),
    };
  }

  private getChildrenCount(item: any) {
    const { childrenKey = 'nodes_count' } = this.templateOptions;
    if (Array.isArray(item[childrenKey])) {
      return item[childrenKey].length;
    }
    return item[childrenKey];
  }
  // eslint-disable-next-line @typescript-eslint/member-ordering
  public handleGetDefaultSelections() {
    const { idKey = 'bk_inst_id' } = this.templateOptions;
    this.selectionIds = this.tplData.reduce((pre, next) => {
      if (this.getDefaultSelections && !!this.getDefaultSelections(next)) {
        pre.push(next[idKey]);
      }
      return pre;
    }, []);
  }
  // eslint-disable-next-line @typescript-eslint/member-ordering
  handleAllSelected() {
    /* 全选/清除全选 */
    if (!this.currentTemplateData.length) return;
    if (this.isSelectAll) {
      this.currentTemplateData.forEach(item => {
        const index = this.selectionIds.indexOf(item.bk_inst_id);
        if (index > -1) {
          this.selectionIds.splice(index, 1);
        }
      });
    } else {
      const selectIds = [];
      this.currentTemplateData.forEach(item => {
        if (!this.selectionIds.includes(item.bk_inst_id)) {
          selectIds.push(item.bk_inst_id);
        }
      });
      this.selectionIds = this.selectionIds.concat(selectIds);
    }
    this.isSelectAll = !this.isSelectAll;
    this.handleCheckChange();
    this.tableRef?.handleGetDefaultData('selection-change');
  }
  // 检测是否全选
  // eslint-disable-next-line @typescript-eslint/member-ordering
  getAllSelectedStatus() {
    if (this.searchValue) {
      this.isSelectAll = this.currentTemplateData.length
        ? this.currentTemplateData.every(item => this.selectionIds.includes(item.bk_inst_id))
        : false;
    }
  }
}
</script>
<style lang="scss" scoped>
.service-template {
  display: flex;
  color: #63656e;

  &-left {
    // flex-basis: 240px;
    display: flex;
    flex-direction: column;
    width: 0;

    .template-list {
      flex: 1;
      margin: 12px 0;
    }

    .template-list-item {
      display: flex;
      justify-content: space-between;
      height: 32px;
      padding: 0 10px;
      line-height: 32px;
      cursor: pointer;
      border-radius: 2px;

      .item-name {
        display: flex;
        align-items: center;
        overflow: hidden;

        .label {
          flex: 1;
          margin-left: 8px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }

      .count {
        display: inline-block;
        height: 20px;
        padding: 0 5px;
        line-height: 20px;
        background: #f0f1f5;
      }

      &:hover {
        background: #f5f6fa;
      }
    }

    .select-all {
      margin-top: 16px;
      text-align: right;

      .btn {
        font-size: 12px;
        color: #3a84ff;
        cursor: pointer;
      }
    }
  }

  &-right {
    flex: 1;
    overflow: auto;
  }
}
</style>
