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
  <span class="log-content-wrapper">
    <span class="null-item" v-if="isVirtual">{{ content }}</span>
    <span
      v-else-if="!isNeedSegment"
      class="valid-text">
      <template v-for="(item, index) in markItem">
        <mark v-if="item.isMark" :key="index" @click="handleClick($event, item.str)">{{item.str}}</mark>
        <span class="null-item" v-else :key="index" @click="handleClick($event, item.str)">{{item.str}}</span>
      </template>
    </span>
    <span v-else class="segment-content">
      <template v-for="(item, index) in splitList">
        <!-- 换行 -->
        <br :key="index" v-if="item === '\n'">
        <!-- 分割符 -->
        <template v-else-if="segmentReg.test(item)">{{item}}</template>
        <!-- 高亮 -->
        <mark
          :key="index"
          v-else-if="checkMark(item)"
          @click="handleClick($event, item)">{{item}}</mark>
        <!-- 可操作分词 -->
        <span
          :key="index"
          v-else-if="index < (segmentLimitIndex)"
          class="valid-text"
          @click="handleClick($event, item)">{{item}}</span>
        <template v-else>{{item}}</template>
      </template>
    </span>

    <div v-show="false">
      <div ref="moreTools" class="event-icons">
        <div class="event-box">
          <span class="event-btn" @click="handleMenuClick('copy')">
            <i class="icon log-icon icon-copy"></i>
            <span>{{ $t('复制') }}</span>
          </span>
        </div>
        <div class="event-box">
          <span class="event-btn" @click="handleMenuClick('is')">
            <i class="icon bk-icon icon-plus-circle"></i>
            <span>{{ $t('添加到本次检索') }}</span>
          </span>
          <div
            class="new-link"
            v-bk-tooltips="$t('新开标签页')"
            @click.stop="handleMenuClick('is', true)">
            <i class="log-icon icon-jump"></i>
          </div>
        </div>
        <div class="event-box">
          <span class="event-btn" @click="handleMenuClick('not')">
            <i class="icon bk-icon icon-minus-circle"></i>
            <span>{{ $t('从本次检索中排除') }}</span>
          </span>
          <div
            class="new-link"
            v-bk-tooltips="$t('新开标签页')"
            @click.stop="handleMenuClick('not', true)">
            <i class="log-icon icon-jump"></i>
          </div>
        </div>
      </div>
    </div>
  </span>
</template>

<script>

