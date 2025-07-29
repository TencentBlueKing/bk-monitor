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
  <transition name="fade">
    <div
      v-if="show"
      v-transfer-dom="'.bk-mobile-landscape'"
      class="bk-select"
    >
      <!-- select内容 -->
      <div class="main">
        <!-- select 标题 -->
        <div
          v-if="title"
          class="title"
        >
          {{ title }}
        </div>
        <!-- options picker -->
        <slot>
          <van-picker
            :columns="columns"
            :default-index="defaultIndex"
            @change="handlePickerChange"
          />
        </slot>
        <!-- 确定/取消 操作 -->
        <div class="contral-btn">
          <span
            class="cancel"
            @click="handleSelectCancel"
          >
            {{ $t('取消') }}
          </span>
          <span class="line" />
          <span
            class="confirm"
            @click="handleSelectConfirm"
          >
            {{ $t('确定') }}
          </span>
        </div>
      </div>
    </div>
  </transition>
</template>
<script lang="ts">
import { Component, Emit, Model, Prop, Vue } from 'vue-property-decorator';

import { Picker } from 'vant';

import transferDom from '../../directives/transform-dom';

interface IOptions {
  text: string;
  value: ValueType;
}

type ValueType = number | string;
@Component({
  name: 'bk-select',
  components: {
    [Picker.name]: Picker,
  },
  directives: {
    transferDom,
  },
})
export default class BkSelect extends Vue {
  // 自定义model
  @Model('update', { type: [String, Number, Array] }) readonly value!: ValueType;

  // select 标题
  @Prop({ default: '' }) private title: string;

  // select options数据项
  @Prop({
    default: () => [
      {
        text: 'no data',
        value: 0,
      },
    ],
  })
  private columns: IOptions[];

  // 是否显示select组件
  @Prop({ default: false }) private show: boolean;

  // select默认选中的索引
  get defaultIndex() {
    return this.columns.findIndex(item => item.value === this.value);
  }

  // 当前选中的值
  private selectedValues: ValueType = this.value;

  // 取消事件
  @Emit('cancel')
  handleSelectCancel() {
    this.handleHideSelect();
    return this.value;
  }

  // 确定事件
  @Emit('confirm')
  @Emit('update')
  handleSelectConfirm() {
    this.handleHideSelect();
    return this.selectedValues;
  }

  handlePickerChange(picker: Picker, selected: IOptions, index: number) {
    this.selectedValues = selected.value;
    this.$emit('change', picker, selected, index);
  }

  @Emit('change')
  @Emit('update:show')
  handleHideSelect() {
    return false;
  }
}
</script>
<style lang="scss" scoped>
@import '../../static/scss/variate.scss';
@import '../../static/scss/mixin.scss';

.bk-select {
  z-index: 9999;

  @include overlay;

  .main {
    @include select-main;
  }
}

@include fade-select-main;

.fade-enter,
.fade-leave-to {
  opacity: 0;

  .main {
    bottom: -300px;
  }
}
</style>
