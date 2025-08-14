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
  <i :class="iconClass" />
</template>
<script lang="ts">
import { Component, Prop, Vue } from 'vue-property-decorator';

type AlarmStatus = 'ABNORMAL' | 'CLOSED' | 'RECOVERED';
type StatusMap = {
  [k in AlarmStatus]: string;
};
type TypeValue = 'level' | 'notice' | 'status';

@Component({
  name: 'icon',
})
export default class Icon extends Vue {
  // icon类别（级别、状态、通知状态）
  @Prop({ default: '' }) private readonly type: TypeValue;
  // icon类型
  @Prop({ default: '' }) private readonly status: number | string;

  // 事件级别对应icon
  private levelTuple = ['danger', 'mind-fill', 'tips'];
  // 告警状态Map
  private statusMap: StatusMap = {
    RECOVERED: 'icon-checked',
    ABNORMAL: 'icon-monitor icon-mc-close',
    CLOSED: 'icon-monitor icon-mc-close',
  };

  get iconClass() {
    if (this.type === 'level') {
      return `icon-monitor icon-${this.levelTuple[(this.status as number) - 1]}`;
    }
    if (this.type === 'notice') {
      return this.status === 'SUCCESS' ? 'icon-checked' : 'icon-monitor icon-mc-close';
    }
    if (this.type === 'status') {
      return this.statusMap[this.status];
    }
    return '';
  }
}
</script>
<style lang="scss" scoped>
@import '../../static/scss/variate';

$colorList: #ea3636 #ff9c01 #ffd000;
$statusList: 'danger' 'mind-fill' 'tips';

@for $i from 1 through 3 {
  .icon-#{nth($statusList, $i)} {
    position: relative;
    top: 1px;
    margin-right: 6px;
    font-size: 14px;
    color: nth($colorList, $i);
  }
}

.icon-danger {
  position: relative;
  top: 0;
}

.icon-mc-close {
  font-size: 22px;
  font-weight: bold;
  color: $deadlyColor;
}

.icon-checked {
  position: relative;
  top: -1px;
  width: 6px;
  height: 10px;
  margin-right: 6px;
  border-color: #10c178;
  border-style: solid;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}
</style>
