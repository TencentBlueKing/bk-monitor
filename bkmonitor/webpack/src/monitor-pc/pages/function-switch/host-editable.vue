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
  <div class="host-editable-wrapper">
    <div
      ref="text"
      class="text"
      @dblclick="dblclickHost"
    >
      {{ value || '--' }}
    </div>
    <div
      v-show="editable"
      ref="input"
      class="input"
      :contenteditable="editable"
      @blur="handleBlur"
      @keydown.enter="handleEnter"
    >
      {{ value }}
    </div>
  </div>
</template>

<script lang="ts">
import { Component, Prop, Ref, Vue } from 'vue-property-decorator';

@Component({
  name: 'host-editable',
})
export default class HostEditable extends Vue {
  @Ref('input') readonly inputRef;
  @Ref('text') readonly textRef;
  // host
  @Prop({ default: false, required: true }) readonly value: string;
  // 编辑状态
  editable = false;

  // 失去焦点后往外更新值
  handleBlur(evt) {
    this.editable = false;
    const text = evt.target.innerText;
    this.value !== text && this.$emit('input', text);
  }

  // 双击后可编辑状态
  dblclickHost() {
    this.editable = true;
    this.$nextTick(() => {
      this.inputRef.focus();
      this.inputRef.innerText = '';
      this.inputRef.innerText = this.value;
      const el = this.inputRef;
      // 设置光标位置至末尾
      if (typeof window.getSelection !== 'undefined' && typeof document.createRange !== 'undefined') {
        const range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
      }
    });
  }

  // 回车
  handleEnter() {
    this.inputRef.blur();
  }
}
</script>

<style lang="scss" scoped>
@import '../../theme/index.scss';

.host-editable-wrapper {
  position: relative;
  height: 26px;
  cursor: pointer;

  .text {
    position: relative;
    padding: 0 20px 0 0;
    line-height: 26px;

    @include ellipsis;
  }

  &:hover {
    background-color: #f0f1f5;
  }

  .input {
    position: absolute;
    top: 0;
    left: 0;
    z-index: 1;
    width: 100%;
    height: 60px;
    overflow-y: scroll;
    background-color: #fff;
    border: 1px solid $slightFontColor;
    border-radius: 2px;
  }
}
</style>
