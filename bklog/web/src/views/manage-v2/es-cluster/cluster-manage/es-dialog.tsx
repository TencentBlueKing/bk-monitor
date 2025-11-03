/*
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
*/
import { defineComponent, ref, computed, watch, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';

interface NodeItem {
  id: number | string;
  name: string;
  host: string;
  attr: string;
  value: number | string;
}

interface FormDataType {
  hot_attr_name: string;
  hot_attr_value: number | string;
  warm_attr_name: string;
  warm_attr_value: number | string;
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
        width={840}
        header-position='left'
        show-footer={false}
        title={title.value}
        value={props.value}
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
              />
              <bk-table-column
                label='Name'
                prop='name'
              />
              <bk-table-column
                label='Host'
                prop='host'
              />
            </bk-table>
          )}
        </div>
      </bk-dialog>
    );
  },
});
