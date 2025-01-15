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
  <bk-dialog
    :value="isShowStrategy"
    theme="primary"
    :header-position="'left'"
    :confirm-fn="handleSubmit"
    :title="$t('快捷屏蔽策略')"
    width="773px"
    @after-leave="handleAfterLeave"
  >
    <div
      v-bkloading="{ isLoading: loading }"
      class="quick-alarm-shield-stratrgy"
    >
      <div
        v-if="!loading"
        class="stratrgy-item"
      >
        <div
          class="item-label item-before"
          style="width: 66px"
        >
          {{ $t('屏蔽时间') }}
        </div>
        <verify-input
          :show-validate.sync="rule.customTime"
          :validator="{ content: $t('至少选择一种时间') }"
        >
          <div class="item-time">
            <bk-button
              v-for="(item, index) in timeList"
              :key="index"
              class="width-item"
              :class="{ 'is-selected': timeValue === item.id }"
              @click.stop="handleScopeChange(item.id)"
            >
              {{ item.name }}
            </bk-button>
            <bk-button
              v-if="timeValue !== 0"
              class="custom-width"
              :class="{ 'is-selected': timeValue === 0 }"
              @click.stop="handleScopeChange(0)"
            >
              {{ $t('button-自定义') }}
            </bk-button>
            <bk-date-picker
              v-else
              ref="time"
              v-model="customTime"
              :options="options"
              :placeholder="$t('选择时间范围')"
              :type="'datetimerange'"
            />
          </div>
        </verify-input>
      </div>
      <div class="stratrgy-item">
        <div class="item-label">
          {{ $t('策略内容') }}
        </div>
        <strategy-detail :strategy-data="strategyData" />
      </div>
      <div
        class="stratrgy-item"
        style="margin-bottom: 11px"
      >
        <div class="item-label">
          {{ $t('屏蔽原因') }}
        </div>
        <div>
          <bk-input
            v-model="desc"
            :type="'textarea'"
            width="625"
            :rows="3"
            :maxlength="100"
          />
        </div>
      </div>
      <!-- <div class="to-strategy" @click="handleToStrategy">更多高级设置<i class="icon-monitor icon-mc-wailian"></i></div> -->
    </div>
  </bk-dialog>
</template>

<script>
import { addShield } from 'monitor-api/modules/shield';
import { getStrategyV2 } from 'monitor-api/modules/strategies';

import { quickAlarmShieldMixin, strategyMapMixin } from '../../../common/mixins';
import VerifyInput from '../../../components/verify-input/verify-input';
import StrategyDetail from '../alarm-shield-components/strategy-detail-new.tsx';

export default {
  name: 'QuickAlarmShieldStratrgy',
  components: {
    VerifyInput,
    StrategyDetail,
  },
  mixins: [quickAlarmShieldMixin, strategyMapMixin],
  props: {
    isShowStrategy: {
      type: Boolean,
      default: false,
    },
    strategyId: Number,
  },
  data() {
    return {
      timeValue: 18,
      customTime: ['', ''],
      desc: '',
      typeLabel: '',
      rule: {
        customTime: false,
      },
      loading: false,
      strategyData: {},
    };
  },
  watch: {
    strategyId: {
      handler(newId, oldId) {
        if (`${newId}` !== `${oldId}`) {
          this.handleDialogShow();
        }
      },
      immediate: true,
    },
  },
  methods: {
    handleSubmit(v) {
      const time = this.getTime();
      if (time) {
        this.loading = true;
        const params = {
          category: 'strategy',
          begin_time: time.begin,
          end_time: time.end,
          dimension_config: {
            id: [this.strategyId],
            level: [this.strategyData?.detects[0].level],
          },
          cycle_config: {
            begin_time: '',
            type: 1,
            day_list: [],
            week_list: [],
            end_time: '',
          },
          shield_notice: false,
          description: this.desc,
          is_quick: true,
        };
        addShield(params)
          .then(() => {
            v.close();
            this.$bkMessage({ theme: 'success', message: this.$t('创建告警屏蔽成功') });
            this.$parent.handleGetListData();
          })
          .finally(() => {
            this.loading = false;
          });
      }
    },
    handleDialogShow() {
      this.loading = true;
      this.timeValue = 18;
      this.desc = '';
      this.customTime = '';
      this.getDetailStrategy();
    },
    getDetailStrategy() {
      if (this.strategyId) {
        getStrategyV2({ id: this.strategyId })
          .then(res => {
            this.strategyData = res;
          })
          .finally(() => {
            this.loading = false;
          });
      }
    },
    handleAfterLeave() {
      this.$emit('update:isShowStrategy', false);
    },
    handleToStrategy() {
      const params = {
        strategyId: this.strategyId,
      };
      this.$emit('update:isShowStrategy', false);
      this.$router.push({ name: 'alarm-shield-add', params });
    },
  },
};
</script>

<style lang="scss" scoped>
.quick-alarm-shield-stratrgy {
  font-size: 14px;
  color: #63656e;

  .stratrgy-item {
    display: flex;
    flex-direction: column;
    margin-bottom: 17px;

    .item-label {
      width: 86px;
      margin-bottom: 8px;
    }

    .item-time {
      display: flex;

      .width-item {
        min-width: 86px;

        &:hover {
          z-index: 2;
          color: #3a84ff;
          background: #e1ecff;
          border: 1px #3a84ff solid;
        }
      }

      .custom-width {
        width: 300px;
      }

      .is-selected {
        z-index: 2;
        color: #3a84ff;
        background: #e1ecff;
        border: 1px #3a84ff solid;
      }

      :deep(.bk-button) {
        margin-left: -1px;
        border-radius: 0;
      }
    }

    .item-before {
      position: relative;

      &::before {
        position: absolute;
        top: 0;
        right: -9px;
        color: #ea3636;
        content: '*';
      }
    }

    :deep(.bk-date-picker.long) {
      width: 300px;
    }

    :deep(.bk-date-picker-rel .bk-date-picker-editor) {
      margin-left: -1px;
      border: 1px #3a84ff solid;
      border-radius: 0;
    }
  }

  .to-strategy {
    display: flex;
    align-items: center;
    color: #3a84ff;
    cursor: pointer;

    i {
      font-size: 21px;
    }
  }
}

:deep(.bk-date-picker-dropdown) {
  /* stylelint-disable-next-line declaration-no-important */
  left: 191px !important;
}

:deep(.bk-dialog-wrapper .bk-dialog-body) {
  max-height: 455px;
  padding: 1px 24px 14px;
  overflow-y: auto;
}

:deep(.item-content) {
  max-height: 270px;
  overflow: scroll;
}
</style>
