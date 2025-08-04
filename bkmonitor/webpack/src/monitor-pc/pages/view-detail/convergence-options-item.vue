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
    class="convergence-options"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
  >
    <i
      v-show="isShowCloseIcon && hasCloseIcon"
      class="icon-monitor icon-mc-close"
      @click="handleClickClose"
    />
    <div class="convergence-options-label">
      {{ title }}
    </div>
    <bk-select
      v-model="checkData"
      searchable
      :clearable="false"
      :popover-options="{ appendTo: 'parent' }"
      @change="handleCheckedChange"
    >
      <bk-option
        v-for="(option, index) in selectList"
        :id="option.id"
        :key="index"
        :name="option.name"
      />
    </bk-select>
  </div>
</template>

<script lang="ts">
import { Component, Prop, Vue } from 'vue-property-decorator';

@Component({
  name: 'convergence-options',
})
export default class ConvergenceOptions extends Vue {
  @Prop()
  readonly hasCloseIcon: boolean;
  @Prop({ default: false })
  readonly isDefault: boolean;
  @Prop()
  readonly title: string;
  @Prop()
  readonly id: string;
  @Prop()
  readonly groupbyList: () => Promise<any[]>;
  @Prop({ default: '' }) readonly defaultValue: string;

  selectList = [];
  isShowCloseIcon = false;
  checkData = '';

  created() {
    this.getGroupList();
  }

  async getGroupList() {
    this.selectList = await this.groupbyList();
    if (this.isDefault) {
      this.selectList.unshift({ id: 'all', name: this.$tc('全部') });
      this.checkData = 'all';
    }
    if (this.defaultValue) {
      for (const item of this.selectList) {
        if (item.id === this.defaultValue) {
          this.checkData = item.id;
          break;
        }
      }
    }
  }

  handleMouseEnter() {
    this.isShowCloseIcon = true;
  }

  handleMouseLeave() {
    this.isShowCloseIcon = false;
  }

  handleClickClose() {
    this.$emit('delete-dimension');
  }

  handleCheckedChange(value) {
    const res = {};
    res[this.id] = value;
    this.$emit('checked-change', res);
  }
}
</script>

<style lang="scss" scoped>
.convergence-options {
  position: relative;
  width: 320px;
  height: 73px;
  padding: 5px 10px 10px 10px;

  &-label {
    margin-bottom: 6px;
  }

  &:hover {
    background: #f5f6fa;
    border-radius: 2px;
  }

  .icon-mc-close {
    position: absolute;
    top: 0;
    right: 0;
    font-size: 24px;
    color: #ea3636;
    cursor: pointer;
  }
}
</style>
