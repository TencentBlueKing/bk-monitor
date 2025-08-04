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
<!--
 * @Author:
 * @Date: 2021-05-25 19:15:01
 * @LastEditTime: 2021-06-18 10:52:49
 * @LastEditors:
 * @Description:
-->
<template>
  <bk-dialog
    :value="value"
    :title="$t('添加更多条件')"
    render-directive="if"
    header-position="left"
    width="460"
    @value-change="handleValueChange"
    @confirm="handleConfirm"
  >
    <div
      v-for="item in groupList"
      :key="item.id"
      class="condition-panel"
    >
      <h2 class="condition-panel-title">
        {{ item.name }}
      </h2>
      <bk-checkbox-group
        v-model="selectedValues[item.id]"
        class="condition-panel-content"
      >
        <bk-checkbox
          v-for="data in item.data"
          :key="data.id"
          class="content-item"
          :value="data.id"
          :disabled="data.filterDisable || (loading && loadingFieldIds.includes(data.id))"
        >
          {{ data.name }}
        </bk-checkbox>
      </bk-checkbox-group>
    </div>
  </bk-dialog>
</template>
<script lang="ts">
import { Component, Emit, Model, Prop, Vue, Watch } from 'vue-property-decorator';

import type { IFieldConfig, ISelectedValues } from '../performance-type';

@Component({ name: 'condition-panel' })
export default class ConditionPanel extends Vue {
  @Model('value-change') private readonly value: boolean;

  @Prop({ default: () => [] }) private readonly fieldData!: IFieldConfig[];
  @Prop({ default: false, type: Boolean }) private readonly loading!: boolean;

  private data = [];
  private selectedValues: ISelectedValues = {
    selectedGroup: [],
    unSelectedGroup: [],
  };
  private loadingFieldIds = [
    'status',
    'cpu_load',
    'cpu_usage',
    'disk_in_use',
    'io_util',
    'mem_usage',
    'psc_mem_usage',
    'display_name',
  ];

  private get groupList() {
    return [
      {
        id: 'selectedGroup',
        name: window.i18n.t('已选条件'),
        data: this.checkedData,
      },
      {
        id: 'unSelectedGroup',
        name: window.i18n.t('可选条件'),
        data: this.unCheckedData,
      },
    ];
  }

  // 获取当前勾选过的字段
  private get checkedData() {
    return this.data.filter(item => !!item.filterChecked);
  }

  private get unCheckedData() {
    return this.data.filter(item => !item.filterChecked);
  }

  created() {
    this.data = JSON.parse(JSON.stringify(this.fieldData));
  }

  @Watch('fieldData', { deep: true })
  private handleFieldDataChange(v) {
    this.data = JSON.parse(JSON.stringify(v));
  }

  @Watch('value')
  private handleChange() {
    this.selectedValues.selectedGroup = this.checkedData.map(item => item.id);
    this.selectedValues.unSelectedGroup = [];
  }

  @Emit('value-change')
  private handleValueChange(v) {
    return v;
  }

  @Emit('confirm')
  private handleConfirm() {
    return this.selectedValues;
  }
}
</script>
<style lang="scss" scoped>
.condition-panel {
  &-title {
    font-size: 12px;
    font-weight: 700;
  }

  &-content {
    display: flex;
    flex-wrap: wrap;

    .content-item {
      flex-basis: 33%;
      margin-bottom: 10px;

      :deep(.bk-checkbox-text) {
        width: 110px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
  }
}
</style>
