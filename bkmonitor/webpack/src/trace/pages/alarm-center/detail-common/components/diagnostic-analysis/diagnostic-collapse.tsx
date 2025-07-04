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
import { defineComponent, type PropType } from 'vue';

import { Collapse, Loading } from 'bkui-vue';

import ContentCollapse from './content-collapse';

import './diagnostic-collapse.scss';
export default defineComponent({
  name: 'DiagnosticCollapse',
  props: {
    list: Array as PropType<any[]>,
    activeIndex: Array as PropType<number[]>,
  },
  setup(props) {
    const titleSlot = item => (
      <span class='collapse-item-title'>
        <i class={`icon-monitor ${item.icon} title-icon-circle`} />
        <span class='field-name'>{item.name}</span>
      </span>
    );
    const contentSlot = item => (
      <Loading loading={false}>
        {item?.render ? (
          item.render(item)
        ) : (
          <ContentCollapse
            v-slots={item.slots}
            list={item.list}
          />
        )}
      </Loading>
    );
    return () => (
      <div class='diagnostic-collapse-box'>
        <Collapse
          class='collapse-main'
          v-model={props.activeIndex}
          v-slots={{
            default: item => titleSlot(item),
            content: item => contentSlot(item),
          }}
          header-icon='right-shape'
          list={props.list}
        />
      </div>
    );
  },
});
