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
  <transition
    name="monitor-loading-fade"
    @after-leave="handleAfterLeave"
  >
    <div
      v-show="visible"
      class="monitor-loading"
      :class="extCls"
      :style="{ backgroundColor: background || '' }"
    >
      <div class="monitor-loading-spinner">
        <span
          v-for="i in 4"
          :key="i"
          class="loading-pointer"
          :class="'pointer-' + i"
        />
      </div>
    </div>
  </transition>
</template>

<script lang="ts">
import { Component, Vue } from 'vue-property-decorator';

@Component
export default class MonitorLoading extends Vue {
  visible = false;
  background = 'rgba(255, 255, 255, 0.9)';
  extCls = '';

  handleAfterLeave(): void {
    this.$emit('after-leave');
  }
}
</script>
<style lang="scss">
$colorList: #fd6154 #ffb726 #4cd084 #57a3f1;

.monitor-loading-fade-enter,
.monitor-loading-fade-leave-active {
  opacity: 0;
}

.monitor-loading {
  position: absolute;
  top: 0;
  right: 4px;
  bottom: 0;
  left: 4px;
  z-index: 900;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.3s;

  @keyframes scale-animate {
    0% {
      transform: scale(1);
    }

    100% {
      transform: scale(0.6);
    }
  }

  &-spinner {
    display: flex;
    align-items: center;

    .loading-pointer {
      width: 14px;
      height: 14px;
      margin-right: 6px;
      border-radius: 100%;
      transform: scale(0.6);
      animation-name: scale-animate;
      animation-duration: 0.8s;
      animation-iteration-count: infinite;
      animation-direction: normal;

      @for $i from 1 through length($colorList) {
        &.pointer-#{$i} {
          /* stylelint-disable-next-line function-no-unknown */
          background-color: nth($colorList, $i);
          animation-delay: ($i * 0.15s + 0.1s);
        }
      }
    }
  }
}
</style>
