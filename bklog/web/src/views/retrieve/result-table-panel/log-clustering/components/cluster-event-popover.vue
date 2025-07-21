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
  <bk-popover
    ref="eventPopover"
    ext-cls="event-tippy"
    :class="['retrieve-event-popover', { 'is-inline': !isCluster }]"
    :on-hide="handlePopoverHide"
    :on-show="handlePopoverShow"
    :placement="placement"
    :tippy-options="tippyOptions"
    :trigger="trigger"
    theme="light"
  >
    <slot />
    <template #content>
      <div class="event-icons">
        <div
          v-if="isCluster"
          class="event-box"
        >
          <span
            class="event-btn"
            @click="handleClick('show original')"
          >
            <i class="icon bk-icon icon-eye"></i>
            <span>{{ $t('查询命中pattern的日志') }}</span>
          </span>
          <div
            class="new-link"
            v-bk-tooltips="$t('新开标签页')"
            @click.stop="handleClick('show original', true)"
          >
            <i class="bklog-icon bklog-jump"></i>
          </div>
        </div>
        <div class="event-box">
          <span
            class="event-btn"
            @click="handleClick('copy')"
          >
            <i class="icon bklog-icon bklog-copy"></i>
            <span>{{ $t('复制') }}</span>
          </span>
        </div>
      </div>
    </template>
  </bk-popover>
</template>

<script>
export default {
  props: {
    placement: {
      type: String,
      default: 'bottom',
    },
    trigger: {
      type: String,
      default: 'click',
    },
    isCluster: {
      type: Boolean,
      default: true,
    },
    tippyOptions: {
      type: Object,
      default: () => {},
    },
    context: {
      type: String,
      require: true,
    },
  },
  computed: {
    isHavePattern() {
      return this.context !== '';
    },
  },
  methods: {
    handleClick(id, isLink = false) {
      this.$emit('event-click', id, isLink);
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
            if (entry.intersectionRatio <= 0) {
              this.$refs.eventPopover.instance.hide();
            }
          }
        });
      });
      this.intersectionObserver.observe(this.$el);
    },
    handlePopoverShow() {
      setTimeout(this.registerObserver, 20);
    },
    handlePopoverHide() {
      this.unregisterOberver();
    },
  },
};
</script>

<style lang="scss">
  @import '@/scss/mixins/flex.scss';

  .event-tippy {
    .event-icons {
      flex-direction: column;

      @include flex-center();
    }

    .event-box {
      min-width: 240px;
      height: 32px;
      padding: 0 10px;
      font-size: 12px;
      cursor: pointer;

      @include flex-center();

      &:hover {
        background: #eaf3ff;
      }
    }

    .new-link {
      width: 24px;
      height: 24px;

      @include flex-center();

      &:hover {
        color: #3a84ff;
      }
    }

    .event-btn {
      flex: 1;
      align-items: center;

      @include flex-justify(left);

      &:hover {
        color: #3a84ff;
      }
    }

    .tippy-tooltip {
      padding: 6px 2px;
    }

    .icon {
      display: inline-block;
      font-size: 14px;
      cursor: pointer;
    }

    .icon-eye {
      margin-right: 6px;
    }

    .icon-copy {
      margin-left: -4px;
      font-size: 24px;
    }

    .icon-copy:before {
      content: '\e109';
    }
  }

  .retrieve-event-popover {
    .bk-tooltip-ref {
      cursor: pointer;

      &:hover {
        color: #3a84ff;
      }
    }

    mark {
      color: #313238;
      background: #f0f1f5;
    }

    &.is-inline {
      display: inline;

      .bk-tooltip-ref {
        display: inline;
      }

      .tippy-tooltip {
        padding-left: 0;
      }
    }
  }
</style>
