import { defineComponent, ref, PropType } from 'vue';

export default defineComponent({
  name: 'ValidateInput',
  props: {
    // 输入值
    value: {
      type: String,
      default: '',
    },
    // 占位符
    placeholder: {
      type: String,
      default: '',
    },
    // 校验函数
    validator: {
      type: Function,
      default: val => Boolean(val),
    },
    onChange: { type: Function },
  },
  emits: ['change'],

  setup(props, { emit }) {
    const isError = ref(false); // 是否显示错误状态

    // 处理输入变化
    const handleChange = (val: string) => {
      emit('change', val);
    };

    // 文本框失焦时校验
    const handleBlur = (val: string) => {
      const validator = props.validator as (val: string) => boolean;
      isError.value = !validator(val);
    };

    return () => (
      <div class='validate-input'>
        <bk-input
          class={isError.value ? 'is-error' : ''}
          placeholder={props.placeholder}
          value={props.value}
          onBlur={handleBlur}
          onChange={handleChange}
        />
      </div>
    );
  },
});
