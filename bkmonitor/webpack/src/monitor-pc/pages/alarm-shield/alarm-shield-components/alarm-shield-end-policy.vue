<template>
  <div class="shield-end-policy">
    <div class="policy-label">
      {{ $t('屏蔽期内告警通知') }}<span v-if="!readonly" class="required"> *</span>
    </div>
    <div class="policy-content">
      <bk-radio-group
        class="policy-options"
        :value="value"
        @change="handleChange"
      >
        <div
          class="policy-option"
          :class="{ 'is-checked': value === 'notify_once', 'is-disabled': readonly }"
          @click="handleChange('notify_once')"
        >
          <bk-radio
            :disabled="readonly"
            value="notify_once"
          />
          <div class="option-copy">
            <div class="option-title">{{ $t('屏蔽结束后发送一次通知') }}</div>
            <p class="option-tips">
              {{
                $t(
                  '屏蔽结束时，仍未恢复的告警将各发送一次通知。告警较多时，可能在短时间内集中产生多条通知。'
                )
              }}
            </p>
          </div>
        </div>
        <div
          class="policy-option"
          :class="{ 'is-checked': value === 'close', 'is-disabled': readonly }"
          @click="handleChange('close')"
        >
          <bk-radio
            :disabled="readonly"
            value="close"
          />
          <div class="option-copy">
            <div class="option-title">{{ $t('屏蔽结束时不再通知') }}</div>
            <p class="option-tips">
              {{
                $t(
                  '屏蔽期间产生的告警，期间不发送通知、不执行处理套餐（作业、回调、自愈等），屏蔽结束时系统将这些告警关闭，不补发通知、不补执行处理，后续新触发的告警按原策略通知和处理。'
                )
              }}
            </p>
          </div>
        </div>
      </bk-radio-group>
      <p
        v-if="showError"
        class="policy-error"
      >
        {{ $t('请选择屏蔽结束后的告警通知方式') }}
      </p>
      <p
        v-if="readonly"
        class="policy-hint"
      >
        {{ $t('结束处理方式创建后不可修改。如需使用另一种方式，请新建屏蔽规则。') }}
      </p>
      <p
        v-else
        class="policy-hint"
      >
        {{ $t('「屏蔽结束」包括按计划到期和提前解除，此选项不影响屏蔽开始前已存在的告警。') }}
      </p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AlarmShieldEndPolicy',
  props: {
    value: { type: String, default: 'notify_once' },
    readonly: { type: Boolean, default: false },
  },
  data() {
    return {
      showError: false,
    };
  },
  methods: {
    handleChange(val) {
      if (this.readonly || val === this.value) return;
      this.showError = false;
      this.$emit('input', val);
    },
    validate() {
      if (this.readonly) return true;
      // 新建默认 notify_once；空值只覆盖初始化异常
      this.showError = !['notify_once', 'close'].includes(this.value);
      return !this.showError;
    },
  },
};
</script>

<style lang="scss" scoped>
.shield-end-policy {
  display: flex;
  align-items: flex-start;
  margin-bottom: 20px;
  font-size: 14px;
  line-height: 22px;
  color: #63656e;

  .policy-label {
    flex: 0 0 120px;
    padding-right: 24px;
    text-align: right;
    white-space: nowrap;
  }

  .required {
    color: #ea3636;
  }

  .policy-content {
    flex: 1;
    min-width: 0;
    max-width: 860px;
  }

  .policy-options {
    display: flex;
    flex-direction: column;
  }

  .policy-option {
    display: flex;
    align-items: flex-start;
    padding: 12px 16px;
    cursor: pointer;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;

    & + .policy-option {
      margin-top: 8px;
    }

    &.is-checked {
      background: #f0f5ff;
      border-color: #3a84ff;
    }

    &.is-disabled {
      cursor: not-allowed;
      background: #fafbfd;

      &.is-checked {
        background: #f5f7fa;
        border-color: #dcdee5;
      }
    }

    :deep(.bk-form-radio) {
      margin-top: 3px;
      margin-right: 0;
      line-height: 16px;

      .bk-radio-text {
        display: none;
      }
    }

    .option-copy {
      flex: 1;
      min-width: 0;
      margin-left: 10px;
    }

    .option-title {
      font-weight: 500;
      line-height: 22px;
      color: #323438;
    }

    &.is-disabled .option-title {
      color: #c4c6cc;
    }

    &.is-disabled.is-checked .option-title {
      color: #979ba5;
    }
  }

  .option-tips,
  .policy-hint {
    margin: 2px 0 0;
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
  }

  .policy-hint {
    margin-top: 8px;
  }

  .policy-error {
    margin: 8px 0 0;
    font-size: 12px;
    line-height: 20px;
    color: #ea3636;
  }
}
</style>
