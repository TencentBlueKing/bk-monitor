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
  <div class="bklog-column-wrapper">
    <template v-if="isJsonFormat">
      <JsonFormatter
        :fields="field"
        :json-value="formatContent"
        @menu-click="handleJsonSegmentClick"
      ></JsonFormatter>
    </template>
    <template v-else>
      <text-segmentation
        :content="formatContent"
        :field="field"
        :data="row"
        @menu-click="handleJsonSegmentClick"
      />
    </template>
  </div>
</template>

<script>
  import JsonFormatter from '@/global/json-formatter.vue';
  import { mapState } from 'vuex';
  import { formatDate, formatDateNanos } from '@/common/util';
  import { BK_LOG_STORAGE } from '@/store/store.type';

  import TextSegmentation from './text-segmentation';
  export default {
    components: {
      TextSegmentation,
      JsonFormatter,
    },
    props: {
      formatJson: {
        type: Boolean,
        default: false,
      },
      content: {
        type: [String, Number, Boolean],
        required: true,
      },

      field: {
        type: Object,
        required: true,
      },
      row: {
        type: Object,
      },
    },
    data() {
      return {
        isInViewPort: false,
      };
    },
    computed: {
      ...mapState({
        tableLineIsWrap: state => state.storage[BK_LOG_STORAGE.TABLE_LINE_IS_WRAP],
        isFormatDateField: state => state.isFormatDate,
      }),

      isJsonFormat() {
        return this.formatJson && /^\[|\{/.test(this.content);
      },

      formatContent() {
        if (this.isFormatDateField) {
          if (this.field.field_type === 'date') {
            return formatDate(Number(this.content)) || this.content || '--';
          }

          // 处理纳秒精度的UTC时间格式
          if (this.field.field_type === 'date_nanos') {
            return formatDateNanos(this.content) || '--';
          }
        }
        return this.content;
      },
    },
    methods: {
      handleJsonSegmentClick({ isLink, option }) {
        // 为了兼容旧的逻辑，先这么写吧
        // 找时间梳理下这块，写的太随意了
        const { depth, operation, value, isNestedField } = option;
        const operator = operation === 'not' ? 'is not' : operation;
        this.$emit('icon-click', operator, value, isLink, depth, isNestedField); // type, content, field, row, isLink
      },
    },
  };
</script>

<style lang="scss" scoped>
  .bklog-column-wrapper {
    display: flex;
    align-items: flex-start;
    height: fit-content;
    padding: 0;
  }
</style>
