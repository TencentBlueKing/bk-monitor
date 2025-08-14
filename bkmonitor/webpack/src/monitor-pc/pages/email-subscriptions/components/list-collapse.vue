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
  <div class="list-collapse-wrap">
    <bk-collapse
      :custom-trigger-area="true"
      :value="activeName"
      @item-click="handleItemClick"
    >
      <bk-collapse-item
        class="list-item"
        name="1"
        :hide-arrow="true"
      >
        <div class="list-header">
          <span
            :class="[
              'icon-monitor',
              'icon-mc-triangle-down',
              { 'icon-mc-triangle-down-hidden': activeName.indexOf('1') === -1 },
            ]"
          />
          <span class="title">{{ title }}</span>
          <slot name="header-btn" />
        </div>
        <div
          slot="content"
          class="list-content"
        >
          <slot name="content" />
        </div>
      </bk-collapse-item>
    </bk-collapse>
  </div>
</template>

<script lang="ts">
import { Component, Emit, Prop, Vue } from 'vue-property-decorator';
/**
 * 邮件订阅列表页
 */
@Component({
  name: 'email-subscriptions',
})
export default class EmailSubscriptions extends Vue {
  @Prop({ default: '', type: String }) private readonly title: string;
  @Prop({ default: [], type: Array }) private readonly activeName: string[];

  @Emit('item-click')
  handleItemClick(arr: string[]) {
    return arr;
  }
}
</script>
<style lang="scss" scoped>
.list-collapse-wrap {
  .list-item {
    :deep(.bk-collapse-item-header),
    :deep(.bk-collapse-item-content) {
      padding: 0;
    }

    .list-header {
      display: flex;
      align-items: center;
      height: 42px;
      padding: 0 16px;
      background: #f0f1f5;
      border: 1px solid #dcdee5;
      // border-bottom: 0;
      border-radius: 2px 2px 0px 0px;

      .icon-mc-triangle-down {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        margin-right: 2px;
        font-size: 24px;

        &::before {
          margin-top: -2px;
        }
      }

      .icon-mc-triangle-down-hidden {
        transform: rotate(-90deg);
      }
    }

    .list-content {
      :deep(.bk-table) {
        /* stylelint-disable-next-line declaration-no-important */
        margin-top: 0 !important;
        border-top: 0;
      }
    }
  }
}
</style>
