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
  <div class="bklog-column-container">
    <!-- eslint-disable vue/no-v-html -->
    <span
      v-bk-tooltips="{ content: $t('查看调用链'), delay: 500 }"
      :class="['field-container', 'add-to']"
    >
      <template v-if="isJsonFormat">
        <JsonFormatter
          :jsonValue="content"
          :fields="field"
          @menu-click="handleJsonSegmentClick"
        ></JsonFormatter>
      </template>
      <template v-else>
        <text-segmentation
          :content="content"
          :field="field"
          @menu-click="handleJsonSegmentClick"
        />
      </template>
    </span>
  </div>
</template>

<script>
import { mapState } from 'vuex';
import TextSegmentation from './text-segmentation';
import JsonFormatter from '@/global/json-formatter.vue';

import { BK_LOG_STORAGE } from '../../../store/store.type';

export default {
  components: {
    TextSegmentation,
    JsonFormatter,
  },
  props: {
    content: {
      type: [String, Number, Boolean],
      required: true,
    },

    field: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      isInViewPort: false,
    };
  },
  computed: {
    ...mapState({
      formatJson: state => state.storage[BK_LOG_STORAGE.TABLE_JSON_FORMAT],
      tableLineIsWrap: state => state.storage[BK_LOG_STORAGE.TABLE_LINE_IS_WRAP],
    }),

    isJsonFormat() {
      return this.formatJson && /^\[|\{/.test(this.content);
    },
  },
  mounted() {
    setTimeout(this.registerObserver, 20);
  },
  beforeUnmount() {
    this.unregisterOberver();
  },
  methods: {
    handleJsonSegmentClick({ isLink, option }) {
      // 为了兼容旧的逻辑，先这么写吧
      // 找时间梳理下这块，写的太随意了
      const { depth, operation, value } = option;
      const operator = operation === 'not' ? 'is not' : operation;
      this.$emit('icon-click', operator, value, isLink, depth); // type, content, field, row, isLink
    },
    unregisterOberver() {
      if (this.intersectionObserver) {
        this.intersectionObserver.unobserve(this.$el);
        this.intersectionObserver.disconnect();
        this.intersectionObserver = null;
      }
    },
    // 注册Intersection监听
    registerObserver() {
      if (this.intersectionObserver) {
        this.unregisterOberver();
      }
      this.intersectionObserver = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (this.intersectionObserver) {
            if (entry.boundingClientRect.height > 72) this.$emit('computed-height');
          }
        });
      });
      this.intersectionObserver?.observe(this.$el);
    },
  },
};
</script>

<style lang="scss" scoped>
  .bklog-column-container {
    padding: 8px 0;
  }
</style>
