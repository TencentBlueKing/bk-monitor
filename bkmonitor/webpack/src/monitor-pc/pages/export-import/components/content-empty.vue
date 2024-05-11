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
  <article>
    <!--空数据-->
    <section class="content-empty">
      <span class="empty-icon"
        ><i
          class="icon-monitor"
          :class="icon"
      /></span>
      <span class="empty-drop">{{ title }}</span>
      <span
        v-if="subTitle"
        class="empty-tip"
        >{{ subTitle }}</span
      >
    </section>
  </article>
</template>
<script>
export default {
  name: 'ContentEmpty',
  props: {
    // icon
    icon: {
      type: String,
      default: 'icon-hint',
    },
    // title
    title: {
      type: String,
      default() {
        return this.$t('无数据');
      },
    },
    // subtitle
    subTitle: {
      type: String,
      default: '',
    },
  },
};
</script>
<style lang="scss" scoped>
@import '../../../theme/index';

$emptyTipColor: #979ba5;

@mixin layout-flex($flexDirection: row, $alignItems: stretch, $justifyContent: flex-start) {
  display: flex;
  flex-direction: $flexDirection;
  align-items: $alignItems;
  justify-content: $justifyContent;
}

.content-empty {
  @include layout-flex(column, center);
  .empty-icon {
    height: 42px;
    width: 42px;
    font-size: 42px;
    color: $slightFontColor;
  }
  .empty-drop {
    margin-top: 6px;
    line-height: 19px;
    font-size: 14px;
    font-weight: bold;
    color: $defaultFontColor;
  }
  .empty-tip {
    margin-top: 6px;
    line-height: 16px;
    color: $emptyTipColor;
  }
}
</style>
