<!--
  - Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
  - Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
  - BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
  -
  - License for BK-LOG 蓝鲸日志平台:
  - -------------------------------------------------------------------
  -
  - Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
  - documentation files (the "Software"), to deal in the Software without restriction, including without limitation
  - the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
  - and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
  - The above copyright notice and this permission notice shall be included in all copies or substantial
  - portions of the Software.
  -
  - THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
  - LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
  - NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
  - WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
  - SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
  -->

<template>
  <div
    :class="['td-log-container', { 'is-wrap': isWrap }]"
    @click.stop
  >
    <!-- eslint-disable vue/no-v-html -->
    <span
      v-bk-tooltips="{ content: $t('查看调用链'), disabled: !hasClickEvent, delay: 500 }"
      :class="['field-container', 'add-to', { active: hasClickEvent }]"
      @click.stop="handleClickContent"
    >
      <text-segmentation
        :content="content"
        :field-type="fieldType"
        :menu-click="handleMenuClick"
      />
    </span>
  </div>
</template>

<script>
import TextSegmentation from './text-segmentation';

export default {
  components: {
    TextSegmentation
  },
  props: {
    isWrap: {
      type: Boolean,
      default: false
    },
    content: {
      type: [String, Number, Boolean],
      required: true
    },
    hasClickEvent: {
      type: Boolean,
      default: false
    },
    fieldName: {
      type: String,
      default: ''
    },
    fieldType: {
      type: String,
      default: ''
    }
  },
  data() {
    return {
      isInViewPort: false
    };
  },
  mounted() {
    setTimeout(this.registerObserver, 20);
  },
  beforeDestroy() {
    this.unregisterOberver();
  },
  methods: {
    handleClickContent() {
      if (this.hasClickEvent) this.$emit('contentClick');
    },
    handleMenuClick(option, content, isLink = false) {
      const operator = option === 'not' ? 'is not' : option;
      this.$emit('iconClick', operator, content, isLink);
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
            if (entry.boundingClientRect.height > 72) this.$emit('computedHeight');
          }
        });
      });
      this.intersectionObserver.observe(this.$el);
    }
  }
};
</script>

<style lang="scss" scoped>
.td-log-container {
  position: relative;
  line-height: 21px;

  &.is-wrap {
    padding-bottom: 3px;
  }

  .field-container {
    &.active:hover {
      color: #3a84ff;
      cursor: pointer;
    }

    &.mark {
      color: black;
      background: #f3e186;
    }
  }

  .icon-search-container {
    display: none;
    width: 14px;
    height: 14px;
    margin-left: 5px;
    vertical-align: bottom;
    cursor: pointer;
    background: #3a84ff;
    justify-content: center;
    align-items: center;

    .icon {
      font-size: 12px;
      font-weight: bold;
      color: #fff;
      background: #3a84ff;
      transform: scale(0.6);

      &.icon-copy {
        font-size: 14px;
        transform: scale(1);
      }
    }
  }

  &:hover {
    .icon-search-container {
      display: inline-flex;
    }
  }
}
</style>
