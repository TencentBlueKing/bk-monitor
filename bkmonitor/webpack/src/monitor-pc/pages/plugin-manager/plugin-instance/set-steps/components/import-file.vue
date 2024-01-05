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
  <monitor-import
    :class="['import-file-wrap', { 'is-error': errMessage }]"
    :return-file-info="true"
    @change="handleFileImport"
    :accept="accept"
    :base64="base64"
  >
    <span
      v-show="!fileContent"
      class="placeholder"
    >{{ localPlaceholder }}</span>
    <span
      v-show="fileContent"
      class="file-name"
    >{{ fileName }}</span>
    <bk-icon
      class="clear-icon"
      type="close-circle-shape"
      style="font-size: 14px"
      v-show="fileContent"
      @click.stop="handleDel"
    />
  </monitor-import>
</template>
<script lang="ts">
import { Component, Emit, Prop, Vue } from 'vue-property-decorator';


import MonitorImport from '../../../../../components/monitor-import/monitor-import.vue';

interface IFileInfo {
  name: string;
  fileStr: string;
  size: number;
}
@Component({
  name: 'ImputFile',
  components: {
    MonitorImport
  }
})
export default class ImportFile extends Vue {
  @Prop({ default: '', type: String }) fileName: string;
  @Prop({ default: '', type: String }) fileContent: string;
  @Prop({ default: true, type: Boolean }) base64: string;
  @Prop({ default: '', type: String }) placeholder: string;
  @Prop({ default: '', type: String }) accept: string;

  errMessage = '';

  @Emit('change')
  emitFileInfo(v) {
    return v;
  }

  @Emit('error-message')
  emitMessage() {
    return this.errMessage;
  }

  get localPlaceholder() {
    let placeholder = '';
    const maxSize = +this.$store.getters.collectingConfigFileMaxSize || 0;
    // 请提交文件，文件大小不能超过2M！
    placeholder = this.$i18n.t('提交文件，文件大小不能超过{num}M！', { num: maxSize }) as string;
    return this.placeholder || placeholder;
  }

  handleFileImport(fileInfo: IFileInfo) {
    const maxSize = this.$store.getters.collectingConfigFileMaxSize;
    const fileSize = fileInfo.size / 1024 / 1024;
    if (maxSize && fileSize > maxSize) {
      this.errMessage = this.$t('文件大小不能超过{num}M！', { num: maxSize }) as string;
    } else {
      this.errMessage = '';
    }
    this.emitMessage();
    this.emitFileInfo({
      name: fileInfo.name,
      fileContent: this.base64 ? fileInfo.fileStr.replace(/^data:[\S]+;base64,/, '') : fileInfo.fileStr
    });
  }
  handleDel() {
    this.errMessage = '';
    this.emitMessage();
    this.emitFileInfo({
      name: '',
      fileContent: ''
    });
  }
}
</script>

<style lang="scss" scoped>
.import-file-wrap {
  position: relative;
  justify-content: start;
  width: 100%;
  height: 100%;
  padding: 0 10px;
  padding-right: 29px;
  margin: 0;
  font-size: 12px;
  border: 1px solid #c4c6cc;
  border-radius: 2px;

  .placeholder {
    color: #c4c6cc;
  }

  .file-name {
    color: #63656e;
  }

  .clear-icon {
    position: absolute;
    top: 50%;
    right: 7px;
    width: 14px;
    height: 14px;
    font-size: 14px;
    color: #c4c6cc;
    border-radius: 50%;
    transform: translateY(-50%);
  }
}

.is-error {
  border-color: #ff5656;

  .clear-icon {
    right: 3px;
  }
}
</style>
