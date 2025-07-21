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
  <div
    ref="scrollContainer"
    class="result-scroll-container"
    @scroll.passive="handleScroll"
  >
    <!-- 检索结果 -->
    <div class="result-text">
      <i18n path="检索结果（找到 {0} 条结果，用时{1}毫秒) {2}">
        <span class="total-count">{{ getShowTotalNum(totalCount) }}</span>
        <span>{{ tookTime }}</span>
        <template v-if="showAddMonitor">
          <span>
            ,
            <i18n path="将搜索条件 {0}">
              <a
                class="monitor-link"
                href="javascript:void(0);"
                @click="jumpMonitor"
              >
                {{ $t('添加为监控') }}
                <span class="bklog-icon bklog-lianjie"></span>
              </a>
            </i18n>
          </span>
        </template>
      </i18n>
    </div>
    <div class="result-main">
      <result-chart
        :date-picker-value="datePickerValue"
        :index-set-item="indexSetItem"
        :retrieve-params="retrieveParams"
        @change-queue-res="changeQueueRes"
        @change-total-count="changeTotalCount"
      />
      <bk-divider class="divider-line"></bk-divider>
      <result-table-panel
        ref="resultTablePanel"
        v-bind="$attrs"
        v-on="$listeners"
        :date-picker-value="datePickerValue"
        :index-set-item="indexSetItem"
        :index-set-list="indexSetList"
        :is-page-over="isPageOver"
        :kv-show-fields-list="kvShowFieldsList"
        :origin-table-list="originTableList"
        :queue-status="queueStatus"
        :retrieve-params="retrieveParams"
        :table-list="tableList"
        :total-count="totalCount"
      />
    </div>
    <!-- 滚动到顶部 -->
    <div
      class="fixed-scroll-top-btn"
      v-show="showScrollTop"
      @click="scrollToTop"
    >
      <i class="bk-icon icon-angle-up"></i>
    </div>
  </div>
</template>

<script>
import { setFieldsWidth, parseBigNumberList, formatNumberWithRegex } from '@/common/util';
import tableRowDeepViewMixin from '@/mixins/table-row-deep-view-mixin';
import { mapState, mapGetters } from 'vuex';

import ResultTablePanel from '../result-table-panel';
import ResultChart from './result-chart';

