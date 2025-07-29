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
  <div class="page-tips-wrap">
    <span class="icon-monitor icon-tips" />
    <span class="text">
      {{ tipsText }}
      <span
        class="link"
        @click="handleOpenLink(linkUrl)"
        >{{ linkText }}</span
      >
      <span
        v-if="docLink"
        class="link"
        @click="handleGotoLink(docLink)"
        >{{ $t('相关文档查看') }}</span
      >
    </span>
  </div>
</template>
<script lang="ts">
import { Component, Mixins, Prop } from 'vue-property-decorator';

import documentLinkMixin from '../../mixins/documentLinkMixin';

@Component({
  name: 'page-tips',
})
export default class PageTips extends Mixins(documentLinkMixin) {
  @Prop({ default: '', type: String }) private readonly tipsText: string;
  @Prop({ default: '', type: String }) private readonly linkText: string;
  @Prop({ default: '', type: String }) private readonly linkUrl: string;
  @Prop({ default: '', type: String }) private readonly docLink: string;

  public handleOpenLink(url: string) {
    window.open(url, '_blank');
  }
}
</script>
<style lang="scss" scoped>
.page-tips-wrap {
  display: flex;
  align-items: center;
  min-height: 32px;
  padding: 0 10px;
  font-size: 0;
  background: #f0f8ff;
  border: 1px solid #c5daff;
  border-radius: 2px;

  span {
    font-size: 12px;
  }

  .icon-tips {
    display: flex;
    align-items: center;
    margin-right: 8px;
    font-size: 16;
    color: #3a84ff;
  }

  .text {
    padding: 7px 0;
    margin-right: 4px;
    line-height: 16px;
  }

  .link {
    margin-right: 4px;
    color: #3a84ff;
    white-space: nowrap;
    cursor: pointer;
  }
}
</style>
