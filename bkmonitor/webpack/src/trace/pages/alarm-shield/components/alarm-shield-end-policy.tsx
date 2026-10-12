import { defineComponent, shallowRef } from 'vue';

import { Radio } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './alarm-shield-end-policy.scss';

export default defineComponent({
  name: 'AlarmShieldEndPolicy',
  props: {
    modelValue: {
      type: String,
      default: 'notify_once',
    },
    readonly: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    'update:modelValue': (_value: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const showError = shallowRef(false);

    const handleChange = (val: string) => {
      if (props.readonly || val === props.modelValue) return;
      showError.value = false;
      emit('update:modelValue', val);
    };

    const validate = () => {
      if (props.readonly) return true;
      // 新建默认 notify_once；空值只覆盖初始化异常
      showError.value = props.modelValue !== 'notify_once' && props.modelValue !== 'close';
      return !showError.value;
    };

    return {
      t,
      showError,
      handleChange,
      validate,
    };
  },
  render() {
    return (
      <div class='shield-end-policy'>
        <Radio.Group
          class='policy-options'
          disabled={this.readonly}
          modelValue={this.modelValue}
          onUpdate:modelValue={this.handleChange}
        >
          <div
            class={['policy-option', { 'is-checked': this.modelValue === 'notify_once', 'is-disabled': this.readonly }]}
            onClick={() => this.handleChange('notify_once')}
          >
            <Radio
              disabled={this.readonly}
              label='notify_once'
            />
            <div class='option-copy'>
              <div class='option-title'>{this.t('屏蔽结束后发送一次通知')}</div>
              <p class='option-tips'>
                {this.t('屏蔽结束时，仍未恢复的告警将各发送一次通知。告警较多时，可能在短时间内集中产生多条通知。')}
              </p>
            </div>
          </div>
          <div
            class={['policy-option', { 'is-checked': this.modelValue === 'close', 'is-disabled': this.readonly }]}
            onClick={() => this.handleChange('close')}
          >
            <Radio
              disabled={this.readonly}
              label='close'
            />
            <div class='option-copy'>
              <div class='option-title'>{this.t('屏蔽结束时不再通知')}</div>
              <p class='option-tips'>
                {this.t(
                  '屏蔽期间产生的告警，期间不发送通知、不执行处理套餐（作业、回调、自愈等），屏蔽结束时系统将这些告警关闭，不补发通知、不补执行处理，后续新触发的告警按原策略通知和处理。'
                )}
              </p>
            </div>
          </div>
        </Radio.Group>
        {this.showError ? <p class='policy-error'>{this.t('请选择屏蔽结束后的告警通知方式')}</p> : undefined}
        <p class='policy-hint'>
          {this.readonly
            ? this.t('结束处理方式创建后不可修改。如需使用另一种方式，请新建屏蔽规则。')
            : this.t('「屏蔽结束」包括按计划到期和提前解除，此选项不影响屏蔽开始前已存在的告警。')}
        </p>
      </div>
    );
  },
});
