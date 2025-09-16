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
  <section :class="['log-view', { 'light-view': showType === 'log' }]">
    <pre id="log-content">
      <div
        v-for="(item, index) in escapedReverseLogList"
        class="line"
        v-show="checkLineShow(item, index, 'reverse')"
        :key="index - reverseLogList.length"
        :class="['line', { 'filter-line': lineMatch(item) }]">
        <span class="line-num">{{ index - reverseLogList.length }}</span>
        <HighlightHtml
          :item="item"
          :light-list="getViewLightList"
          :is-show-key="showType === 'log'"
          :ignore-case="ignoreCase"
        />
      </div>
      <div
        v-for="(item, index) in escapedLogList"
        v-show="checkLineShow(item, index, 'normal')"
        :key="index"
        :class="['line', { 'log-init': index === 0, 'new-log-line': newIndex && index >= newIndex, 'filter-line': lineMatch(item) }]">
        <span class="line-num">{{ index }}</span>
        <HighlightHtml
          :item="item"
          :is-show-key="showType === 'log'"
          :light-list="getViewLightList"
          :ignore-case="ignoreCase"
        />
      </div>
    </pre>
  </section>
</template>

<script>
import HighlightHtml from "./highlight-html";

export default {
  name: "LogView",
  components: {
    HighlightHtml,
  },
  props: {
    reverseLogList: {
      type: Array,
      default() {
        return [];
      },
    },
    logList: {
      type: Array,
      default() {
        return [];
      },
    },
    filterKey: {
      type: String,
      default: "",
    },
    isRealTimeLog: {
      type: Boolean,
      default: false,
    },
    maxLength: {
      type: Number,
      default: 0,
    },
    shiftLength: {
      type: Number,
      default: 0,
    },
    interval: {
      type: Object,
      default: () => ({}),
    },
    filterType: {
      type: String,
      default: "",
    },
    ignoreCase: {
      type: Boolean,
      default: false,
    },
    lightList: {
      type: Array,
      default() {
        return [];
      },
    },
    showType: {
      type: String,
      default: "log",
    },
  },
  data() {
    return {
      oldIndex: null,
      newIndex: null,
      intervalTime: null,
      realNewIndexTimer: null,
      resRangeIndexs: [],
      reverseResRangeIndexs: [],
    };
  },
  computed: {
    escapedLogList() {
      return this.logList.map(this.escapeString);
    },
    escapedReverseLogList() {
      return this.reverseLogList.map(this.escapeString);
    },
    isIncludeFilter() {
      return this.filterType === "include";
    },
    getViewLightList() {
      const list = [];
      if (this.filterKey) {
        list.push({
          str: this.filterKey,
          style: "color: #FF5656; font-size: 12px; font-weight: 700;",
          isUnique: true,
        });
      }
      list.push(
        ...this.lightList.map((item) => ({
          str: item.heightKey,
          style: this.getLineColor(item),
          isUnique: false,
        }))
      );
      return list;
    },
  },
  watch: {
    logList: {
      immediate: true,
      handler(val) {
        if (this.isRealTimeLog) {
          // 实时日志记录新增日志索引
          if (this.oldIndex) {
            this.newIndex = this.oldIndex;
            this.oldIndex = val.length;
          } else {
            this.oldIndex = val.length;
          }
          // 超过限制长度的处理
          if (val.length > this.maxLength) {
            this.oldIndex = this.oldIndex - this.shiftLength;
          }
          clearTimeout(this.realNewIndexTimer);
          this.realNewIndexTimer = setTimeout(() => {
            this.newIndex = null;
          }, 5000);
        }
      },
    },
    escapedReverseLogList() {
      if (this.filterKey.length) {
        this.setResRange();
      }
    },
    filterKey(val) {
      if (val.length) {
        this.setResRange();
      } else {
        this.reverseResRangeIndexs.splice(0, this.reverseResRangeIndexs.length);
        this.resRangeIndexs.splice(0, this.resRangeIndexs.length);
      }
    },
    interval: {
      deep: true,
      handler() {
        clearTimeout(this.intervalTime);
        this.intervalTime = setTimeout(() => {
          if (this.filterKey.length) {
            this.setResRange();
          }
        }, 500);
      },
    },
    ignoreCase() {
      this.setResRange();
    },
  },
  methods: {
    checkLineShow(item, index, field) {
      if (this.isIncludeFilter) {
        const list =
          field === "reverse"
            ? this.reverseResRangeIndexs
            : this.resRangeIndexs;
        return this.handleMatch(item) || list.includes(index);
      }
      return this.filterKey.length ? !this.handleMatch(item) : true;
    },
    handleMatch(item) {
      const valStr = Object.values(item).join(" ");
      let { filterKey } = this;
      const keyVal = this.ignoreCase ? valStr : valStr.toLowerCase();
      filterKey = this.ignoreCase ? filterKey : filterKey.toLowerCase();

      return keyVal.includes(filterKey);
    },
    lineMatch(item) {
      if (!this.filterKey) return false;
      return (
        this.handleMatch(item) && Object.values(this.interval).some(Boolean)
      );
    },
    escapeString(item) {
      const map = {
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#x27;": "'",
      };
      const escapeObj = Object.fromEntries(
        Object.entries(item).map(([key, val]) => {
          return [
            [key],
            typeof val !== "string"
              ? String(val ?? " ")
              : val.replace(
                  RegExp(`(${Object.keys(map).join("|")})`, "g"),
                  (match) => map[match]
                ),
          ];
        })
      );
      return escapeObj;
    },
    setResRange() {
      this.resRangeIndexs.splice(0, this.resRangeIndexs.length);
      this.reverseResRangeIndexs.splice(0, this.reverseResRangeIndexs.length);
      const reverListLen = this.escapedReverseLogList.length;
      const listLen = this.escapedLogList.length;
      let resExtra = 0;
      let reverseResExtra = 0;

      // 根据前后行数缓存索引
      this.escapedReverseLogList.forEach((item, index) => {
        if (this.handleMatch(item)) {
          const min = index - Number(this.interval.prev);
          const max = index + Number(this.interval.next);
          const minVal = min < 0 ? 0 : min;
          const maxVal = max >= reverListLen ? reverListLen - 1 : max;

          if (max >= reverListLen) resExtra = Math.abs(max - index);

          for (let i = minVal; i <= maxVal; i++) {
            this.reverseResRangeIndexs.push(i);
          }
        }
      });

      // 根据前后行数缓存索引
      this.escapedLogList.forEach((item, index) => {
        if (this.handleMatch(item)) {
          const min = index - Number(this.interval.prev);
          const max = index + Number(this.interval.next);
          const minVal = min < 0 ? 0 : min;
          const maxVal = max >= listLen ? listLen - 1 : max;

          if (min < 0) reverseResExtra = Math.abs(min);

          for (let i = minVal; i <= maxVal; i++) {
            this.resRangeIndexs.push(i);
          }
        }
      });

      if (resExtra) {
        for (let i = 0; i < resExtra; i++) {
          if (!this.resRangeIndexs.includes(i)) {
            this.resRangeIndexs.push(i);
          }
        }
      }

      if (reverseResExtra) {
        for (let i = 0; i < reverseResExtra; i++) {
          const index = this.escapedReverseLogList.length - i - 1;
          if (!this.reverseResRangeIndexs.includes(index)) {
            this.reverseResRangeIndexs.push(index);
          }
        }
      }
    },
    getLineColor(item) {
      return `background: ${item.color.light}; color: ${
        this.showType === "log" ? "#16171A" : "#313238"
      }; padding: 0 4px; border-radius: 2px; height: 22px; display: inline-block; line-height: 22px; font-weight: 500;`;
    },
  },
};
</script>