export default {
  components: {
    ResultChart,
    ResultTablePanel,
  },
  mixins: [tableRowDeepViewMixin],
  inheritAttrs: false,
  props: {
    retrieveParams: {
      type: Object,
      required: true,
    },
    tookTime: {
      type: Number,
      required: true,
    },
    tableData: {
      type: Object,
      required: true,
    },
    indexSetList: {
      type: Array,
      required: true,
    },
    datePickerValue: {
      type: Array,
      default: () => [],
    },
    indexSetItem: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      originTableList: [],
      tableList: [],
      throttle: false, // 滚动节流 是否进入cd
      isPageOver: false, // 前端分页加载是否结束
      count: 0, // 数据总条数
      pageSize: 50, // 每页展示多少数据
      currentPage: 1, // 当前加载了多少页
      totalCount: 0,
      scrollHeight: 0,
      limitCount: 0,
      queueStatus: false,
      showScrollTop: false, // 显示滚动到顶部icon
      isInit: false,
      timer: null,
      kvShowFieldsList: [],
    };
  },
  computed: {
    ...mapState({
      bkBizId: state => state.bkBizId,
      isExternal: state => state.isExternal,
    }),
    ...mapGetters({
      isUnionSearch: 'isUnionSearch',
    }),
    showAddMonitor() {
      return (
        !this.isExternal &&
        Boolean(window.MONITOR_URL && this.$store.state.topMenu.some(item => item.id === 'monitor')) &&
        !this.isUnionSearch
      );
    },
  },
  watch: {
    tableData(data) {
      this.finishPolling = data?.finishPolling;
      if (data?.list?.length) {
        if (this.isInit) {
          // 根据接口 data.fields ==> item.max_length 设置各个字段的宽度比例
          setFieldsWidth(this.visibleFields, data.fields, 500);
          this.isInit = true;
        }
        const list = parseBigNumberList(data.list);
        const originLogList = parseBigNumberList(data.origin_log_list);
        this.count += data.list.length;
        this.kvShowFieldsList = Object.keys(data.fields || []);
        this.tableList.push(...list);
        this.originTableList.push(...originLogList);
        this.$nextTick(() => {
          this.$refs.scrollContainer.scrollTop = this.newScrollHeight;
        });
        this.isPageOver = false;
      }
    },
  },
  methods: {
    // 跳转到监控
    jumpMonitor() {
      const indexSetId = this.$route.params.indexId;
      const params = {
        bizId: this.$store.state.bkBizId,
        indexSetId,
        scenarioId: '',
        indexStatement: this.retrieveParams.keyword, // 查询语句
        dimension: [], // 监控维度
        condition: [], // 监控条件
      };
      const indexSet = this.indexSetList.find(item => item.index_set_id === indexSetId);
      if (indexSet) {
        params.scenarioId = indexSet.category_id;
      }
      this.retrieveParams.addition.forEach(item => {
        params.condition.push({
          condition: 'and',
          key: item.field,
          method: item.operator === 'eq' ? 'is' : item.operator,
          value: item.value,
        });
      });
      const urlArr = [];
      for (const key in params) {
        if (key === 'dimension' || key === 'condition') {
          urlArr.push(`${key}=${encodeURI(JSON.stringify(params[key]))}`);
        } else {
          urlArr.push(`${key}=${params[key]}`);
        }
      }
      window.open(`${window.MONITOR_URL}/?${urlArr.join('&')}#/strategy-config/add`, '_blank');
    },
    reset() {
      this.newScrollHeight = 0;
      this.$nextTick(() => {
        this.$refs.scrollContainer.scrollTop = this.newScrollHeight;
      });
      this.count = 0;
      this.currentPage = 1;
      this.originTableList = [];
      this.tableList = [];
      this.isInit = false;
    },
    // 滚动到顶部
    scrollToTop() {
      this.$easeScroll(0, 300, this.$refs.scrollContainer);
    },
    handleScroll() {
      if (this.isPageOver || this.$refs.resultTablePanel.active === 'clustering') {
        return;
      }
      clearTimeout(this.timer);
      this.timer = setTimeout(() => {
        const el = this.$refs.scrollContainer;
        this.showScrollTop = el.scrollTop > 550;
        if (el.scrollHeight - el.offsetHeight - el.scrollTop < 20) {
          if (this.count === this.limitCount || this.finishPolling) return;

          this.isPageOver = true;
          this.currentPage += 1;
          this.newScrollHeight = el.scrollTop;
          this.$emit('request-table-data');
        }
      }, 200);
    },
    changeTotalCount(count) {
      this.totalCount = count;
    },
    changeQueueRes(status) {
      this.queueStatus = status;
    },
    getShowTotalNum(num) {
      return formatNumberWithRegex(num);
    },
  },
};
</script>

<style lang="scss" scoped>
  // @import '../../../scss/mixins/scroller.scss';

  .result-scroll-container {
    height: 100%;
    overflow: auto;

    &::-webkit-scrollbar {
      width: 10px;
      height: 4px;
      background: transparent;
    }

    &::-webkit-scrollbar-thumb {
      background-color: #ddd;
      background-clip: padding-box;
      border-color: transparent;
      border-style: dashed;
      border-left-width: 3px;
      border-radius: 5px;
    }

    &::-webkit-scrollbar-thumb:hover {
      background: #ddd;
    }
  }

  .result-text {
    padding: 10px 20px;
    font-size: 12px;
    color: #63656e;

    .monitor-link {
      color: #3a84ff;
    }

    .total-count {
      color: #f00;
    }
  }

  .result-main {
    min-height: calc(100% - 54px);
    margin: 0 16px 16px;
    background-color: #fff;
  }

  .divider-line {
    /* stylelint-disable-next-line declaration-no-important */
    margin: 0 !important;
  }

  .fixed-scroll-top-btn {
    position: fixed;
    right: 14px;
    bottom: 24px;
    z-index: 2100;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    color: #63656e;
    cursor: pointer;
    background: #f0f1f5;
    border: 1px solid #dde4eb;
    border-radius: 4px;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.2);
    transition: all 0.2s;

    &:hover {
      color: #fff;
      background: #979ba5;
      transition: all 0.2s;
    }

    .bk-icon {
      font-size: 20px;
      font-weight: bold;
    }
  }
</style>
