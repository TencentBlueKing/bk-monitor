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
    class="dialog-wrap"
    :title="curItem.title"
    :width="curItem.width"
    :esc-close="false"
    :value="dialogShow"
    :mask-close="false"
    header-position="left"
    @after-leave="handleAfterLeave"
    @confirm="handleConfirm"
  >
    <div
      v-bkloading="{ isLoading: loading || isLoading }"
      class="strategy-dialog-wrap"
    >
      <div
        v-if="setType !== 7"
        class="num-tips"
      >
        <i18n path="已选择{0}个策略"
          ><span class="num-text">&nbsp;{{ checkedList.length }}&nbsp;</span></i18n
        >
      </div>
      <!-- 告警组 -->
      <template v-if="setType === 0">
        <div class="from-item-wrap">
          <div class="alarm-group-label">{{ $t('告警组') }} <span class="asterisk">*</span></div>
          <bk-select
            v-if="dialogShow"
            v-model="data.alarmGroup"
            class="alarm-notice-list"
            behavior="simplicity"
            multiple
            :clearable="false"
            searchable
          >
            <bk-option
              v-for="(option, index) in groupList"
              :id="option.id"
              :key="index"
              :name="option.name"
            />
          </bk-select>
          <span
            v-if="data.noticeGroupError"
            class="notice-error-msg error-msg-font"
          >
            {{ $t('选择告警组') }}
          </span>
        </div>
      </template>
      <!-- 触发条件 -->
      <template v-else-if="setType === 1">
        <div class="modify-trigger-condition">
          <i18n
            class="i18n"
            path="在{0}个周期内{1}满足{2}次检测算法触发异常告警"
          >
            <bk-input
              v-model="data.triggerCondition.cycleOne"
              behavior="simplicity"
              class="number-input w56"
              type="number"
              :show-controls="false"
              :min="1"
              :max="60"
              @change="handleFormatNumber(arguments, 'triggerCondition', 'cycleOne')"
            />
            <bk-select
              v-model="data.triggerCondition.type"
              behavior="simplicity"
              style="width: 64px"
              :clearable="false"
            >
              <bk-option
                v-for="(option, index) in triggerTypeList"
                :id="option.id"
                :key="index"
                :name="option.name"
              />
            </bk-select>
            <bk-input
              v-model="data.triggerCondition.count"
              behavior="simplicity"
              class="number-input w56"
              type="number"
              :show-controls="false"
              :min="1"
              :max="numbersScope.countMax"
              @change="handleFormatNumber(arguments, 'triggerCondition', 'count')"
            />
          </i18n>
          <span
            v-if="data.triggerError"
            class="trigger-condition-tips"
          >
            <i class="icon-monitor icon-mind-fill item-icon" /> {{ $t('要求: 满足次数&lt;=周期数') }}
          </span>
        </div>
      </template>
      <!-- 恢复条件 -->
      <template v-else-if="setType === 5">
        <div class="modify-trigger-condition">
          <i18n path="连续{0}个周期内不满足触发条件表示恢复">
            <bk-input
              v-model="data.recover.val"
              behavior="simplicity"
              class="number-input"
              type="number"
              :show-controls="false"
              :min="1"
              @change="handleFormatNumber(arguments, 'recover', 'val')"
            />
          </i18n>
        </div>
        <span
          v-if="data.recoverCycleError"
          class="recover-cycle-error-msg error-msg-font"
        >
          {{ $t('仅支持整数') }}
        </span>
      </template>
      <!-- 通知间隔 -->
      <template v-else-if="setType === 2">
        <div class="alarm-interval">
          {{ $t('若告警未恢复并且未确认，则每隔') }}
          <bk-input
            v-model="data.notice.val"
            behavior="simplicity"
            class="number-input"
            type="number"
            :show-controls="false"
            :min="1"
            :max="1440"
            @change="handleFormatNumber(arguments, 'notice', 'val')"
          />
          {{ $t('分钟进行告警') }}
        </div>
        <span
          v-if="data.recoverAlarmError"
          class="recover-error-msg error-msg-font"
        >
          {{ $t('仅支持整数') }}
        </span>
      </template>
      <!-- 无数据告警 -->
      <template v-else-if="setType === 3">
        <div class="no-data-alarm">
          <i18n
            class="i18n"
            path="{0}当数据连续丢失{1}个周期触发无数据告警"
          >
            <bk-switcher
              v-model="data.openAlarmNoData"
              class="inline-switcher"
              size="small"
              theme="primary"
            />
            <bk-input
              v-model="data.noDataAlarm.cycle"
              behavior="simplicity"
              :disabled="!data.openAlarmNoData"
              class="number-input"
              type="number"
              :show-controls="false"
              :min="1"
              @change="handleFormatNumber(arguments, 'noDataAlarm', 'cycle')"
            />
          </i18n>
        </div>
        <span
          v-if="data.noDataCycleError"
          class="no-data-error-msg error-msg-font"
        >
          {{ $t('仅支持整数') }}
        </span>
      </template>
      <!-- 告警恢复通知 -->
      <template v-else-if="setType === 4">
        <bk-checkbox
          v-model="data.alarmNotice"
          class="alarm-recover"
        >
          {{ $t('告警恢复通知') }}
        </bk-checkbox>
      </template>
      <!-- 启停策略 -->
      <template v-else-if="setType === 6">
        <div class="alarm-recover">
          <bk-radio-group v-model="data.enAbled">
            <bk-radio
              style="margin-right: 58px"
              :value="true"
              >{{ $t('启用') }}</bk-radio
            >
            <bk-radio :value="false">
              {{ $t('停用') }}
            </bk-radio>
          </bk-radio-group>
        </div>
      </template>
      <!-- 删除策略 -->
      <template v-else-if="setType === 7">
        <div class="delete-strategy">
          {{ $t('已选择 {n} 个策略，确定批量删除？', { n: checkedList.length }) }}
          <!-- {{ $t('确认是否批量删除已选择的') + checkedList.length + $t("个策略") }} -->
        </div>
      </template>
      <!-- 告警模板 -->
      <template v-else-if="setType === 9">
        <div
          v-bkloading="{ isLoading: alertNotificationTemplateLoading }"
          class="alarm-recover message-template"
        >
          <span
            class="default-template"
            @click="alertNotificationTemplate.messageTemplate = messageTemplate"
            >{{ $t('填充默认模板') }}</span
          >
          <template-input
            ref="templateInput"
            :default-value="alertNotificationTemplate.messageTemplate"
            :trigger-list="alertNotificationTemplate.triggerList"
            @change="handleTemplateChange"
          />
          <div class="message-template-tip">
            <div>{{ $t('注意：批量设置会覆盖原有的已选择的告警策略模版配置。') }}</div>
          </div>
        </div>
      </template>
      <!-- 标签 -->
      <template v-else-if="setType === 10">
        <div class="from-item-wrap">
          <div class="alarm-group-label">{{ $t('标签') }} <span class="asterisk">*</span></div>
          <multi-label-select
            style="width: 100%; margin-bottom: 40px"
            mode="select"
            behavior="simplicity"
            :auto-get-list="true"
            :checked-node="data.labels"
            @loading="v => (isLoading = v)"
            @checkedChange="v => (data.labels = v)"
          />
          <span
            v-if="data.labelsError"
            class="notice-error-msg error-msg-font"
          >
            {{ $t('选择标签') }}
          </span>
        </div>
      </template>
      <template v-else-if="setType === 11">
        <div
          v-bkloading="{ isLoading: alarmHandlingData.loading }"
          class="alarm-handling"
        >
          <div class="alarm-handling-tip">
            <span class="icon-monitor icon-hint" />
            <div>{{ $t('批量修改告警模版会将所有选择策略修改成当前设置的内容。') }}</div>
          </div>
          <div class="alarm-handling-content">
            <alarm-handling
              ref="alarmHandling"
              :key="alarmHandlingData.key"
              :is-fta-alert="alarmHandlingData.isFtaAlert"
              :enabled-no-data="alarmHandlingData.enabledNoData"
              :value="alarmHandlingData.value"
              :strategy-id="alarmHandlingData.strategyId ? +alarmHandlingData.strategyId : ''"
              :group-list="alarmHandlingData.groupList"
              :readonly="alarmHandlingData.readonly"
              :is-preview="false"
              @change="val => (alarmHandlingData.value = val)"
              @addGroup="handleCancel"
            />
          </div>
        </div>
      </template>
    </div>
    <template #footer>
      <bk-button
        v-if="setType === 6 || setType === 7"
        theme="primary"
        @click="handleConfirm"
      >
        {{ $t('确认') }}
      </bk-button>
      <bk-button
        v-else
        theme="primary"
        :disabled="loading"
        @click="handleConfirm"
      >
        {{ $t('保存') }}
      </bk-button>
      <bk-button @click="handleCancel">
        {{ $t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>
<script>
import { listUserGroup } from 'monitor-api/modules/model';
import { noticeVariableList } from 'monitor-api/modules/strategies';

import MultiLabelSelect from '../../../components/multi-label-select/multi-label-select';
import AlarmHandling from '../strategy-config-set-new/alarm-handling-bak/alarm-handling.tsx';
import TemplateInput from '../strategy-config-set/strategy-template-input/strategy-template-input';
// import { createNamespacedHelpers } from 'vuex'
// const { mapActions } = createNamespacedHelpers('strategy-config')
export default {
  name: 'StrategyConfigDialog',
  components: {
    TemplateInput,
    MultiLabelSelect,
    AlarmHandling,
  },
  props: {
    setType: {
      type: Number,
      required: true,
    },
    groupList: {
      type: Array,
      default: () => [],
    },
    dialogShow: Boolean,
    selectList: {
      type: Array,
      default() {
        return [];
      },
    },
    checkedList: {
      type: Array,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      isLoading: false,
      typeMap: [
        {
          title: this.$t('修改告警组'),
          width: 400,
        },
        {
          title: this.$t('修改触发条件'),
          width: 480,
        },
        {
          title: this.$t('修改通知间隔'),
          width: 480,
        },
        {
          title: this.$t('修改无数据告警'),
          width: 400,
        },
        {
          title: this.$t('批量修改告警恢复通知'),
          width: 400,
        },
        {
          title: this.$t('修改恢复条件'),
          width: 480,
        },
        {
          title: this.$t('启/停策略'),
          width: 400,
        },
        {
          title: this.$t('删除策略'),
          width: 480,
        },
        {
          title: this.$t('增删目标'),
          width: 480,
        },
        {
          title: this.$t('修改告警模版'),
          width: 480,
        },
        {
          title: this.$t('修改标签'),
          width: 400,
        },
        {
          title: this.$t('修改告警模版'),
          width: 640,
        },
      ],
      triggerTypeList: [{ id: 1, name: this.$t('累计') }],
      numbersScope: {
        countMax: 5,
      },
      data: {
        labels: [],
        alarmGroup: '',
        triggerCondition: {
          cycleOne: 5,
          count: 4,
          cycleTwo: 5,
          type: 1,
        },
        recover: {
          val: 5,
        },
        notice: {
          val: 120,
        },
        noDataAlarm: {
          cycle: 5,
        },
        openAlarmNoData: true,
        alarmNotice: true,
        triggerError: false,
        noticeGroupError: false,
        recoverAlarmError: false,
        recoverCycleError: false,
        noDataCycleError: false,
        enAbled: false,
        labelsError: false,
      },
      cachInitData: null,
      alertNotificationTemplate: {
        messageTemplate: '',
        triggerList: [],
      },
      messageTemplate: `{{content.level}}
{{content.begin_time}}
{{content.time}}
{{content.duration}}
{{content.target_type}}
{{content.data_source}}
{{content.content}}
{{content.current_value}}
{{content.biz}}
{{content.target}}
{{content.dimension}}
{{content.detail}}
{{content.related_info}}`,
      alertNotificationTemplateLoading: true,
      alarmHandlingData: {
        value: [],
        isFtaAlert: false,
        enabledNoData: false,
        readonly: false,
        strategyId: '',
        groupList: [],
        loading: false,
        key: 1,
      },
    };
  },
  computed: {
    curItem() {
      return this.typeMap[this.setType] || {};
    },
  },
  watch: {
    async dialogShow(v) {
      if (v) {
        this.setType === 0 && this.$emit('get-group-list');
        this.data = JSON.parse(JSON.stringify(this.cachInitData));
        if (this.setType === 11) {
          await this.$nextTick();
          this.$refs.alarmHandling.clearErrorMsg();
          this.alarmHandlingData.key += 1;
        }
      }
    },
    'data.triggerCondition.cycleOne'(v) {
      this.numbersScope.countMax = v;
    },
    async setType(v) {
      // 批量告警模板数据
      if (v === 9) {
        if (this.alertNotificationTemplate.triggerList.length === 0) {
          this.handleGetVariateList();
        } else {
          this.alertNotificationTemplateLoading = false;
        }
      } else if (v === 11) {
        if (!this.alarmHandlingData.groupList.length) {
          this.alarmHandlingData.loading = true;
          await this.getAlarmGroupList();
          this.alarmHandlingData.loading = false;
        }
      }
    },
  },
  created() {
    this.cachInitData = JSON.parse(JSON.stringify(this.data));
  },
  methods: {
    // ...mapActions(['getNoticeVariableList']),
    // 获取策略模板变量列表
    async getNoticeVariableList() {
      const data = await noticeVariableList({ bk_biz_id: this.$store.getters.bizId }).catch(() => []);
      return data;
    },
    // 获取策略模板变量列表
    async handleGetVariateList() {
      const data = await this.getNoticeVariableList();
      this.alertNotificationTemplate.triggerList = data.reduce((pre, cur) => {
        pre.push(...cur.items);
        return pre;
      }, []);
      this.alertNotificationTemplateLoading = false;
    },
    // 获取告警组数据
    getAlarmGroupList() {
      return listUserGroup().then(data => {
        this.alarmHandlingData.groupList = data.map(item => ({
          id: item.id,
          name: item.name,
          receiver: item?.users?.map(rec => rec.display_name) || [],
        }));
        !this.alarmHandlingData.value.length &&
          this.alarmHandlingData.value.push({
            signal: 'abnormal',
            config_id: 1,
            user_groups: [],
            show: true,
          });
      });
    },
    // 通知模板编辑变化触发
    handleTemplateChange(v) {
      this.alertNotificationTemplate.messageTemplate = v || '';
    },
    handleCancel() {
      this.$emit('hide-dialog', false);
    },
    async handleConfirm() {
      const params = await this.generationParam();
      if (params) {
        this.$emit('confirm', params);
        this.$emit('hide-dialog', false);
      }
    },
    handleAfterLeave() {
      this.isLoading = false;
      this.$emit('hide-dialog', false);
    },
    handleFormatNumber(arg, type, prop) {
      let inputVal = arg[0].toString();
      const index = inputVal.indexOf('.');
      if (index > -1) {
        inputVal = inputVal.replace(/\./gi, '');
      }
      this.data[type][prop] = Number.parseInt(inputVal, 10);
    },
    validateGroupList() {
      this.data.noticeGroupError = !this.data.alarmGroup.length;
      return this.data.noticeGroupError;
    },
    validateLabelsList() {
      this.data.labelsError = !this.data.labels.length;
      return this.data.labelsError;
    },
    validateTriggerCondition() {
      for (const key in this.data.triggerCondition) {
        if (!this.data.triggerCondition[key]) {
          this.data.triggerError = true;
          return true;
        }
      }
      const cycleOne = Number.parseInt(this.data.triggerCondition.cycleOne, 10);
      const count = Number.parseInt(this.data.triggerCondition.count, 10);
      if (cycleOne < count) {
        this.data.triggerError = true;
      } else {
        this.data.triggerError = false;
      }
      return this.data.triggerError;
    },
    validateRecoveAlarmCondition() {
      this.data.recoverAlarmError = !this.data.notice.val;
      return this.data.recoverAlarmError;
    },
    validateRecoveCycle() {
      this.data.recoverCycleError = !this.data.recover.val;
      return this.data.recoverCycleError;
    },
    validateNoDataAlarmCycle() {
      this.data.noDataCycleError = !this.data.noDataAlarm.cycle;
      return this.data.noDataCycleError;
    },
    async generationParam() {
      const setTypeMap = {
        0: () => (this.validateGroupList() ? false : { notice_group_list: this.data.alarmGroup }),
        1: () =>
          this.validateTriggerCondition()
            ? false
            : {
                trigger_config: {
                  count: Number.parseInt(this.data.triggerCondition.count, 10),
                  check_window: Number.parseInt(this.data.triggerCondition.cycleOne, 10),
                },
              },
        2: () =>
          this.validateRecoveAlarmCondition() ? false : { alarm_interval: Number.parseInt(this.data.notice.val, 10) },
        3: () => {
          if (this.data.openAlarmNoData && this.validateNoDataAlarmCycle()) {
            return false;
          }
          return this.data.openAlarmNoData
            ? {
                no_data_config: {
                  continuous: Number.parseInt(this.data.noDataAlarm.cycle, 10),
                  is_enabled: this.data.openAlarmNoData,
                },
              }
            : { no_data_config: { is_enabled: this.data.openAlarmNoData } };
        },
        4: () => ({ send_recovery_alarm: this.data.alarmNotice }),
        5: () => (this.validateRecoveCycle() ? false : { recovery_config: { check_window: this.data.recover.val } }),
        6: () => ({ is_enabled: this.data.enAbled }),
        7: () => ({ isDel: true }),
        9: () => ({ message_template: this.alertNotificationTemplate.messageTemplate }),
        10: () => (this.validateLabelsList() ? false : { labels: this.data.labels }),
        11: async () => {
          const validate = await this.$refs.alarmHandling
            .validate()
            .then(() => true)
            .catch(() => false);
          return validate
            ? {
                actions: this.alarmHandlingData.value,
              }
            : false;
        },
      };
      return setTypeMap[this.setType] ? setTypeMap[this.setType]() : {};
    },
  },
};
</script>

<style lang="scss" scoped>
.dialog-wrap {
  :deep(.bk-dialog-wrapper) {
    .header-on-left {
      padding-bottom: 15px;
    }
  }
}

.strategy-dialog-wrap {
  position: relative;

  .i18n {
    display: flex;
    align-items: center;
  }

  .num-tips {
    margin-bottom: 12px;
    font-size: 12px;
    color: #979ba5;

    .num-text {
      font-weight: bold;
    }
  }

  .alarm-notice-list {
    margin-bottom: 40px;
  }

  .modify-trigger-condition {
    display: flex;
    align-items: center;
    margin-top: 13px;
    margin-bottom: 46px;
    font-size: 12px;

    :deep(.bk-select) {
      .bk-select-name {
        padding-right: 24px;
      }
    }

    .trigger-condition-tips {
      position: absolute;
      top: 66px;
      left: 22px;
      font-size: 12px;
      color: #ea3636;
    }
  }

  .alarm-group-label {
    margin-bottom: 5px;
    font-size: 12px;

    .asterisk {
      margin-left: 3px;
      color: #ea3636;
    }
  }

  .delete-strategy {
    margin-top: 7px;
    margin-bottom: 50px;
    line-height: 20px;
    color: #63656e;
    text-align: center;
  }

  .alarm-recover {
    margin-bottom: 42px;
  }

  .alarm-interval {
    margin-top: 13px;
    margin-bottom: 40px;
  }

  .no-data-alarm {
    margin-bottom: 38px;

    .inline-switcher {
      margin-right: 8px;
    }
  }

  .no-data-alarm-cycle {
    margin-bottom: 40px;
  }

  .number-input {
    display: inline-block;
    width: 64px;
    margin: 0 8px;

    :deep(.bk-form-input) {
      height: 24px;
      text-align: center;
    }
  }

  .w56 {
    width: 56px;
  }

  .bk-select {
    line-height: 24px;

    :deep(.bk-select-angle) {
      top: 1px;
    }

    :deep(.bk-select-name) {
      height: 24px;
    }
  }

  .from-item-wrap {
    position: relative;
  }

  .notice-error-msg {
    position: absolute;
    top: 59px;
  }

  .trigger-error {
    color: #ea3636;
  }

  .error-msg-font {
    font-size: 12px;
    color: #ea3636;
  }

  .recover-error-msg {
    position: absolute;
    top: 23px;
  }

  .recover-cycle-error-msg {
    position: absolute;
    top: 32px;
  }

  .no-data-error-msg {
    position: absolute;
    top: 62px;
  }

  .default-template {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    height: 20px;
    color: #3a84ff;
    cursor: pointer;
  }

  .message-template {
    :deep(.template-input) {
      min-height: 150px;
    }

    &-tip {
      position: relative;
      padding: 10px 35px 10px 10px;
      margin: 10px 0 20px 0;
      overflow: hidden;
      line-height: 24px;
      background-color: #f0f8ff;
      border: 1px solid #a3c5fd;
      border-radius: 2px;
      transition: height ease-in-out 0.3s;

      div {
        color: #63656e;
      }
    }
  }

  .alarm-handling {
    width: 592px;
    max-height: 510px;
    padding-bottom: 18px;
    overflow-y: auto;

    &-tip {
      display: flex;
      align-items: center;
      height: 32px;
      padding: 0 10px;
      font-size: 12px;
      color: #63656e;
      background: #f0f8ff;
      border: 1px solid #c5daff;
      border-radius: 3px;

      .icon-hint {
        margin-right: 8px;
        font-size: 16px;
        color: #3a84ff;
      }
    }

    &-content {
      margin-top: 10px;
    }
  }
}
</style>
<style lang="scss" scoped>
:deep(.bk-dialog-body) {
  padding-top: 0;
  padding-bottom: 0;
}

:deep(.bk-dialog-footer) {
  font-size: 0;

  .bk-button {
    margin-right: 10px;

    &:last-child {
      margin-right: 0;
    }
  }
}
</style>
<style lang="scss">
.tippy-popper {
  body & {
    pointer-events: auto;
  }
}
</style>
