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
  <section class="custom-serious">
    <div class="custom-serious-title">
      {{ $t('告警事件') }}
    </div>
    <div class="custom-serious-content">
      <div
        v-for="(item, index) in alarm.abnormal_events"
        :key="index"
        class="chart-item"
      >
        <business-alarm-card
          :id="item.event_id"
          :title="item.strategy_name"
          :level="item.level"
          :alarm="item"
        />
      </div>
    </div>
  </section>
</template>

<script>
import BusinessAlarmCard from '../components/business-alarm-card/business-alarm-card';

export default {
  name: 'ServiceSerious',
  components: {
    BusinessAlarmCard,
  },
  props: {
    alarm: {
      type: Object,
      required: true,
    },
  },
};
</script>

<style scoped lang="scss">
@import '../common/mixins';

.custom-serious {
  &-title {
    font-size: $fontSmSize;
    font-weight: bold;
    color: $defaultFontColor;
    line-height: 19px;
    padding-bottom: 8px;
    margin-right: 40px;
    border-bottom: 1px solid $defaultBorderColor;
  }
  &-content {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    flex-wrap: wrap;
    min-width: 460px;
    max-height: 260px;
    overflow: auto;
    margin-top: 14px;

    @media only screen and (min-width: 1414px) {
      .chart-item:nth-child(2n + 1) {
        margin-right: 30px;
      }
    }
    @media only screen and (max-width: 1434px) {
      .chart-item {
        margin-right: 30px;
      }
    }
  }
}
</style>
