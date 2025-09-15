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
import { computed, defineComponent, type PropType } from 'vue';

import './index.scss';

export type ShowListType = {
  fieldName: string;
  label?: string;
  desc?: string;
  descType?: string;
  valueRender?: (value: any, object: any) => HTMLElement | string;
};

export default defineComponent({
  props: {
    object: {
      type: Object,
      default: () => ({}),
    },
    showList: {
      type: Array as PropType<ShowListType[]>,
      default: () => [],
    },
    labelWidth: {
      type: Number,
      default: 200,
    },
    formType: {
      type: String,
    },
  },
  setup(props) {
    const defaultValueRender = (name: string) => <span>{props.object[name] ?? 'undefined'}</span>;
    const renderList = computed(() => {
      if (props.showList.length) {
        return props.showList.map(item => {
          return {
            fieldName: item.fieldName,
            label: item.label,
            valueRender: item.valueRender ?? defaultValueRender,
            desc: item.desc,
            descType: item.descType,
          };
        });
      }

      return Object.keys(props.object).map(name => {
        return {
          fieldName: name,
          label: name,
          valueRender: defaultValueRender,
        };
      });
    });
    return () => (
      <bk-form
        formType={props.formType}
        label-width={props.labelWidth}
        model={props.object}
        on-input={() => {}}
      >
        {renderList.value.map(item => (
          <bk-form-item
            key={item.fieldName}
            style='margin-top: 0;'
            ext-cls='bklog-v3-object-view-item'
            desc={item.desc}
            desc-type={item.descType}
            label={item.label ?? item.fieldName}
          >
            {item.valueRender(item.fieldName, props.object)}
          </bk-form-item>
        ))}
      </bk-form>
    );
  },
});
