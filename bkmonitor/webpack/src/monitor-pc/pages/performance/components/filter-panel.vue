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
  <div>
    <performance-dialog
      :title="$t('主机筛选')"
      :value="value"
      :ok-text="$t('button-筛选')"
      :cancel-text="$t('清空')"
      :show-undo="false"
      @change="handleDialogValueChange"
      @cancel="handleReset"
      @confirm="handleFilterData"
    >
      <div
        class="filter-panel"
        v-if="value"
      >
        <div
          v-for="item in data"
          :key="item.id"
        >
          <filter-panel-item
            v-if="item.show"
            :class="{ mb10: lastItemId !== item.id }"
            v-model="item.value"
            :title="item.name"
            :type="item.type"
            :disabled="item.filterDisable"
            :options="item.options || []"
            :conditions="item.conditions || {}"
            :multiple="!!item.multiple"
            :allow-empt="!!item.allowEmpt"
            @close="handlePanelItemClose(item.id)"
          />
        </div>
        <bk-button
          class="add-panel"
          text
          @click="handleMoreClick"
        >
          <i class="icon-monitor icon-mc-add" />
          {{ $t('添加条件') }}
        </bk-button>
      </div>
    </performance-dialog>
    <condition-panel
      v-model="showMoreCondition"
      :field-data="data"
      :loading="tableInstance.loading"
      @confirm="handleConditionConfirm"
    />
  </div>
</template>
<script lang="ts">
import { Component, Emit, Inject, Model, Prop, Vue, Watch } from 'vue-property-decorator';

import { Storage } from '../../../utils';
import { IFieldConfig, ISelectedValues } from '../performance-type';
import TableStore from '../table-store';

import ConditionPanel from './condition-panel.vue';
import FilterPanelItem from './filter-panel-item.vue';
import PerformanceDialog from './performance-dialog.vue';

const CONDITION_CHECKED_LIST = 'CONDITION_CHECKED_LIST'; /** 筛选条件缓存key */
@Component({
  name: 'filter-panel',
  components: {
    PerformanceDialog,
    FilterPanelItem,
    ConditionPanel
  }
})
export default class FilterPanel extends Vue {
  @Model('update-value', { type: Boolean }) readonly value: boolean;
  @Prop({ default: () => [] }) readonly fieldData!: IFieldConfig[];
  @Inject('tableInstance') readonly tableInstance: TableStore;

  data: IFieldConfig[] = [];
  showMoreCondition = false;
  storage = new Storage();

  get lastItemId() {
    const list = this.data.filter(item => item.show);
    return list?.[list.length - 1].id;
  }
  created() {
    this.data = JSON.parse(JSON.stringify(this.fieldData));
    this.handleCheckedData();
  }

  @Watch('fieldData', { deep: true })
  handleFieldDataChange(v) {
    this.data = JSON.parse(JSON.stringify(v));
    this.handleCheckedData();
    this.updateCheckedData();
  }

  @Emit('update-value')
  handleDialogValueChange(v: boolean) {
    // 还原筛选条件
    if (!v) {
      this.data = JSON.parse(JSON.stringify(this.fieldData));
      this.updateCheckedData();
    }
    return v;
  }

  @Emit('reset')
  handleReset() {
    this.tableInstance.page = 1;
    this.tableInstance.fieldData.forEach((item) => {
      item.value = Array.isArray(item.value) ? [] : '';
    });
  }

  /**
   * @description: 更新条件的显隐状态
   * @param {*}
   * @return {*}
   */
  handleCheckedData() {
    const loadingFieldIds = [
      'status',
      'cpu_load',
      'cpu_usage',
      'disk_in_use',
      'io_util',
      'mem_usage',
      'psc_mem_usage',
      'display_name'
    ];
    this.data.forEach((item) => {
      if (this.tableInstance.loading) {
        item.show = !!item.filterChecked && !loadingFieldIds.includes(item.id);
      } else {
        // 增加show属性控制显隐，避免data引用发生改变而导致组件刷新
        item.show = !!item.filterChecked;
      }
    });
  }

  handleMoreClick() {
    this.showMoreCondition = true;
  }

  handleConditionConfirm(v: ISelectedValues) {
    const selected = v.selectedGroup.concat(v.unSelectedGroup);
    this.data.forEach((item) => {
      item.filterChecked = selected.includes(item.id);
    });
    this.handleCheckedData();
    this.updatedConditionStorage();
  }

  /** 根据缓存更新选中的条件的状态 */
  updateCheckedData() {
    const checkedList = this.storage.get(CONDITION_CHECKED_LIST);
    this.data.forEach((item) => {
      if (!!checkedList) {
        item.show = checkedList.includes(item.id);
        item.filterChecked = item.show;
      }
    });
  }

  /**
   * 更新筛选条件的选中缓存
   */
  updatedConditionStorage() {
    const checkedId = this.data.reduce((total, item) => {
      if (item.show) total.push(item.id);
      return total;
    }, []);
    this.storage.set(CONDITION_CHECKED_LIST, checkedId);
  }

  @Emit('close')
  handlePanelItemClose(id: string) {
    const item = this.tableInstance.fieldData.find(item => item.id === id);
    if (item) {
      item.filterChecked = false;
      Array.isArray(item.value) ? (item.value = []) : (item.value = '');
    }
    return item;
  }

  @Emit('filter')
  handleFilterData() {
    this.tableInstance.page = 1;
    this.tableInstance.fieldData.forEach((item) => {
      const data = this.data.find(data => data.id === item.id);
      if (data) {
        item.value = data.value;
        item.filterChecked = data.filterChecked;
        // 非空值情况下默认展示数据列，空值就保持原有展示情况
        const notEmptyValue = Array.isArray(data.value) ? data.value.length > 0 : !!data.value;
        // 集群模块字段对应的是 集群列 和 模块列
        if (item.id === 'cluster_module' && notEmptyValue) {
          this.tableInstance.fieldData
            .filter(item => ['bk_cluster', 'bk_inst_name'].includes(item.id))
            .forEach((item) => {
              item.checked = true;
            });
        } else if (notEmptyValue) {
          item.checked = true;
        }
      }
    });
    return this.data;
  }
}
</script>
<style lang="scss" scoped>
.filter-panel {
  padding: 10px 10px 0;

  .add-panel {
    margin-left: 12px;
    font-size: 12px;
  }
}
</style>
