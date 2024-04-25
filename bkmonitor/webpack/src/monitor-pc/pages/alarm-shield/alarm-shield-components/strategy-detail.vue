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
  <div class="stratrgy-detail">
    <!-- 事件 -->
    <div
      v-if="strategyData.dataTypeLabel === 'event'"
      class="item-content"
    >
      <div class="column-item">
        <div class="column-label">{{ $t('事件名称') }} :</div>
        <div class="column-content item-font">
          {{ strategyData.name }}
        </div>
      </div>
      <div class="column-item">
        <div class="column-label">{{ $t('告警级别') }} :</div>
        <div class="column-content item-font">
          {{ levelMap[strategyData.level[0]] }}
        </div>
      </div>
      <!-- 自定义事件 -->
      <template v-if="strategyData.dataTypeLabel === 'event' && strategyData.dataSourceLabel === 'custom'">
        <div class="column-item column-item-agg-condition">
          <div class="column-label column-target">{{ $t('监控条件') }} :</div>
          <div class="column-agg-condition">
            <div
              v-for="(item, index) in aggCondition"
              :key="index"
              class="column-agg-dimension mb-2"
              :style="{ color: aggConditionColorMap[item], 'font-weight': aggConditionFontMap[item] }"
            >
              {{ item }}
            </div>
          </div>
        </div>
      </template>
    </div>
    <!-- 监控采集 -->
    <div
      v-else
      class="item-content"
    >
      <!-- 日志 -->
      <template v-if="strategyData.dataTypeLabel === 'log'">
        <div class="column-item">
          <div class="column-label">{{ $t('索引集') }} :</div>
          <div class="column-center">
            {{ strategyData.metricField }}
          </div>
        </div>
        <div class="column-item">
          <div class="column-label">{{ $t('检索语句') }} :</div>
          <div class="column-center">
            {{ strategyData.keywordsQueryString }}
          </div>
        </div>
      </template>
      <div class="column-item">
        <div class="column-label">
          {{ $t('指标名称：') }}
        </div>
        <div class="column-content">
          <div class="item-center">
            {{ strategyData.metricField }}
          </div>
          <div class="item-source">
            {{ strategyData.metricDescription }}
          </div>
        </div>
      </div>
      <div class="column-item">
        <div class="column-label">{{ $t('计算公式') }} :</div>
        <div class="column-content item-font">
          <div
            v-if="strategyData.aggMethod === 'REAL_TIME'"
            class="item-font"
          >
            {{ $t('实时') }}
          </div>
          <div
            v-else
            class="item-font"
          >
            {{ strategyData.aggMethod }}
          </div>
        </div>
      </div>
      <!-- 实时不显示 -->
      <div
        v-if="strategyData.aggMethod !== 'REAL_TIME'"
        class="column-item"
        style="margin-bottom: 14px"
      >
        <div class="column-label">{{ $t('汇聚周期') }} :</div>
        <div class="column-content">{{ strategyData.aggInterval / 60 }} {{ $t('分钟') }}</div>
      </div>
      <!-- 实时不显示 -->
      <div
        v-if="strategyData.aggMethod !== 'REAL_TIME'"
        class="column-item column-item-agg-condition"
        style="margin-bottom: 21px"
      >
        <div class="column-label column-target">{{ $t('维度') }} :</div>
        <div class="column-agg-condition">
          <div
            v-for="(item, index) in strategyData.aggDimension"
            :key="index"
            class="column-agg-dimension mb-2"
          >
            {{ item }}
          </div>
        </div>
      </div>
      <div class="column-item column-item-agg-condition">
        <div class="column-label column-target">
          {{ $t('监控条件') }}
        </div>
        <div class="column-agg-condition">
          <div
            v-for="(item, index) in aggCondition"
            :key="index"
            class="column-agg-dimension mb-2"
            :style="{ color: aggConditionColorMap[item], 'font-weight': aggConditionFontMap[item] }"
          >
            {{ item }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { strategyMapMixin } from '../../../common/mixins';

export default {
  name: 'StrategyDetail',
  mixins: [strategyMapMixin],
  props: {
    strategyData: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      levelMap: ['', this.$t('致命'), this.$t('提醒'), this.$t('预警')],
      aggCondition: [],
    };
  },
  watch: {
    strategyData: {
      handler(newV) {
        const arr = [];
        this.aggCondition = [];
        Array.isArray(newV.aggCondition) &&
          newV.aggCondition.forEach(item => {
            if (item.condition) {
              arr.push(item.condition);
            }
            arr.push(item.key);
            arr.push(this.methodMap[item.method]);
            arr.push(item.value);
          });
      },
      immediate: true,
    },
  },
};
</script>

<style lang="scss" scoped>
.stratrgy-detail {
  display: flex;
  flex-direction: column;

  .item-label {
    width: 56px;
    margin-bottom: 8px;
  }

  .item-content {
    display: flex;
    flex-direction: column;
    padding: 17px 21px 7px 21px;
    min-width: 625px;
    background: #fafbfd;
    border: 1px solid #dcdee5;
    border-radius: 2px;

    .column-item {
      min-height: 32px;
      display: flex;
      align-items: flex-start;
      margin-bottom: 8px;
    }

    .column-label {
      min-width: 80px;
      text-align: right;
      margin-right: 7px;
      color: #979ba5;
    }

    .column-target {
      height: 32px;
      line-height: 32px;
    }

    .column-content {
      .item-source {
        color: #979ba5;
        font-size: 12px;
        margin-top: 3px;
      }

      .item-center {
        height: 19px;
        line-height: 19px;
      }
    }

    .item-font {
      height: 19px;
      line-height: 19px;
    }

    .column-agg-dimension {
      background: #fff;
      font-size: 12px;
      text-align: center;
      height: 32px;
      line-height: 16px;
      border-radius: 2px;
      border: 1px solid #dcdee5;
      margin: 0 2px 2px 0;
      padding: 7px 12px 9px 12px;
    }

    .column-agg-condition {
      max-width: calc(100vw - 322px);
      display: flex;
      flex-wrap: wrap;

      .item-blue {
        color: #3a84ff;
      }

      .item-yellow {
        color: #ff9c01;
      }
    }

    .column-item-agg-condition {
      align-items: flex-start;
    }
  }
}
</style>
