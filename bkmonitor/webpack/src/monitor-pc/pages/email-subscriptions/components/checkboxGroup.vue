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
  <div class="checkbox-group-wrap">
    <bk-checkbox
      v-for="item in list"
      :key="JSON.stringify(item)"
      :class="['list-item', { active: active === item.key }]"
      :true-value="item.key"
      :false-value="''"
      :disabled="disabled && !localValue.includes(item.key)"
      :checked="isChecked(item.key)"
      @change="(v, ov) => handleChange(v, ov, item)"
    >
      <span
        v-bk-overflow-tips
        class="checkbox-item-title"
        >{{ item.title }}</span
      >
    </bk-checkbox>
  </div>
</template>

<script lang="ts">
import { Component, Emit, Model, Prop, Vue, Watch } from 'vue-property-decorator';

import type { IGraphValueItem } from '../types';
/**
 * 图表多选组件
 */
@Component({
  name: 'checkbox-group',
})
export default class CheckboxGroup extends Vue {
  // value双向绑定
  @Model('valueChange', { type: Array }) private value: IGraphValueItem[];

  // 列表
  @Prop({ default: () => [], type: Array }) private readonly list: any;

  // 选中
  @Prop({ default: '', type: String }) private readonly active: string;

  @Prop({ default: false, type: Boolean }) private readonly disabled: boolean;

  // 本地存储选中值
  private localValue: IGraphValueItem[] = [];

  @Emit('valueChange')
  handleValueChange() {
    return this.localValue;
  }

  @Watch('value', { immediate: true })
  valueChange(v: IGraphValueItem[]) {
    this.localValue = v;
  }

  private handleChange(v, ov, item) {
    if (v) {
      this.localValue.push({
        id: v,
        name: item.title,
      });
    } else {
      const index = this.localValue.findIndex(item => item.id === ov);
      this.localValue.splice(index, 1);
    }
    this.handleValueChange();
  }

  private isChecked(key) {
    return !!this.localValue.find(item => item.id === key);
  }
}
</script>

<style lang="scss" scoped>
.checkbox-group-wrap {
  .list-item {
    display: block;
    height: 20px;
    margin-top: 8px;
    line-height: 20px;

    .checkbox-item-title {
      display: inline-block;
      max-width: 229px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    :deep(.bk-checkbox-text) {
      height: 20px;
      margin-left: 6px;
      font-size: 12px;
      line-height: 20px;
      color: #63656e;

      &:hover {
        color: #3a84ff;
      }
    }
  }

  .active {
    :deep(.bk-checkbox-text) {
      color: #3a84ff;
    }
  }
}
</style>
