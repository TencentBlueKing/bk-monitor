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
    class="monitor-import"
    @click="handleClick"
  >
    <slot>{{ $t('导入') }}</slot>
    <input
      ref="fileInput"
      :accept="accept"
      type="file"
      @input="handleInput"
    />
  </span>
</template>
<script lang="ts">
import { Component, Emit, Prop, Ref, Vue } from 'vue-property-decorator';

@Component({ name: 'MonitorImport' })
export default class MonitorExport extends Vue {
  @Prop({ default: false, type: Boolean }) returnFileInfo: boolean;
  @Prop({ default: '.json', type: String }) accept: string;
  @Prop({ default: false, type: Boolean }) base64: boolean;
  @Prop({ default: false, type: Boolean }) disabled: boolean;
  @Ref('fileInput') readonly fileInputRef: HTMLElement;

  //   @Ref('input') readonly inputRef: HTMLElement

  @Emit('change')
  emitFile(data) {
    return data;
  }

  handleClick() {
    !this.disabled && this.fileInputRef.click();
  }

  async handleInput(event: { target: { files: any[]; value: '' } }) {
    const [file] = Array.from(event.target.files);
    const fileName = file.name;
    let contents = {};
    await new Promise(resolve => {
      const reader = new FileReader();
      reader.onload = (e: { target: any }) => {
        try {
          if (this.returnFileInfo) {
            contents = {
              name: fileName,
              fileStr: e.target.result,
              size: file.size,
            };
          } else {
            contents = e.target.result;
          }
          resolve(contents);
          event.target.value = '';
        } catch (e) {
          resolve({});
        }
      };
      if (this.base64) {
        reader.readAsDataURL(file);
      } else {
        reader.readAsText(file, 'UTF-8');
      }
    });
    this.$emit('change', contents);
  }
}
</script>

<style lang="scss" scoped>
.monitor-import {
  position: relative;
  cursor: pointer;

  input[type='file'] {
    position: absolute;
    top: 0;
    left: 0;
    display: none;
    width: 100%;
    height: 100%;
    cursor: pointer;
    opacity: 0;
  }
}
</style>
