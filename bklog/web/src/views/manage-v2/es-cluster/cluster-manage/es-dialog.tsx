import { defineComponent, ref, computed, watch, PropType } from 'vue';
import useLocale from '@/hooks/use-locale';

interface NodeItem {
  id: string | number;
  name: string;
  host: string;
  attr: string;
  value: string | number;
}

interface FormDataType {
  hot_attr_name: string;
  hot_attr_value: string | number;
  warm_attr_name: string;
  warm_attr_value: string | number;
}

export default defineComponent({
  name: 'EsDialog',
  props: {
    value: {
      type: Boolean,
      default: false,
    },
    list: {
      type: Array as PropType<NodeItem[]>,
      default: () => [],
    },
    type: {
      type: String,
      default: 'hot',
    },
    formData: {
      type: Object as PropType<FormDataType>,
      required: true,
    },
  },
  emits: ['handle-value-change'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const title = ref('');

    const filterList = computed(() => {
      return props.list.filter(item => {
        if (props.type === 'hot') {
          return item.attr === props.formData.hot_attr_name && item.value === props.formData.hot_attr_value;
        }
        return item.attr === props.formData.warm_attr_name && item.value === props.formData.warm_attr_value;
      });
    });

    watch(
      () => props.value,
      val => {
        if (val) {
          const isHot = props.type === 'hot';
          const name = isHot ? props.formData.hot_attr_name : props.formData.warm_attr_name;
          const value = isHot ? props.formData.hot_attr_value : props.formData.warm_attr_value;
          title.value = t('包含属性 {n} 的节点列表', { n: `${name}:${value}` });
        }
      },
    );

    const handleVisibilityChange = (val: boolean) => {
      emit('handle-value-change', val);
    };

    return () => (
      <bk-dialog
        show-footer={false}
        title={title.value}
        value={props.value}
        width={840}
        header-position='left'
        on-value-change={handleVisibilityChange}
      >
        <div style='min-height: 200px; padding-bottom: 20px'>
          {props.value && (
            <bk-table
              data={filterList.value}
              max-height={320}
            >
              <bk-table-column
                label='ID'
                prop='id'
              ></bk-table-column>
              <bk-table-column
                label='Name'
                prop='name'
              ></bk-table-column>
              <bk-table-column
                label='Host'
                prop='host'
              ></bk-table-column>
            </bk-table>
          )}
        </div>
      </bk-dialog>
    );
  },
});