<style lang="scss">
@import "../../scss/mixins/clearfix";

.log-view {
  min-height: 100%;
  color: #f0f1f5;
  background: #292929;

  #log-content {
    box-sizing: border-box;
    margin: 0;
    font-size: 0;

    .line {
      display: flex;
      flex-direction: row;
      min-height: 16px;
      padding: 8px 15px 8px 55px;
      margin: 0;
      // font-family: var(--table-fount-family);
      font-family: "Roboto Mono", monospace;
      font-size: 12px;
      line-height: 24px;
      border-top: 1px solid transparent;

      &.log-init {
        background: #3d4d69;
      }

      &.new-log-line {
        background: #1e3023;
      }

      &:hover {
        background: #212121;
      }

      &.filter-line {
        background: #392715;
      }
    }

    .line-num {
      display: inline-block;
      min-width: 38px;
      padding-right: 12px;
      margin-left: -36px;
      line-height: 24px;
      color: #eaebf0;
      text-align: right;
      user-select: none;
      font-weight: 400;
    }

    .line-text {
      line-height: 24px;
      word-break: break-all;
      word-wrap: break-word;
      white-space: pre-wrap;
    }
  }

  &.light-view {
    color: #16171a;
    background: #fff;

    #log-content {
      .line {
        border-top: 1px solid #dcdee5;

        &.log-init {
          background: #f0f5ff;
        }

        &.new-log-line {
          background: #f2fff4;
        }

        &:hover {
          background: #f5f7fa;
        }

        &.filter-line {
          background: #fff3e1;
        }
      }

      .line-num {
        color: #313238;
      }
    }
  }
}
</style>
