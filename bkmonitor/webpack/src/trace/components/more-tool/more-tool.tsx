/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { type PropType, defineComponent, ref } from 'vue';

import IconFont from '../icon-font/icon-font';
import SelectMenu, { type ISelectMenuOption } from '../select-menu/select-menu';
/**
 * 更多操作菜单选择器
 * 通过默认插槽可改变触发的icon
 */
export default defineComponent({
  name: 'MoreTool',
  props: {
    list: {
      type: Array as PropType<ISelectMenuOption[]>,
      default: () => [],
    },
    onSelect: {
      type: Function as PropType<(item: ISelectMenuOption) => void>,
    },
  },
  setup(props, { emit }) {
    const isShow = ref(false);

    /** 选中菜单 */
    const handleSelect = (item: ISelectMenuOption) => {
      emit('select', item);
    };

    return {
      isShow,
      handleSelect,
    };
  },
  render() {
    return (
      <span class='more-tool-wrap'>
        <SelectMenu
          list={this.list}
          onSelect={this.handleSelect}
          onShowChange={val => (this.isShow = val)}
        >
          {this.$slots.default?.() ?? (
            <IconFont
              width={24}
              height={24}
              activeStyle={this.isShow}
              classes={['icon-more']}
              icon='icon-mc-more'
              hoverStyle
            />
          )}
        </SelectMenu>
      </span>
    );
  },
});
