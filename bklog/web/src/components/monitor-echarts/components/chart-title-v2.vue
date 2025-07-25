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
            path="（找到 {0} 条结果，用时 {1} 毫秒) {2}"
          >
            <span class="total-count">{{ getShowTotalNum(totalCount) }}</span>
            <span>{{ tookTime }}</span>
          </i18n>
        </div>
        <div
          v-if="!isFold"
          class="converge-cycle"
          @click.stop
        >
          <span>{{ $t('汇聚周期') + ' : ' }}</span>
          <bk-select
            ext-cls="select-custom"
            v-model="chartInterval"
            :clearable="false"
            :popover-width="70"
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

          <BklogPopover
            content-class="bklog-v3-grade-setting"
            ref="refGradePopover"
            :options="tippyOptions"
            :beforeHide="beforePopoverHide"
          >
            <span class="bklog-icon bklog-shezhi"></span>
            <template #content>
              <GradeOption
                ref="refGradeOption"
                @change="handleGradeOptionChange"
              ></GradeOption>
            </template>
          </BklogPopover>
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
  </div>
</template>

<script lang="ts">
  import { Component, Vue, Prop, Ref, Watch } from 'vue-property-decorator';
  import useStore from '@/hooks/use-store';
  import { BK_LOG_STORAGE } from '@/store/store.type.ts';

  import { formatNumberWithRegex } from '../../../common/util';

  import ChartMenu from './chart-menu.vue';
  import BklogPopover from '../../bklog-popover';
  import GradeOption from './grade-option';
  import RetrieveHelper, { RetrieveEvent } from '../../../views/retrieve-helper';

  const store = useStore();

  @Component({
    name: 'chart-title-v2',
    components: {
      ChartMenu,
      BklogPopover,
      GradeOption,
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
      { id: '1d', name: '1 d' },
    ];

    tippyOptions = {
      appendTo: document.body,
      hideOnClick: false,
      onShown: () => {
        const cfg = this.$store.state.indexFieldInfo.custom_config?.grade_options ?? {};
        (this.$refs.refGradeOption as any)?.updateOptions?.(cfg);
      },
    };

    get retrieveParams() {
      return this.$store.getters.retrieveParams;
    }

    get tookTime() {
      return Number.parseFloat(this.$store.state.tookTime).toFixed(0);
    }

    get fieldList() {
      return this.$store.state.indexFieldInfo.fields ?? [];
    }

    @Watch('retrieveParams.interval')
    watchChangeChartInterval(newVal) {
      this.chartInterval = newVal;
    }

    handleShowMenu(e: MouseEvent) {
      this.$emit('toggle-expand', !this.isFold);
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
      setTimeout(() => {
        RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
      });
    }

    handleGradeOptionChange({ isSave }) {
      (this.$refs.refGradePopover as any)?.hide();
      if (isSave) {
        RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
      }
    }

    /**
     * 通过判定当前点击元素是否为指定弹出下拉菜单的子元素判定是否允许关闭弹出
     * @param e
     */
    beforePopoverHide(e: MouseEvent) {
      const target = e.target as HTMLElement;

      if (
        ((target.classList.contains('bk-option-name') || target.classList.contains('bk-option-content-default')) &&
          target.closest('.bk-select-dropdown-content.bklog-popover-stop')) ||
        target.classList.contains('bklog-popover-stop')
      ) {
        return false;
      }
      return true;
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
      color: #4d4f56;

      .select-custom {
        display: inline-block;
        padding-left: 5px;
        color: #313238;
        vertical-align: middle;
        border: none;

        :deep(.bk-select-name) {
          width: 60px;
          padding-right: 20px;
          padding-left: 0;
          text-align: center;
        }
      }

      .bklog-icon {
        padding: 1px;
        font-size: 14px;
        cursor: pointer;
      }
    }

    .chart-title {
      width: 100%;
      padding: 0 4px;
      margin-left: -10px;
      font-size: 12px;
      color: #4d4f56;
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
          font-family: MicrosoftYaHei-Bold, sans-serif;
          font-weight: 700;
          line-height: 20px;
          color: #313238;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .time-result {
          padding-left: 5px;
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
<style lang="scss"></style>
