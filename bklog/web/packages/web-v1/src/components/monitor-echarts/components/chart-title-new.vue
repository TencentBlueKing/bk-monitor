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
  <div class="title-wrapper-new">
    <div
      ref="chartTitle"
      class="chart-title"
      tabindex="0"
    >
      <div class="main-title">
        <div
          class="title-click"
          @click.stop="handleShowMenu"
        >
          <span
            class="bk-icon icon-down-shape"
            :class="{ 'is-flip': isFold }"
          ></span>
          <div class="title-name">{{ title }}</div>
          <i18n
            class="time-result"
            path="检索结果（找到 {0} 条结果，用时{1}毫秒) {2}"
          >
            <span class="total-count">{{ getShowTotalNum(totalCount) }}</span>
            <span>{{ tookTime }}</span>
          </i18n>
        </div>
        <div
          v-if="!isEmptyChart && !isFold"
          class="converge-cycle"
          @click.stop
        >
          <span>{{ $t('汇聚周期') }}</span>
          <bk-select
            style="width: 80px"
            ext-cls="select-custom"
            v-model="chartInterval"
            :clearable="false"
            behavior="simplicity"
            data-test-id="generalTrendEcharts_div_selectCycle"
            size="small"
            @change="handleIntervalChange"
          >
            <bk-option
              v-for="option in intervalArr"
              :id="option.id"
              :key="option.id"
              :name="option.name"
            >
            </bk-option>
          </bk-select>
        </div>
      </div>
      <div
        v-if="subtitle"
        class="sub-title"
      >
        {{ subtitle }}
      </div>
    </div>
    <bk-spin
      v-if="loading && !isFold"
      class="chart-spin"
    ></bk-spin>
    <!-- <div
      v-else-if="!isFold"
      class="menu-list"
    >
      <span
        class="bklog-icon bklog-xiangji"
        data-test-id="generalTrendEcharts_span_downloadEcharts"
        @click.stop="handleMenuClick({ id: 'screenshot' })"
      >
      </span>
    </div> -->
    <!-- <chart-menu
      v-show="showMenu"
      :list="menuList"
      @menu-click="handleMenuClick"
      :style="{ left: menuLeft + 'px' }">
    </chart-menu> -->
  </div>
</template>

<script lang="ts">
  import { Component, Vue, Prop, Ref, Watch } from 'vue-property-decorator';
  import { formatNumberWithRegex } from '@/common/util';
  import useStore from '@/hooks/use-store';
  import { BK_LOG_STORAGE } from '@/store/store.type.ts';

  import ChartMenu from './chart-menu.vue';

  const store = useStore();

  @Component({
    name: 'chart-title',
    components: {
      ChartMenu,
    },
  })
  export default class ChartTitle extends Vue {
    @Prop({ default: '' }) title: string;
    @Prop({ default: '' }) subtitle: string;
    @Prop({ default: () => [] }) menuList: string[];
    @Prop({ default: store.state.storage[BK_LOG_STORAGE.TREND_CHART_IS_FOLD] }) isFold: boolean;
    @Prop({ default: true }) loading: boolean;
    @Prop({ default: true }) isEmptyChart: boolean;
    @Prop({ required: true }) totalCount: number;
    @Ref('chartTitle') chartTitleRef: HTMLDivElement;

    chartInterval = 'auto';
    intervalArr = [
      { id: 'auto', name: 'auto' },
      { id: '1m', name: '1 min' },
      { id: '5m', name: '5 min' },
      { id: '1h', name: '1 h' },
      { id: '1d', name: '1d' },
    ];

    get retrieveParams() {
      return this.$store.state.retrieveParams;
    }

    get tookTime() {
      return this.$store.state.tookTime;
    }

    @Watch('retrieveParams.interval')
    watchChangeChartInterval(newVal) {
      this.chartInterval = newVal;
    }

    handleShowMenu(e: MouseEvent) {
      this.$emit('toggle-expand', !this.isFold);

      // this.showMenu = !this.showMenu
      // const rect = this.chartTitleRef.getBoundingClientRect()
      // this.menuLeft = rect.width  - 185 < e.layerX ? rect.width  - 185 : e.layerX
    }
    getShowTotalNum(num) {
      return formatNumberWithRegex(num);
    }
    handleMenuClick(item) {
      this.$emit('menu-click', item);
    }
    // 汇聚周期改变
    handleIntervalChange() {
      this.$emit('interval-change', this.chartInterval);
      this.$store.commit('retrieve/updateChartKey');
    }
  }
</script>
<style lang="scss" scoped>
  .title-wrapper-new {
    position: relative;
    z-index: 999;
    flex: 1;
    width: 100%;

    .converge-cycle {
      display: flex;
      align-items: center;
      margin-left: 14px;
      font-size: 12px;
      font-weight: normal;
      color: #63656e;

      .select-custom {
        display: inline-block;
        margin-left: 5px;
        vertical-align: middle;
      }
    }

    .chart-title {
      padding: 0 10px;
      margin-left: -10px;
      font-size: 12px;
      color: #63656e;
      border-radius: 2px;

      .title-click {
        display: flex;
        flex-wrap: nowrap;
        align-items: center;
        cursor: pointer;
      }

      .main-title {
        display: flex;
        flex-wrap: nowrap;
        align-items: center;
        justify-content: space-between;
        height: 24px;

        .title-name {
          height: 20px;
          overflow: hidden;
          font-weight: 700;
          line-height: 20px;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .time-result {
          margin-left: 14px;

          .total-count {
            color: #f00;
          }
        }

        .icon-down-shape {
          margin-right: 8px;
          transition: transform 0.3s;

          &.is-flip {
            transition: transform 0.3s;
            transform: rotate(-90deg);
          }
        }

        // &::after {
        //   /* stylelint-disable-next-line declaration-no-important */
        //   font-family: 'icon-monitor' !important;
        //   content: '\e61c';
        //   font-size: 20px;
        //   width: 24px;
        //   height: 16px;
        //   align-items: center;
        //   justify-content: center;
        //   color: #979ba5;
        //   margin-right: auto;
        //   display: none;
        // }
      }

      .sub-title {
        height: 16px;
        overflow: hidden;
        line-height: 16px;
        color: #979ba5;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .menu-list {
      position: absolute;
      top: 0;
      right: 36px;

      .bklog-icon {
        font-size: 14px;
        color: #979ba5;
        cursor: pointer;
      }
    }

    .chart-spin {
      position: absolute;
      top: 27px;
      right: 36px;
    }
  }
</style>
