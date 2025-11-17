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
  <div class="title-wrapper">
    <div
      ref="chartTitle"
      class="chart-title"
      tabindex="0"
      @blur="showMenu = false"
      @click.stop="handleShowMenu"
    >
      <div class="main-title">
        <span
          class="bk-icon icon-down-shape"
          :class="{ 'is-flip': isFold }"
        ></span>
        <div class="title-name">{{ title }}</div>
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
    <div
      v-else-if="!isFold"
      class="menu-list"
    >
      <span
        class="log-icon icon-xiangji"
        data-test-id="generalTrendEcharts_span_downloadEcharts"
        @click.stop="handleMenuClick({ id: 'screenshot' })"
      >
      </span>
    </div>
    <!-- <chart-menu
      v-show="showMenu"
      :list="menuList"
      @menu-click="handleMenuClick"
      :style="{ left: menuLeft + 'px' }">
    </chart-menu> -->
  </div>
</template>

<script lang="ts">
  import { Component, Vue, Prop, Ref } from 'vue-property-decorator';
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
    @Ref('chartTitle') chartTitleRef: HTMLDivElement;
    private showMenu = false;
    private menuLeft = 0;
    handleShowMenu(e: MouseEvent) {
      this.$emit('toggle-expand', !this.isFold);

      // this.showMenu = !this.showMenu
      // const rect = this.chartTitleRef.getBoundingClientRect()
      // this.menuLeft = rect.width  - 185 < e.layerX ? rect.width  - 185 : e.layerX
    }
    handleMenuClick(item) {
      this.showMenu = false;
      this.$emit('menu-click', item);
    }
  }
</script>
<style lang="scss" scoped>
  .title-wrapper {
    position: relative;
    flex: 1;
    width: 100%;

    .chart-title {
      padding: 4px 10px;
      margin-left: -10px;
      font-size: 12px;
      color: #63656e;
      cursor: pointer;
      border-radius: 2px;

      // &:hover {
      //   .main-title {
      //     &::after {
      //       display: flex;
      //     }
      //   }
      // }

      .main-title {
        display: flex;
        flex-wrap: nowrap;
        align-items: center;
        font-weight: 700;

        .title-name {
          height: 20px;
          overflow: hidden;
          line-height: 20px;
          text-overflow: ellipsis;
          white-space: nowrap;
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
      top: 16px;
      right: 36px;

      .log-icon {
        font-size: 14px;
        color: #979ba5;
        cursor: pointer;
      }
    }

    .chart-spin {
      position: absolute;
      top: 24px;
      right: 36px;
    }
  }
</style>
