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
  <div class="empty-target">
    <top-hint
      v-if="needTitle"
      class="target-hint"
    >
      <slot> {{ $t('未选择采集目标，但并不影响本次操作') }} </slot>
    </top-hint>
    <div class="empty-container">
      <i class="icon-monitor icon-tishi hint-icon" />
      <div class="hint-text">
        <slot name="desc">
          {{ $t('未选择采集目标，无需下发') }}
        </slot>
      </div>
    </div>
  </div>
</template>

<script>
import TopHint from './top-hint';

export default {
  name: 'EmptyTarget',
  components: {
    TopHint,
  },
  props: {
    needTitle: {
      type: Boolean,
      default: true,
    },
  },
};
</script>

<style lang="scss" scoped>
.empty-target {
  height: 500px;
  margin-bottom: 20px;

  .target-hint {
    margin-bottom: 10px;
  }

  .empty-container {
    height: 452px;
    background: #fff;
    border-radius: 2px;
    border: 1px dashed #dcdee5;
    position: relative;
    display: flex;
    justify-content: center;

    .hint-icon {
      position: absolute;
      top: 142px;
      left: calc(50% - 16px);
      font-size: 32px;
      color: #dcdee5;
    }

    .hint-text {
      min-width: 144px;
      height: 16px;
      line-height: 16px;
      position: absolute;
      top: 186px;
      font-size: 12px;
      color: #979ba5;
    }
  }
}
</style>
