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
      <div class="loading-done-container">
        <div
          v-if="config.loading"
          class="loading-container"
        >
          <svg
            class="loading-svg"
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
        </div>
        <div
          v-else
          class="done-container"
        >
          <i
            v-if="config.status"
            class="icon-monitor icon-duihao success"
          />
          <i
            v-else
            class="icon-monitor icon-chahao error"
          />
        </div>
      </div>
      <div class="message-container">
        <div class="message-title">
          {{ config.title }}
        </div>
        <div
          v-if="config.showText"
          class="message-text-container"
        >
          <slot name="text">
            <p class="message-text">
              {{ config.text }}
            </p>
          </slot>
        </div>
      </div>
    </div>
    <div
      v-if="config.showFooter"
      class="loading-done-footer"
    >
      <slot name="footer" />
    </div>
  </div>
</template>

<script>
export default {
  name: 'LoadingDone',
  props: {
    options: {
      type: Object,
      default: () => {},
    },
  },
  data() {
    return {
      config: {
        loading: true,
        status: true,
        title: this.$t('加载中...'),
        text: this.$t('加载中...'),
        showFooter: true,
        showText: true,
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
};
</script>

<style scoped lang="scss">
.loading-done {
  display: flex;
  justify-content: center;
  flex-direction: column;

  .loading-done-body {
    display: flex;
    flex-direction: column;
    align-items: center;

    .loading-done-container {
      width: 56px;
      height: 56px;

      .loading-container {
        width: 56px;
        height: 56px;

        @keyframes loading-ratate {
          0% {
            transform: rotate(0deg);
          }

          100% {
            transform: rotate(-360deg);
          }
        }

        .loading-svg {
          animation: loading-ratate 1s linear 0s infinite;

          g {
            @for $i from 1 through 8 {
              :nth-child(#{$i}) {
                fill: #3a84ff;
                opacity: #{$i * 0.125};
              }
            }
          }
        }
      }

      .done-container {
        text-align: center;

        .success {
          font-size: 56px;
          color: #2dcb56;
        }

        .error {
          font-size: 56px;
          color: #ea3636;
        }
      }
    }

    .message-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      margin-top: 17px;

      .message-title {
        height: 21px;
        line-height: 21px;
        font-size: 16px;
        font-weight: bold;
        color: #000;
      }

      .message-text-container {
        margin-top: 10px;

        .message-text {
          height: 16px;
          margin: 0;
          line-height: 16px;
          font-size: 12px;
          color: #63656e;
        }
      }
    }
  }

  p {
    margin: 0;
    color: #63656e;
  }

  .loading-done-footer {
    display: flex;
    justify-content: center;
    margin-top: 36px;
  }
}
</style>
