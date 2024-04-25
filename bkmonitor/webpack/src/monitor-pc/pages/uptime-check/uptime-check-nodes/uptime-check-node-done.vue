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
  <div class="loading-done">
    <div class="loading-done-body">
      <div
        v-if="config.isLoading"
        class="loading-container"
      >
        <svg
          class="loading-done-svg loading-svg"
          viewBox="0 0 64 64"
        >
          <g>
            <path
              d="M20.7,15c1.6,1.6,1.6,4.1,0,5.7s-4.1,1.6-5.7,0l-2.8-2.8c-1.6-1.6-1.6-4.1,0-5.7s4.1-1.6,5.7,0L20.7,15z"
            />
            <path d="M12,28c2.2,0,4,1.8,4,4s-1.8,4-4,4H8c-2.2,0-4-1.8-4-4s1.8-4,4-4H12z" />
            <path
              d="M15,43.3c1.6-1.6,4.1-1.6,5.7,0c1.6,1.6,1.6,4.1,0,5.7l-2.8,2.8c-1.6,1.6-4.1,1.6-5.7,0s-1.6-4.1,0-5.7L15,43.3z"
            />
            <path d="M28,52c0-2.2,1.8-4,4-4s4,1.8,4,4v4c0,2.2-1.8,4-4,4s-4-1.8-4-4V52z" />
            <path
              d="M51.8,46.1c1.6,1.6,1.6,4.1,0,5.7s-4.1,1.6-5.7,0L43.3,49c-1.6-1.6-1.6-4.1,0-5.7s4.1-1.6,5.7,0L51.8,46.1z"
            />
            <path d="M56,28c2.2,0,4,1.8,4,4s-1.8,4-4,4h-4c-2.2,0-4-1.8-4-4s1.8-4,4-4H56z" />
            <path
              d="M46.1,12.2c1.6-1.6,4.1-1.6,5.7,0s1.6,4.1,0,5.7l0,0L49,20.7c-1.6,1.6-4.1,1.6-5.7,0c-1.6-1.6-1.6-4.1,0-5.7L46.1,12.2z"
            />
            <path d="M28,8c0-2.2,1.8-4,4-4s4,1.8,4,4v4c0,2.2-1.8,4-4,4s-4-1.8-4-4V8z" />
          </g>
        </svg>
        <div class="message-container">
          <h4 class="message-title">
            {{ config.loadingTitle }}
          </h4>
          <p
            v-if="config.loadingText"
            class="message-text"
          >
            {{ config.loadingText }}
          </p>
        </div>
      </div>
      <div
        v-else
        class="result-container"
      >
        <svg
          v-if="config.status"
          class="loading-done-svg success-svg"
          viewBox="0 0 64 64"
        >
          <path
            d="M32,4c15.5,0,28,12.5,28,28S47.5,60,32,60S4,47.5,4,32S16.5,4,32,4z M32,8C18.7,8,8,18.7,8,32c0,13.3,10.7,24,23.9,24.1c6.4,0,12.5-2.5,17.1-7.1c9.4-9.4,9.4-24.6,0.1-33.9c0,0,0,0-0.1-0.1C44.5,10.5,38.4,8,32,8z"
          />
          <polygon points="44,22 47,25 28,44 17,33 20,30 28,38" />
        </svg>
        <svg
          v-else
          class="loading-done-svg fail-svg"
          viewBox="0 0 64 64"
        >
          <g>
            <path
              d="M32,8c13.3,0,24,10.7,24,24S45.3,56,32,56S8,45.3,8,32S18.7,8,32,8 M32,4C16.5,4,4,16.5,4,32s12.5,28,28,28s28-12.5,28-28S47.5,4,32,4z"
            />
            <path
              d="M40.5,20.7l2.8,2.8L34.8,32l8.5,8.5l-2.8,2.8L32,34.8l-8.5,8.5l-2.8-2.8l8.5-8.5l-8.5-8.5l2.8-2.8l8.5,8.5L40.5,20.7z"
            />
          </g>
        </svg>
        <div class="message-container">
          <h4 class="message-title">
            {{ config.statusTitle }}
          </h4>
          <p
            v-if="config.statusText"
            class="message-text"
          >
            {{ config.statusText }}
          </p>
        </div>
      </div>
    </div>
    <div
      v-if="!config.isLoading"
      class="loading-done-footer"
    >
      <bk-button
        v-if="config.isShowCancel"
        class="button-cancel"
        @click="handleCancel"
        >{{ config.cancelText }}</bk-button
      >
      <bk-button
        v-if="config.isShowConfirm"
        theme="primary"
        @click="handleConfirm"
        >{{ config.confirmText }}</bk-button
      >
    </div>
  </div>
</template>

<script>
export default {
  name: 'LoadingDone',
  props: {
    options: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      config: {
        isLoading: true,
        status: true,
        loadingTitle: this.$t('加载中...'),
        loadingText: '',
        statusTitle: this.$t('成功'),
        statusText: '',
        isShowCancel: true,
        isShowConfirm: true,
        cancelText: this.$t('取消'),
        confirmText: this.$t('确定'),
      },
    };
  },
  watch: {
    options: {
      handler(val) {
        this.config = { ...this.config, ...val };
      },
      deep: true,
      immediate: true,
    },
  },
  methods: {
    handleCancel() {
      this.$emit('cancel');
    },
    handleConfirm() {
      this.$router.push({
        name: 'uptime-check-task-add',
      });
      // window.location.href = `${window.site_url}${this.$store.getters.bizId}/uptime_check/summary/`
    },
  },
};
</script>

<style scoped lang="scss">
@import '../../home/common/mixins';

@mixin message-title {
  font-weight: bold;
  height: 21px;
  font-size: 16px;
  color: #000;
  line-height: 21px;
}
@mixin message-text {
  width: auto;
  height: 16px;
  font-size: 12px;
  color: #63656e;
  line-height: 16px;
}

.loading-done {
  display: flex;
  justify-content: center;
  flex-direction: column;
  .loading-done-body {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    .loading-done-svg {
      width: 49px;
      height: 49px;

      @keyframes done-loading {
        0% {
          transform: rotate(0deg);
        }
        100% {
          transform: rotate(-360deg);
        }
      }
      &.loading-svg {
        animation: done-loading 1s linear 0s infinite;
        g {
          @for $i from 1 through 8 {
            :nth-child(#{$i}) {
              fill: $primaryFontColor;
              opacity: #{$i * 0.125};
            }
          }
        }
      }
      &.success-svg {
        fill: #2dcb56;
      }
      &.fail-svg {
        fill: #ea3636;
      }
    }
    .loading-container,
    .result-container {
      display: inline-flex;
      flex-direction: column;
      align-items: center;
    }
    .message-container {
      margin-top: 16px;
      .message-title {
        margin: 0;
        height: 21px;
        line-height: 21px;
        font-size: 16px;
        font-weight: bold;
        color: #313238;
        text-align: center;
      }
      .message-text {
        margin: 12px 0 0 0;
      }
    }
  }
  .loading-done-footer {
    display: flex;
    justify-content: center;
    margin-top: 17px;
    .button-cancel {
      margin-right: 10px;
    }
  }
}
</style>