export default {
  props: {
    content: {
      type: [String, Number],
      required: true,
    },
    fieldType: {
      type: String,
      default: '',
    },
    menuClick: Function,
  },
  data() {
    return {
      curValue: '', // 当前选中分词
      segmentReg: /<mark>(.*?)<\/mark>|([,&*+:;?^=!$<>'"{}()|[\]/\\|\s\r\n\t]|[-])/,
      originalMarkReg: /<mark>(.*?)<\/mark>/g,
      segmentLimitIndex: 0, // 分词超出最大数量边界下标
      limitCount: 256, // 支持分词最大数量
      currentEvent: null,
      intersectionObserver: null,
    };
  },
  computed: {
    isNeedSegment() {
      return ['text'].includes(this.fieldType);
    },
    isVirtual() {
      return this.fieldType === '__virtual__';
    },
    splitList() {
      const value = this.content;
      let arr = value.split(this.segmentReg);
      arr = arr.filter(val => val && val.length);
      this.getLimitValidIndex(arr);
      return arr;
    },
    markList() {
      let markVal = this.content.toString().match(/(<mark>).*?(<\/mark>)/g) || [];
      if (markVal.length) {
        markVal = markVal.map(item => item.replace(/<mark>/g, '')
          .replace(/<\/mark>/g, ''));
      }
      return markVal;
    },
    /** 检索的高亮列表 */
    markItem() {
      let splitList = this.content
        .toString()
        .split(this.originalMarkReg)
        .filter(Boolean)
        .map(item => ({
          str: item,
          isMark: false,
        }));
      // 过滤切割的数组 判断所有的值filter(Boolean)清空所有空字符串后 若为空数组 则补一个空字符串展示位
      if (!splitList.length) splitList = [{
        str: '',
        isMark: false,
      }];
      let markVal = this.content.toString().match(this.originalMarkReg);
      if (markVal?.length) {
        splitList.forEach((el) => {
          markVal = markVal.map(item => item.replace(/<mark>/g, '').replace(/<\/mark>/g, ''));
          markVal.includes(el.str) && (el.isMark = true); // 给匹配到的数据 mark高亮设置为true
        });
      }
      return splitList;
    },
  },
  beforeDestroy() {
    this.handleDestroy();
  },
  methods: {
    /**
     * @desc 获取限制最大分词数下标
     * @param { Array } list
     */
    getLimitValidIndex(list) {
      let segmentCount = 0;
      this.segmentLimitIndex = 0;
      for (let index = 0; index < list.length; index++) {
        this.segmentLimitIndex += 1;
        if (!this.segmentReg.test(list[index])) {
          segmentCount += 1;
        }
        if (segmentCount > this.limitCount) break;
      }
    },
    formatterStr(content) {
      // 匹配高亮标签
      let value = content;
      if (this.markList.length) {
        value = String(value).replace(/<mark>/g, '')
          .replace(/<\/mark>/g, '');
      }

      return value;
    },
    handleDestroy() {
      if (this.popoverInstance) {
        this.popoverInstance?.hide(0);
        this.popoverInstance?.destroy();
        this.popoverInstance = null;
        this.curValue = '';
      }
    },
    handleClick(e, value) {
      if (!value.toString()) return;
      this.handleDestroy();
      this.curValue = value;
      this.popoverInstance = this.$bkPopover(e.target, {
        content: this.$refs.moreTools,
        trigger: 'click',
        placement: 'bottom-start',
        arrow: true,
        theme: 'light',
        interactive: true,
        extCls: 'event-tippy-content',
        onHidden: () => {
          this.unregisterObserver();
          this.popoverInstance && this.popoverInstance.destroy();
          this.popoverInstance = null;
          this.currentEvent.classList.remove('focus-text');
        },
        onShow: () => {
          setTimeout(this.registerObserver, 20);
          this.currentEvent = e.target;
          this.currentEvent.classList.add('focus-text');
        },
      });
      this.popoverInstance && this.popoverInstance.show(10);
    },
    // 注册Intersection监听
    registerObserver() {
      if (this.intersectionObserver) this.unregisterObserver();
      this.intersectionObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (this.intersectionObserver) {
            if (entry.intersectionRatio <= 0) {
              this.popoverInstance.hide();
            }
          }
        });
      });
      this.intersectionObserver.observe(this.$el);
    },
    unregisterObserver() {
      if (this.intersectionObserver) {
        this.intersectionObserver.unobserve(this.$el);
        this.intersectionObserver.disconnect();
        this.intersectionObserver = null;
      }
    },
    checkMark(splitItem) {
      if (!this.markList.length) return false;
      // 以句号开头或句号结尾的分词符匹配成功也高亮展示
      return this.markList.some(item => item === splitItem
       || splitItem.startsWith(`.${item}`)
       || splitItem.endsWith(`${item}.`),
      );
    },
    handleMenuClick(event, isLink = false) {
      this.menuClick(event, this.curValue, isLink);
      this.handleDestroy();
    },
  },
};
</script>

<style lang="scss">
@import '@/scss/mixins/flex.scss';

.event-tippy-content {
  .event-icons {
    flex-direction: column;

    @include flex-center();
  }

  .event-box {
    height: 32px;
    min-width: 240px;
    font-size: 12px;
    padding: 0 10px;
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

  .icon-minus-circle,
  .icon-plus-circle {
    margin-right: 6px;
  }

  .icon-copy {
    margin-left: -4px;
    font-size: 24px;
  }
}

.log-content-wrapper {
  word-break: break-all;

  .segment-content {
    white-space: normal;
  }

  .menu-list {
    display: none;
    position: absolute;
  }

  .valid-text {
    cursor: pointer;

    &.focus-text,
    &:hover {
      color: #3a84ff;
    }
  }

  .null-item {
    min-width: 6px;
    display: inline-block;
  }
}
</style>
