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
    v-bkloading="{ isLoading }"
    class="dynamic-group"
  >
    <div
      :style="{ width: isNaN(leftPanelWidth) ? leftPanelWidth : `${leftPanelWidth}px` }"
      class="dynamic-group-left"
    >
      <bk-input
        :model-value="searchValue"
        :placeholder="dynamicGroupPlaceholder"
        right-icon="bk-icon icon-search"
        clearable
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
          >{{ isSelectAll ? $t('清除全选') : $t('全选') }}</span
        >
      </div>
      <bk-virtual-scroll
        class="template-list"
        :item-height="32"
        :list="currentTemplateData"
      >
        <template #default="{ data }">
          <li
            class="template-list-item"
            :class="{ active: activeGroupId === data[templateOptions.idKey] }"
            @click="() => handleListClick(data)"
          >
            <div class="item-name">
              <bk-checkbox
                :checked="selectionIds.includes(data[templateOptions.idKey])"
                @change="() => handleCheckboxClick(data)"
                @click.native="e => e.stopPropagation()"
              />
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
    <div class="dynamic-group-right ml20">
      <ip-list-table
        ref="table"
        :disabled-loading="isLoading"
        :empty-text="emptyText"
        :enable-table-search="false"
        :get-search-table-data="getTableData"
        :ip-list-table-config="dynamicGroupTableConfig"
        :show-selection-column="false"
      />
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Ref, Vue } from 'vue-property-decorator';

import { agentStatisticsIpChooserDynamicGroup } from 'monitor-api/modules/model';

import { Debounce } from '../common/util';
import IpSelectorTable from '../components/ip-selector-table.vue';
import IpListTable from './ip-list.vue';

import type {
  IipListParams,
  ITableCheckData,
  ITableConfig,
  ITemplateDataOptions,
  SearchDataFuncType,
} from '../types/selector-type';
import type { TranslateResult } from 'vue-i18n';

// 服务模板
@Component({
  name: 'dynamic-group',
  components: {
    IpSelectorTable,
    IpListTable,
  },
})
export default class ServiceTemplate extends Vue {
  // 获取组件初始化数据
  @Prop({ type: Function, required: true })
  private readonly getDefaultData!: () => Promise<any[]>;
  // 表格搜索数据
  @Prop({ type: Function, required: true }) private readonly getSearchTableData!: SearchDataFuncType;
  // 左侧列表是否勾选回调
  @Prop({ type: Function }) private readonly getDefaultSelections!: Function;

  @Prop({ default: '', type: String }) private readonly dynamicGroupPlaceholder!: string;
  @Prop({
    default: () => ({
      idKey: 'id',
      childrenKey: 'instances_count',
      labelKey: 'name',
    }),
    type: Object,
  })
  private readonly templateOptions!: ITemplateDataOptions;
  // 表格字段配置
  @Prop({ default: () => [], type: Array }) private readonly dynamicGroupTableConfig!: ITableConfig[];
  @Prop({ default: 240, type: [Number, String] }) private readonly leftPanelWidth!: number | string;

  @Ref('table') private readonly tableRef!: IpListTable;

  // 左侧列表区域搜素值
  private searchValue = '';
  // 左侧列表数据
  private tplData: any[] = [];
  // 左侧列表各项存在子项的数量集合
  private tplDataCountByIdMap: Record<string, number> = {};

  // 左侧列表选中项ID数组
  private selectionIds: (number | string)[] = [];
  // 默认为true是为了阻止 IpListTable 组件loading
  private isLoading = true;
  // table 表格空数据时显示文案
  private emptyText: TranslateResult = window.i18n.t('暂无数据');
  // 当前激活分组 ID（用于table接口请求）
  private activeGroupId = '';
  // 全选 checkbox 状态
  private isSelectAll = false;

