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
  <div class="alarm-shield-detail-event">
    <div class="scope-item adapt-icon">
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
    <div class="strategy-detail">
      <div class="strategy-detail-label">
        {{ $t('告警内容') }}
      </div>
      <div class="strategy-detail-content">
        <!-- <div class="column-item">
                    <div class="item-label"> {{ $t('告警级别：') }} </div><div class="item-content">{{levelMap[dimension.level]}}</div>
                </div> -->
        <div class="column-item">
          <div class="item-label">{{ $t('维度信息') }} :</div>
          <div class="item-content">
            {{ dimension.dimensions }}
          </div>
        </div>
        <div
          class="column-item"
          style="margin-bottom: 18px"
        >
          <div class="item-label">{{ $t('检测算法') }} :</div>
          <div class="item-content">
            {{ dimension.eventMessage }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AlarmShieldDetailEvent',
  props: {
    dimension: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      levelMap: ['', this.$t('致命'), this.$t('预警'), this.$t('提醒')],
    };
  },
  methods: {
    // 跳转到对应的事件详情
    handleToEvent() {
      this.$router.push({ name: 'event-center-detail', params: { id: this.dimension.id } });
    },
    handleToStrategy(id) {
      this.$router.push({ name: 'strategy-config-detail', params: { id } });
    },
  },
};
</script>

<style lang="scss" scoped>
.alarm-shield-detail-event {
  font-size: 14px;
  color: #63656e;

  .scope-item {
    display: flex;
    align-items: flex-start;
    margin-bottom: 20px;

    .item-label {
      min-width: 90px;
      color: #979ba5;
      text-align: right;
      margin-right: 24px;
    }

    .item-content {
      min-height: 16px;
      display: flex;
      align-items: center;

      &-name {
        display: flex;
        align-items: center;
      }

      i {
        font-size: 21px;
        color: #979ba5;
        cursor: pointer;

        &:hover {
          color: #3a84ff;
        }
      }

      &-target {
        word-break: break-all;
        max-width: calc(100vw - 306px);
      }
    }
  }

  .adapt-icon {
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
      color: #979ba5;
      min-width: 90px;
      text-align: right;
      margin-right: 24px;
      padding-top: 6px;
    }

    &-content {
      display: flex;
      flex-direction: column;
      padding: 18px 21px 0 21px;
      min-width: 836px;
      background: #fafbfd;
      border: 1px solid #dcdee5;
      border-radius: 2px;

      .column-item {
        display: flex;
        align-items: flex-start;
        margin-bottom: 20px;
      }

      .item-label {
        min-width: 70px;
        text-align: right;
        margin-right: 6px;
      }

      .item-content {
        word-wrap: break-word;
        word-break: break-all;
      }
    }
  }
}
</style>
