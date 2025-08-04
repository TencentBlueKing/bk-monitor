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
    class="label-wrapper"
    :class="orientation"
    @click="handleClick"
  >
    <i
      class="icon-monitor"
      :class="`icon-${orientation}`"
    />
  </div>
</template>
<script lang="ts">
import { Component, Emit, Model, Vue } from 'vue-property-decorator';

export enum Screen {
  LANDSCAPE = 'landscape', // 横屏
  PORTRAIT = 'portrait', // 竖屏
}

@Component
export default class ScreenOrientation extends Vue {
  // 自定义v-model
  @Model('orientation-change', { type: String }) private readonly value!: string;

  // 当前方向
  private orientation = '';

  created() {
    this.orientation = this.getRealOrientation();
    window.addEventListener('orientationchange', this.handleOrientationchange, false);
    this.$once('hook:beforeDestroy', () => {
      window.removeListener(this.handleOrientationchange);
    });
  }

  @Emit('click')
  @Emit('orientation-change')
  handleClick() {
    this.orientation = this.orientation === Screen.PORTRAIT ? Screen.LANDSCAPE : Screen.PORTRAIT;
    let className = '';
    let rotate = 0;
    const realOrientation = this.getRealOrientation();
    if (realOrientation !== this.orientation) {
      className = this.orientation === Screen.LANDSCAPE ? 'bk-mobile-landscape' : 'bk-mobile-portrait';
      rotate = this.orientation === Screen.LANDSCAPE ? 90 : -90;
    } else {
      className = '';
      rotate = 0;
    }

    this.setRootElementClass(className, rotate);
    return this.orientation;
  }

  @Emit('change')
  @Emit('orientation-change')
  handleOrientationchange() {
    this.orientation = this.getRealOrientation();
    this.setRootElementClass('', 0);
    return this.orientation;
  }

  setRootElementClass(className: string, rotate: number) {
    const htmlEle = this.$root.$el as HTMLElement;
    htmlEle.className = className;
    htmlEle.style.transform = rotate === 0 ? 'unset' : `rotate(${rotate}deg)`;
  }

  getRealOrientation() {
    return Math.abs(window.orientation as number) === 90 ? Screen.LANDSCAPE : Screen.PORTRAIT;
  }
}
</script>
<style lang="scss" scoped>
.label-wrapper {
  position: fixed;
  right: 1.5rem;
  bottom: 1.5rem;
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 3.5rem;
  height: 3.5rem;
  background: #fff;
  border-radius: 50%;
  box-shadow: 0 3px 6px 0 rgb(79 85 96 / 30%);

  i {
    font-size: 1.6rem;
    color: #3a84ff;
  }
}
</style>