  private get currentTemplateData() {
    const data = this.tplData;
    const keyword = this.searchValue;
    const labelKey = this.templateOptions.labelKey;
    if (!Array.isArray(data) || keyword.trim() === '') return data;
    return data.filter(item => {
      if (typeof item[labelKey] === 'string') {
        return item[labelKey].indexOf(keyword.trim()) > -1;
      }
      return false;
    });
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
      if (this.tplData.length && !this.activeGroupId) {
        this.activeGroupId = this.tplData[0].id;
        this.handleGetDefaultDataCount();
        this.tableRef?.handleGetDefaultData('selection-change');
      }
    } catch (err) {
      console.log(err);
      return [];
    } finally {
      this.isLoading = false;
    }
  }

  // 获取列表各项存在的子项数量
  private async handleGetDefaultDataCount() {
    const requestParam = {
      dynamic_group_list: this.tplData.map(({ id, meta }) => ({ id, meta })),
      scope_list: [
        {
          scope_type: 'biz',
          scope_id: this.$store.getters.bizId,
        },
      ],
    };
    const result = await agentStatisticsIpChooserDynamicGroup(requestParam);
    this.tplDataCountByIdMap = result.reduce((prev, curr) => {
      prev[curr.dynamic_group.id] = curr.host_count || 0;
      return prev;
    }, {});
  }

  @Debounce(300)
  private async handleTemplateSearchChange(value: string) {
    this.searchValue = value;
    this.$nextTick(() => {
      this.getAllSelectedStatus();
    });
  }

  private async getTableData(params: IipListParams, type?: string) {
    try {
      if (!this.activeGroupId) {
        return {
          total: 0,
          data: [],
        };
      }
      const reqParams = {
        id: this.activeGroupId,
        page_size: params.limit,
        start: 0,
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

  private handleListClick(item: any) {
    const { idKey = 'id' } = this.templateOptions;
    const itemId = item[idKey];
    const shouldRequest = this.activeGroupId !== itemId;
    if (shouldRequest) {
      this.activeGroupId = itemId;
      this.tableRef?.handleGetDefaultData('selection-change');
    }
  }

  private handleCheckboxClick(item: any) {
    const { idKey = 'id' } = this.templateOptions;
    const itemId = item[idKey];
    const index = this.selectionIds.findIndex(id => id === itemId);
    if (index > -1) {
      this.selectionIds.splice(index, 1);
    } else {
      this.selectionIds.push(itemId);
    }
    this.handleCheckChange();
    this.getDefaultSelections(item);
    this.getAllSelectedStatus();
  }

  @Emit('check-change')
  private handleCheckChange(): ITableCheckData {
    const { idKey = 'id' } = this.templateOptions;
    return {
      selections: this.tplData.filter(item => this.selectionIds.includes(item[idKey])),
    };
  }

  private getChildrenCount(groupItem: any) {
    const groupId = groupItem.id;
    return this.tplDataCountByIdMap[groupId] ?? 0;
  }

  public handleGetDefaultSelections() {
    const { idKey = 'id' } = this.templateOptions;
    this.selectionIds = this.tplData.reduce((pre, next) => {
      if (this.getDefaultSelections && !!this.getDefaultSelections(next)) {
        pre.push(next[idKey]);
      }
      return pre;
    }, []);
  }

  handleAllSelected() {
    const { idKey = 'id' } = this.templateOptions;
    /* 全选/清除全选 */
    if (!this.currentTemplateData.length) return;
    if (this.isSelectAll) {
      this.currentTemplateData.forEach(item => {
        const index = this.selectionIds.indexOf(item[idKey]);
        if (index > -1) {
          this.selectionIds.splice(index, 1);
        }
      });
    } else {
      const selectIds = [];
      this.currentTemplateData.forEach(item => {
        if (!this.selectionIds.includes(item[idKey])) {
          selectIds.push(item[idKey]);
        }
      });
      this.selectionIds = this.selectionIds.concat(selectIds);
    }
    this.isSelectAll = !this.isSelectAll;
    this.handleCheckChange();
    this.tableRef?.handleGetDefaultData('selection-change');
  }

  // 检测是否全选

  getAllSelectedStatus() {
    if (this.searchValue) {
      this.isSelectAll = this.currentTemplateData.length
        ? this.currentTemplateData.every(item => this.selectionIds.includes(item[this.templateOptions.idKey]))
        : false;
    }
  }
}
</script>
<style lang="scss" scoped>
.dynamic-group {
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

      &.active {
        background: #e1ecff;

        &:hover {
          background: #e1ecff;
        }
      }

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
