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
  <span
    :class="['monitor-select-wrap', { 'is-disabled': disabled }]"
    @click="handleClick"
  >
    <span class="btn-content">
      <slot />
    </span>
    <bk-select
      ref="selectDropdown"
      v-model="localValue"
      :ext-popover-cls="`dropdown-content ${extPopoverCls}`"
      class="select-dropdown"
      :popover-min-width="popoverMinWidth"
      @toggle="handleToggle"
      @change="handleSelectChange"
    >
      <bk-option
        v-for="(option, index) in localList"
        :id="option.id"
        :key="index"
        :disabled="option.disabled"
        :name="option.name"
      >
        <slot
          :option="option"
          name="item"
        />
      </bk-option>
    </bk-select>
  </span>
</template>
<script lang="ts">
import { Component, Emit, Model, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import { deepClone } from 'monitor-common/utils/utils';

@Component({ name: 'monitor-select' })
export default class MonitorSelect extends Vue {
  @Prop({ default: () => [], type: Array }) readonly list: any;
  @Prop({ default: false, type: Boolean }) readonly disabled: boolean;
  @Prop({ default: 100, type: Number }) readonly popoverMinWidth: number;
  @Prop({ default: '', type: String }) readonly extPopoverCls: '';

  @Model('valueChange') readonly value: number | string;

  @Ref('selectDropdown') readonly selectDropdownRef: any;

  private showInput = false;
  private localValue: number | string = '';
  private localList: any = [];
  private localInputValue = '';

  @Watch('value', { immediate: true })
  handleValueChange(v) {
    this.localValue = v;
  }

  @Watch('list', { immediate: true, deep: true })
  handleListChange(list) {
    this.localList = list;
  }

  @Emit('change')
  @Emit('valueChange')
  emitValueChange() {
    return this.localValue;
  }

  @Emit('select')
  emitSelect() {
    return {
      newVal: this.localValue,
      oldVal: this.value,
    };
  }

  @Emit('listChange')
  emitListChange() {
    return deepClone(this.localList);
  }

  @Emit('toggle')
  handleToggle(val: boolean) {
    !val && (this.showInput = false);
    return val;
  }
  // 更新值
  public async updateValue() {
    await this.$nextTick();
    this.localValue = this.value;
  }

  private handleClick() {
    if (this.disabled) return;
    this.selectDropdownRef?.show();
  }

  private handleSelectChange() {
    if (this.value !== this.localValue) {
      this.emitSelect();
      this.emitValueChange();
    }
  }

  private handleShowInput() {
    this.showInput = true;
  }
}
</script>

<style lang="scss" scoped>
.monitor-select-wrap {
  position: relative;
  cursor: pointer;

  .btn-content {
    z-index: 1;
  }

  .select-dropdown {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    left: 0;
    z-index: -1;
    overflow: hidden;
    line-height: 1;
    opacity: 0;

    :deep(.bk-icon) {
      display: none;
    }

    :deep(.bk-select-dropdown) {
      height: 100%;

      .bk-tooltip-ref {
        height: 100%;
      }

      :deep(.bk-select-name) {
        height: 100%;
        padding: 0;
      }
    }
  }
}

.is-disabled {
  cursor: default;
}
</style>

<style lang="scss">
.dropdown-content .test {
  .bk-option-content,
  .bk-select-extension {
    padding: 0 10px;
  }

  .add-input-wrap {
    display: flex;
    align-items: center;

    .input {
      flex: 1;
    }

    .btn {
      flex-shrink: 0;
      padding: 0;
      margin: 0 8px;

      &:last-child {
        margin: 0;
      }
    }
  }
}
</style>
