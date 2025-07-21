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
  <div ref="shadowHost">
    <slot v-if="!shadowContent"></slot>
  </div>
</template>

<script>
import Vue from 'vue';

export default {
  name: 'ShadowWrapper',
  props: {
    shadowContent: {
      type: Boolean,
      default: true,
    },
  },
  mounted() {
    this.setupShadowDom();
  },
  updated() {
    this.setupShadowDom();
  },
  methods: {
    setupShadowDom() {
      if (!this.shadowContent) {
        return;
      }

      if (!this.shadowRoot) {
        this.shadowRoot = this.$refs.shadowHost.attachShadow({ mode: 'open' });
      } else {
        // 清理先前的内容
        while (this.shadowRoot.firstChild) {
          this.shadowRoot.firstChild.remove();
        }
      }

      // 缓存插槽内容的 VNode
      const slotContent = this.$slots.default;

      // 延迟渲染插槽内容，通过 Vue 的 nextTick 确保 DOM 已经完全更新
      this.$nextTick(() => {
        new Vue({
          parent: this.$parent,
          render: h => h('div', { class: 'shadow-container' }, slotContent),
        }).$mount(this.shadowRoot.appendChild(document.createElement('div')));
      });
    },
  },
};
</script>

<style scoped>
  /* ShadowWrapper 组件自身的样式 */
  .shadow-container {
    all: initial;

    /* 确保样式隔离 */
    display: inline-block;
  }
</style>
