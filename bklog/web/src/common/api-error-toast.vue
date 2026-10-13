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
  <transition name="bk-message-fade">
    <div
      v-show="visible"
      class="bk-message bk-message-error bklog-api-error-message"
    >
      <i class="bk-message-icon bk-icon icon-close-circle-shape"></i>
      <div class="bk-message-content">
        <div class="bklog-api-error-message__title">{{ title }}</div>
        <div class="bklog-api-error-message__suggestion">{{ suggestion }}</div>
        <div
          v-if="requestId || original"
          class="bklog-api-error-message__meta"
        >
          <span v-if="requestId">{{ $t('请求 ID：{n}', { n: requestId }) }}</span>
          <button
            v-if="original"
            class="bklog-api-error-message__detail"
            type="button"
            @click="expanded = !expanded"
          >
            {{ expanded ? $t('收起详情') : $t('查看详情') }}
          </button>
        </div>
        <pre
          v-if="expanded && original"
          class="bklog-api-error-message__original"
          >{{ original }}</pre
        >
      </div>
      <div
        class="bk-message-close"
        @click.stop="close"
      >
        <i class="bk-icon icon-close"></i>
      </div>
    </div>
  </transition>
</template>

<script>
  export default {
    name: 'ApiErrorToast',
    props: {
      title: {
        type: String,
        default: '',
      },
      suggestion: {
        type: String,
        default: '',
      },
      requestId: {
        type: String,
        default: '',
      },
      original: {
        type: String,
        default: '',
      },
      delay: {
        type: Number,
        default: 12000,
      },
    },
    data() {
      return {
        visible: false,
        expanded: false,
        timer: null,
      };
    },
    watch: {
      expanded(val) {
        if (val) {
          this.clearTimer();
        } else {
          this.startTimer();
        }
      },
    },
    mounted() {
      this.visible = true;
      this.startTimer();
    },
    beforeDestroy() {
      this.clearTimer();
    },
    methods: {
      startTimer() {
        this.clearTimer();
        if (this.expanded || this.delay <= 0) {
          return;
        }
        this.timer = window.setTimeout(() => {
          this.close();
        }, this.delay);
      },
      clearTimer() {
        if (this.timer) {
          window.clearTimeout(this.timer);
          this.timer = null;
        }
      },
      close() {
        this.clearTimer();
        this.visible = false;
        window.setTimeout(() => {
          this.$emit('closed');
        }, 300);
      },
    },
  };
</script>

<style lang="scss">
  .bklog-api-error-message {
    z-index: 9999;
    max-width: 560px;

    .bk-message-content {
      display: block;
      max-width: 500px;
      overflow: visible;
      line-height: 20px;
      white-space: normal;
    }

    &__title {
      font-weight: 700;
    }

    &__suggestion {
      margin-top: 4px;
    }

    &__meta {
      margin-top: 8px;
      font-size: 12px;
      line-height: 18px;
      color: #63656e;
    }

    &__detail {
      padding: 0;
      margin-left: 8px;
      color: #3a84ff;
      cursor: pointer;
      background: transparent;
      border: 0;
    }

    &__original {
      max-height: 160px;
      padding: 8px;
      margin: 8px 0 0;
      overflow: auto;
      font-size: 12px;
      line-height: 18px;
      color: #63656e;
      word-break: break-all;
      white-space: pre-wrap;
      background: #f5f7fa;
      border-radius: 2px;
    }
  }
</style>
