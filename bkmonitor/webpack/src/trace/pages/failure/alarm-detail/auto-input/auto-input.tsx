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
import { computed, defineComponent, PropType, ref } from 'vue';

import { Input } from 'bkui-vue';
import { $bkPopover } from 'bkui-vue/lib/popover';

import './auto-input.scss';

interface ITipsList {
  id: string;
  name: string;
}

export default defineComponent({
  props: {
    modelValue: {
      default: '',
      type: String,
    },
    placeholder: {
      default: '',
      type: String,
    },
    readonly: {
      default: false,
      type: Boolean,
    },
    tipsList: {
      default: () => [],
      type: Array as PropType<ITipsList[]>,
    },
  },
  emits: ['change', 'input', 'update:modelValue'],
  setup(props, { emit }) {
    const popoverInstance = ref<HTMLDivElement>();
    const offsetX = ref(0);
    const offsetY = ref(0);
    const keyword = ref('');
    const oldVal = ref('');
    const startIndex = ref(0);
    const curIndex = ref(0);

    const tipsListFilter = computed(() => props.tipsList.filter(item => item.id.indexOf(keyword.value) > -1));

    const tipsListEl = ref<HTMLElement>(null);
    const inputEl = ref<HTMLElement>(null);

    const emitValue = val => {
      emit('change', val);
      emit('input', val);
      emit('update:modelValue', val);
    };
    const value = computed({
      get() {
        return props.modelValue;
      },
      set: emitValue,
    });
    // 输入事件
    const handleInput = (val, evt) => {
      handleInputEvt(evt);
      if (!props.modelValue || !tipsListFilter.value.length) {
        return handleDestroyPopover();
      }
      handlePopoverShow();
      emitValue(val);
    };

    // 处理输入事件数据
    const handleInputEvt = evt => {
      // 最新值
      const { target } = evt;
      const newVal: string = target.value;
      getIndex(newVal, oldVal.value);
      keyword.value = handleKeyword(newVal);
      oldVal.value = newVal;
      emitValue(newVal);
    };

    // 获取光标的位置
    const getIndex = (newVal: string, oldVal: string): number => {
      const tempStr = newVal.length > oldVal.length ? newVal : oldVal;
      console.log(newVal, oldVal, 'old');
      let diffIndex = 0;
      tempStr.split('').find((item, idx) => {
        diffIndex = idx;
        return oldVal[idx] !== newVal[idx];
      });
      curIndex.value = diffIndex;
      if (newVal[diffIndex] === '{' && newVal[diffIndex - 1] === '{') {
        startIndex.value = diffIndex - 1;
      }
      // 当出现{{{{
      if (curIndex.value) {
        if (newVal.indexOf('{{{{') > -1) {
          curIndex.value = curIndex.value - 2;
          startIndex.value = startIndex.value - 2;
        }
      }
      return diffIndex;
    };

    // 点击选中
    const handleMousedown = (item: ITipsList) => {
      const paramsArr = props.modelValue.split('');
      paramsArr.splice(startIndex.value, curIndex.value - startIndex.value + 1, `{{${item.id}}}`);
      emitValue(paramsArr.join(''));
      oldVal.value = props.modelValue;
      keyword.value = '';
    };
    // 处理关键字
    const handleKeyword = (newVal: string): string => {
      return newVal
        .slice(startIndex.value, curIndex.value + 1)
        .replace(/({)|(})/g, '')
        .trim();
    };

    // 提示列表显示方法
    const handlePopoverShow = () => {
      console.log('handlePopoverShow', popoverInstance.value);
      if (!popoverInstance.value) {
        popoverInstance.value = $bkPopover({
          target: inputEl.value,
          content: tipsListEl.value,
          arrow: false,
          flip: false,
          flipBehavior: 'bottom',
          trigger: 'manual',
          placement: 'top-start',
          theme: 'light auto-input',
          maxWidth: 520,
          duration: [200, 0],
          offset: [offsetX.value, offsetY.value],
        });
      } else {
        // 更新提示的位置
        popoverInstance.value.set({
          offset: `${offsetX.value}, ${offsetY.value}`,
        });
      }
      // 显示
      popoverInstance.value.show(100);
    };

    // 隐藏
    const handleDestroyPopover = (): void => {
      if (popoverInstance.value) {
        popoverInstance.value.hide(0);
        popoverInstance.value.destroy?.();
        popoverInstance.value = null;
      }
    };
    return {
      value,
      tipsListFilter,
      handleInput,
      handleMousedown,
    };
  },
  render() {
    return (
      <div class='auto-input-wrap'>
        <div ref='input'>
          <Input
            v-model={this.value}
            behavior={'simplicity'}
            placeholder={this.placeholder || this.$t('请输入')}
            readonly={this.readonly}
            onInput={this.handleInput}
          ></Input>
        </div>
        <div style='display: none'>
          <ul class='tips-list-wrap'>
            {this.tipsListFilter.map((item, index) => (
              <li
                key={index}
                class='list-item'
                onMousedown={() => this.handleMousedown(item)}
              >
                <span>{item.id}</span>
                <span class='item-desc'>{item.name}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  },
});
