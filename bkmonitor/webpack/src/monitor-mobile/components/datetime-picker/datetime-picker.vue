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
      class="bk-datetime-picker"
    >
      <div class="main">
        <div class="title">
          {{ title ? title : $t('选择截止时间') }}
        </div>
        <van-datetime-picker
          ref="datetimePicker"
          :max-date="maxDate"
          :min-date="minDate"
          :value="value"
          type="datetime"
        />
        <div class="contral-btn">
          <span
            class="cancel"
            @click="handleCancel"
            >{{ $t('取消') }}</span
          >
          <span class="line" />
          <span
            class="confirm"
            @click="handleConfirm"
            >{{ $t('确定') }}</span
          >
        </div>
      </div>
    </div>
  </transition>
</template>
<script lang="ts">
import { Component, Emit, Prop, Ref, Vue } from 'vue-property-decorator';

import { DatetimePicker } from 'vant';

export interface ITimeObj {
  dateObj: Date;
  datetime: string;
  timestamp: number;
}

@Component({
  name: 'bk-datetime-picker',
  components: {
    [DatetimePicker.name]: DatetimePicker,
  },
})
export default class TendencyChart extends Vue {
  @Ref() readonly datetimePicker!: DatetimePicker;
  // 显示状态
  @Prop({ default: false }) private show: boolean;

  // 日期范围
  @Prop(Date) private minDate: Date;

  @Prop(Date) private maxDate: Date;

  // 当前时间
  @Prop({ default: () => new Date() }) private value: Date;

  @Prop({ default: '' }) private readonly title: string;

  // 处理点击确定
  @Emit('confirm')
  handleConfirm(): ITimeObj {
    const DP = this.datetimePicker.getPicker();
    // 当前选中的值
    const val = DP.getValues().map(item => parseInt(item, 10));
    const datetime = val.join('/');
    val[1] -= 1; // 注意月份从0开始
    const timeTuple = [...val] as [number, number, number, number, number];
    const timestamp = +new Date(...timeTuple);
    const timeObj = {
      timestamp,
      datetime,
      dateObj: new Date(...timeTuple),
    };
    this.handleCancel();
    return timeObj;
  }

  // 点击取消
  @Emit('cancel')
  handleCancel() {
    this.$emit('update:show', false);
  }
}
</script>
<style lang="scss" scoped>
@import '../../static/scss/variate';
@import '../../static/scss/mixin';

.bk-datetime-picker {
  position: fixed;
  inset: 0;
  z-index: 9999;
  padding: 1rem;
  background-color: rgb(0 0 0 / 10%);

  :deep(.van-datetime-picker) {
    .van-picker__toolbar {
      display: none;
    }
  }

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
