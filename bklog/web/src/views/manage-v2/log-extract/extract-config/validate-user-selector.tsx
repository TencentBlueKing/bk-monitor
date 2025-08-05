import { defineComponent, ref, PropType } from 'vue';
import BkUserSelector from '@blueking/user-selector';

import './validate-user-selector.scss';

export default defineComponent({
  name: 'ValidateUserSelector',
  components: {
    BkUserSelector,
  },
  props: {
    // 输入值
    value: {
      type: Array,
      default: () => [],
    },
    // 占位符
    placeholder: {
      type: String,
      default: '',
    },
    // API 地址
    api: {
      type: String,
      default: '',
    },
    // 是否禁用
    disabled: {
      type: Boolean,
      default: false,
    },
    onChange: { type: Function },
  },
  emits: ['change'],

  setup(props, { emit }) {
    const isError = ref(false); // 是否显示错误状态

    // 校验初始值
    const validateInitValue = () => {
      if (props.value.length) {
        isError.value = false;
      } else {
        isError.value = true;
      }
    };

    // 处理选择变化
    const handleChange = (val: any[]) => {
      const realVal = val.filter(item => item !== undefined);
      isError.value = !realVal.length;
      emit('change', realVal);
    };

    // 失焦时校验
    const handleBlur = () => {
      isError.value = !props.value.length;
    };

    return () => (
      <div class='validate-user-selector'>
        <BkUserSelector
          style='width: 400px'
          api={props.api}
          class={isError.value ? 'is-error' : ''}
          disabled={props.disabled}
          empty-text='无匹配人员'
          placeholder={props.placeholder}
          value={props.value}
          onBlur={handleBlur}
          onChange={handleChange}
        />
      </div>
    );
  },
});
