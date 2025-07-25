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
  <div class="select-menu">
    <ul
      class="menu"
      :style="{ minWidth: popoverWidth + 'px' }"
    >
      <li
        v-for="(item, index) in list"
        v-show="!item.hidden"
        :key="index"
        class="menu-item"
        :style="{ 'text-align': align }"
        :disabled="item.disabled"
        :title="item.name"
        @click="!item.disabled && handleMenuClick(item)"
      >
        {{ item.name }}
      </li>
    </ul>
    <div
      v-show="showExtension"
      class="extension"
      @click="handleExtensionClick"
    >
      {{ extensionText }}
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Vue } from 'vue-property-decorator';

export interface IMenu {
  disabled?: boolean;
  hidden?: boolean;
  id: number | string;
  name: string;
  readonly?: boolean;
}

@Component({ name: 'select-menu' })
export default class Menu extends Vue {
  @Prop({ default: () => [], type: Array }) private readonly list!: IMenu[];
  @Prop({ default: 'left', type: String }) private readonly align!: string;
  @Prop({ default: false, type: Boolean }) private readonly showExtension!: boolean;
  @Prop({ default: 84, type: [Number, String] }) private readonly popoverWidth!: number | string;

  private extensionText = window.i18n.t('全部选项');

  @Emit('click')
  private handleMenuClick(item: IMenu) {
    return item;
  }

  @Emit('extension-click')
  private handleExtensionClick() {}
}
</script>
<style lang="scss" scoped>
.menu {
  font-size: 12px;
  padding: 6px 0;
  min-width: 84px;
  background: #fff;
  border: 1px solid #dcdee5;
  max-height: 260px;
  overflow: auto;
  &-item {
    height: 32px;
    line-height: 32px;
    padding: 0 10px;
    cursor: pointer;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    word-break: break-all;
    &:hover {
      background: #f5f6fa;
      color: #3a84ff;
    }
  }
  &-item[disabled] {
    color: #c4c6cc;
    cursor: not-allowed;
  }
}
.extension {
  height: 32px;
  border: 1px solid #dcdee5;
  border-top: 0;
  display: flex;
  align-items: center;
  background-color: #fafbfd;
  padding: 0 15px;
  cursor: pointer;
}
</style>
