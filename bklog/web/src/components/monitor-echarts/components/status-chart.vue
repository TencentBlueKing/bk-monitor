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
  <ul class="status-chart">
    <template v-if="series.length">
      <template>
        <bk-popover
          v-for="(item, index) in series"
          :content="statusList[item.status]"
          :key="index"
          placement="top"
        >
          <li
            class="status-chart-item"
            :class="`status-${item.status}`"
          >
            {{ item.value }}
          </li>
        </bk-popover>
      </template>
    </template>
    <div
      v-else
      class="status-chart-empty"
    >
      --
    </div>
  </ul>
</template>

<script lang="ts">
import { Vue, Prop, Component } from 'vue-property-decorator';
@Component({
  name: 'StatusChart',
})
export default class StatusChart extends Vue {
  // 端口列表
  @Prop({
    default() {
      return [];
    },
  })
  readonly series: { value: string; status: string }[];
  private statusList: any[];
  created() {
    this.statusList = [this.$t('正常'), this.$t('停用'), this.$t('异常')];
  }
}
</script>

<style lang="scss" scoped>
  $statusFontColor: #10c178 #c4c6cc #ffb848;
  $statusBgColor: #e7f9f2 #f0f1f5 #ffe8c3;

  .status-chart {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    width: 100%;
    height: 100%;
    padding: 0;

    &-item {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 30px;
      padding: 5px 14px;
      margin: 0 2px 2px 0;
      font-size: 12px;
      line-height: 20px;
      border-radius: 2px;

      @for $i from 0 through 2 {
        &.status-#{$i} {
          /* stylelint-disable-next-line function-no-unknown */
          color: nth($statusFontColor, $i + 1);

          /* stylelint-disable-next-line function-no-unknown */
          background: nth($statusBgColor, $i + 1);

          &:hover {
            color: white;
            cursor: pointer;

            /* stylelint-disable-next-line function-no-unknown */
            background: nth($statusFontColor, $i + 1);
          }
        }
      }
    }

    &-empty {
      font-size: 50px;
      line-height: 30px;
      color: #dcdee5;
    }
  }
</style>
