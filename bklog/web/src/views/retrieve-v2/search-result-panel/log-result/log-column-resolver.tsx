import { formatDate, formatDateNanos } from '@/common/util';
import { defineComponent, ref, CreateElement, watch, computed } from 'vue';

export default defineComponent({
  props: {
    isIntersection: {
      type: Boolean,
      default: false,
    },
    content: {
      type: [Object, String, Number, Boolean],
      default: () => ({}),
    },
    maxHeight: {
      type: [String, Number],
      default: '100%',
    },
    fieldType: {
      type: String,
      default: '',
    },
    formatDate: {
      type: Boolean,
      default: true,
    },
  },
  setup(props, { slots }) {
    const isResolved = ref(props.isIntersection);
    const formatContent = () => {
      if (props.formatDate) {
        if (props.fieldType === 'date') {
          return formatDate(Number(props.content));
        }

        // 处理纳秒精度的UTC时间格式
        if (props.fieldType === 'date_nanos') {
          return formatDateNanos(props.content);
        }
      }
      return props.content || '--';
    };

    watch(
      () => [props.isIntersection],
      ([isIntersection]) => {
        if (isIntersection) {
          isResolved.value = true;
        }
      },
    );

    const renderPlaceholder = computed(() => {
      if (typeof props.content === 'object') {
        return JSON.stringify(props.content, null, 2);
      }

      return formatContent();
    });

    return (h: CreateElement) => {
      if (isResolved.value) {
        return slots.default?.();
      }

      return h(
        'div',
        {
          class: 'bklog-v3-column-placeholder',
          style: {
            '--max-height': props.maxHeight,
          },
          domProps: {
            innerHTML: renderPlaceholder.value || '--',
          },
        },
        [],
      );
    };
  },
});
