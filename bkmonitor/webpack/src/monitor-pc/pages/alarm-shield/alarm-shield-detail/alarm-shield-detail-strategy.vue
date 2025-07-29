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
  <div class="alarm-shield-detail-strategy">
    <div class="scope-item scope-item-icon">
      <div class="item-label">
        {{ $t('屏蔽策略') }}
      </div>
      <div class="item-content">
        <div
          v-for="(item, index) in dimension.strategies"
          :key="item.id"
          class="item-content-name"
        >
          {{ item.name
          }}<i
            class="icon-monitor icon-mc-wailian"
            @click="handleToStrategy(item.id)"
          />
          <span v-if="index + 1 !== dimension.strategies.length">,</span>
        </div>
      </div>
    </div>
    <div
      v-if="isOneStrategy"
      class="strategy-detail"
    >
      <div class="strategy-detail-label">
        {{ $t('策略内容') }}
      </div>
      <!-- <strategy-detail :strategy-data="dimension.strategies[0].itemList[0]"></strategy-detail> -->
      <strategy-detail-new :strategy-data="strategyData" />
    </div>
    <alarm-shield-detail-dimension :detail-data="detailData" />
    <div
      v-if="dimension.target"
      class="scope-item"
    >
      <div class="item-label">
        {{ $t('屏蔽范围') }}
      </div>
      <div class="item-content">
        <div class="item-content-target">
          {{ target }}
        </div>
      </div>
    </div>
    <div class="scope-item">
      <div class="item-label">
        {{ $t('屏蔽级别') }}
      </div>
      <div class="item-content">
        {{ level }}
      </div>
    </div>
  </div>
</template>

<script>
import { transformDataKey } from 'monitor-common/utils/utils';

import { strategyMapMixin } from '../../../common/mixins';
import StrategyDetailNew from '../alarm-shield-components/strategy-detail-new';
import AlarmShieldDetailDimension from './alarm-shield-detail-dimension.tsx';

export default {
  name: 'AlarmShieldDetailStrategy',
  components: {
    StrategyDetailNew,
    AlarmShieldDetailDimension,
  },
  mixins: [strategyMapMixin],
  props: {
    dimension: {
      type: Object,
      default: () => ({}),
    },
    detailData: {
      type: Object,
      default: () => null,
    },
  },
  data() {
    return {
      level: '',
      levelMap: ['', this.$t('致命'), this.$t('预警'), this.$t('提醒')],
      target: '',
    };
  },
  computed: {
    isOneStrategy() {
      return this.dimension.strategies?.length === 1;
    },
    strategyData() {
      return transformDataKey(
        {
          id: this.dimension.strategies[0].id,
          name: this.dimension.strategies[0].name,
          scenario: this.dimension.strategies[0].scenario,
          items: [{ queryConfigs: this.dimension.strategies[0].itemList }],
        },
        true
      );
    },
  },
  created() {
    this.handleStrategyDetail();
  },
  methods: {
    handleStrategyDetail() {
      const arr = [];
      if (Array.isArray(this.dimension.level)) {
        this.dimension.level.forEach(item => {
          arr.push(this.levelMap[item]);
        });
      } else {
        arr.push(this.levelMap[this.dimension.level]);
      }
      this.level = arr.join('、');
      if (this.dimension.target) {
        this.target = this.dimension.target.join(',');
      }
    },
    handleToStrategy(id) {
      this.$router.push({ name: 'strategy-config-detail', params: { id } });
    },
  },
};
</script>

<style lang="scss" scoped>
.alarm-shield-detail-strategy {
  font-size: 14px;
  color: #63656e;

  .scope-item {
    display: flex;
    align-items: flex-start;
    margin-bottom: 20px;

    .item-label {
      min-width: 90px;
      margin-right: 24px;
      color: #979ba5;
      text-align: right;
    }

    .item-content {
      display: flex;
      flex-direction: row;
      flex-wrap: wrap;
      align-items: center;
      min-height: 16px;

      &-name {
        display: flex;
        flex-direction: row;
        align-items: center;
      }

      i {
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 21px;
        color: #979ba5;
        cursor: pointer;

        &:hover {
          color: #3a84ff;
        }
      }

      &-target {
        display: block;
        max-width: calc(100vw - 306px);
        word-break: break-all;
      }
    }
  }

  .scope-item-icon {
    /* stylelint-disable-next-line declaration-no-important */
    align-items: center !important;

    .item-content {
      line-height: 23px;
    }
  }

  .strategy-detail {
    display: flex;
    align-items: flex-start;
    margin-bottom: 20px;

    &-label {
      min-width: 90px;
      padding-top: 6px;
      margin-right: 24px;
      color: #979ba5;
      text-align: right;
    }

    &-content {
      display: flex;
      flex-direction: column;
      width: calc(100vw - 306px);
      padding: 11.5px 21px 6px 21px;
      background: #fafbfd;
      border: 1px solid #dcdee5;
      border-radius: 2px;

      .column-item {
        display: flex;
        align-items: flex-start;
        min-height: 32px;
        margin-bottom: 7px;
      }

      .item-label {
        min-width: 70px;
        height: 32px;
        margin-right: 6px;
        line-height: 32px;
        text-align: right;
      }

      .item-content {
        height: 32px;
        line-height: 32px;
      }

      .item-aggdimension {
        height: 32px;
        padding: 7px 12px 9px 12px;
        margin: 0 2px 2px 0;
        font-size: 12px;
        line-height: 16px;
        text-align: center;
        background: #fff;
        border: 1px solid #dcdee5;
        border-radius: 2px;
      }

      .item-aggcondition {
        display: flex;
        flex-wrap: wrap;
        max-width: calc(100vw - 322px);

        .item-blue {
          color: #3a84ff;
        }

        .item-yellow {
          color: #ff9c01;
        }
      }

      &-aggCondition {
        align-items: flex-start;
      }
    }
  }
}
</style>
