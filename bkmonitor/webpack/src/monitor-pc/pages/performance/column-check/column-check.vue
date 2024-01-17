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
  <div class="column-check-wrapper">
    <bk-checkbox
      :indeterminate="value === 1"
      :value="value === 2"
      :class="{
        'all-checked': currentType === 'all',
        indeterminate: value === 1 && currentType === 'all'
      }"
      :disabled="disabled"
      @change="handleChangeAll"
    />
    <bk-popover
      placement="bottom-start"
      theme="column-check"
      :arrow="false"
      trigger="click"
      ref="popover"
      offset="-10, 0"
      :distance="0"
      :on-hide="() => (showList = false)"
      :on-show="() => (showList = true)"
    >
      <i :class="['icon-monitor', showList ? 'icon-arrow-up' : 'icon-arrow-down']" />
      <template #content>
        <ul class="dropdown-list">
          <li
            :class="['list-item', { 'list-item-active': currentType === item.id }]"
            v-for="(item, index) in list"
            :key="index"
            @click="handleSelect(item.id)"
          >
            {{ item.name }}
          </li>
        </ul>
      </template>
    </bk-popover>
  </div>
</template>

<script lang="ts">
import { Component, Emit, Prop, Ref, Vue, Watch } from 'vue-property-decorator';


@Component({
  name: 'column-check'
})
export default class StrategySetTarget extends Vue {
  @Ref('popover') readonly popover!: any;

  @Prop({
    default: []
  })
    list: { id: string; name: string }[];

  @Prop({
    default: 0,
    validator: val => [0, 1, 2].includes(val)
  })
    value: number;

  @Prop({ default: 'current' }) readonly defaultType: 'current' | 'all';
  @Prop({ default: false, type: Boolean }) disabled: boolean;

  checkValue = false;
  currentType = 'current';
  showList = false;

  created() {
    this.currentType = this.defaultType;
  }

  @Watch('defaultType')
  handleTypeChange() {
    this.currentType = this.defaultType;
  }

  @Emit('change')
  emitChange(value: number, type: string): { value: number; type: string } {
    return {
      value,
      type
    };
  }

  // 选择全选方式
  handleSelect(type: string): void {
    this.currentType = type;
    this.checkValue = true;
    this.popover.instance.hide();
    this.emitChange(this.checkValue ? 2 : 0, this.currentType);
  }

  // 全选操作
  handleChangeAll(value: boolean): void {
    this.checkValue = value;
    this.emitChange(this.checkValue ? 2 : 0, value ? this.currentType : 'current');
  }
}
</script>

<style lang="scss">
.column-check-theme {
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: all;

  .tippy-backdrop {
    background: none;
  }

  .dropdown-list {
    padding: 5px 0;
    overflow: hidden;
    font-size: 14px;
    background-color: #fff;
    border-radius: 4px;
    box-shadow: 0px 3px 6px 1px rgba(0, 0, 0, .1);

    .list-item {
      height: 32px;
      padding: 0 16px;
      line-height: 32px;
      color: #63656e;
      pointer-events: all;
      cursor: pointer;
    }

    .list-item-active {
      color: #3a84ff;
      background-color: #eaf3ff;
    }
  }
}
</style>
<style lang="scss">
.column-check-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;

  .all-checked {
    .bk-checkbox {
      background-color: #fff;

      &::after {
        border-color: #3a84ff;
      }
    }
  }

  .indeterminate {
    .bk-checkbox {
      &::after {
        background: #3a84ff;
      }
    }
  }

  .bk-tooltip {
    position: absolute;
    top: 1px;
    right: -20px;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;

    .bk-tooltip-ref {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 100%;

      .icon-monitor {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        font-size: 20px;
        cursor: pointer;
      }
    }
  }
}
</style>
