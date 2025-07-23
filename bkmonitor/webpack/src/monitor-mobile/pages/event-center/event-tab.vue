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
  <div class="event-tab">
    <van-tabs
      :class="'event-tab-' + tabList.length"
      :value="value"
      @change="handleChangeTab"
    >
      <van-tab
        v-for="(item, index) in tabList"
        :key="index"
      >
        <template #title>
          <div class="event-tab-text">
            <span class="title">
              {{ item.count ? (item.shortTitle ? item.shortTitle : item.title) : item.title }}
            </span>
            <span
              class="count"
              v-show="item.count"
            >
              {{ handleCount(item.count) }}
            </span>
          </div>
        </template>
      </van-tab>
    </van-tabs>
  </div>
</template>
<script lang="ts">
import { Component, Prop, Vue } from 'vue-property-decorator';

import { Tab, Tabs } from 'vant';

import type { ITabItem } from './event-center.vue';

@Component({
  name: 'event-tab',
  components: {
    [Tab.name]: Tab,
    [Tabs.name]: Tabs,
  },
})
export default class EventTab extends Vue {
  // tab的配置
  @Prop({ default: () => [] }) readonly tabList: ITabItem[];

  // v-model的值
  @Prop() readonly value: number;

  handleCount(count) {
    return count <= 99 ? count : 99;
  }

  // 点击tab
  handleChangeTab(val) {
    this.$emit('input', this.tabList[val].value);
    this.$emit('change', this.tabList[val].value);
  }
}
</script>
<style lang="scss">
@import '../../static/scss/variate.scss';

.event-tab {
  box-sizing: border-box;
  border-bottom: 1px solid #dcdee5;

  @for $i from 2 through 3 {
    .event-tab-#{$i} {
      .van-tabs__line {
        /* stylelint-disable-next-line declaration-no-important */
        width: 100% / $i !important;
        height: 2px;
        background-color: $primaryColor;
      }
    }
  }

  &-text {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    font-size: 16px;

    .count {
      display: flex;
      align-items: center;
      justify-items: center;
      // height: 16px;
      padding: 0 4px;
      margin-left: 6px;
      font-size: 14px;
      background-color: #c4c6cc;
      border-radius: 10px;
    }
  }

  .van-tabs__wrap {
    height: 48px;

    .van-tab {
      font-size: 16px;
      color: #63656e;

      .count {
        font-size: 14px;
        color: #fff;
      }
    }

    .van-tab--active {
      font-weight: 500;
      color: #313328;

      .count {
        background: #3a84ff;
      }
    }
  }

  .van-hairline--top-bottom {
    &::after {
      border: 0;
    }
  }
}
</style>
