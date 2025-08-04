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

import { TagInput } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import AngleLeftIcon from './icons/angle-left.svg';
import AngleRightIcon from './icons/angle-right.svg';

import './search-bar.scss';

const SearchBarProps = {
  showResultCount: {
    type: Boolean,
    default: true,
  },
  resultCount: {
    type: Number,
    default: 1,
  },
  limitClassify: {
    type: Boolean,
    default: false,
  },
  prevResult: Function as PropType<() => void>,
  nextResult: Function as PropType<() => void>,
  clearSearch: Function as PropType<() => void>,
  trackFilter: Function as PropType<(list: string[]) => void>,
};

export default defineComponent({
  name: 'SearchBar',
  props: SearchBarProps,
  setup(props, { expose }) {
    const curFocusIndex = ref<number>(0);
    const searchValue = ref<string[]>([]);
    const { t } = useI18n();

    const handleChange = (list: string[]) => {
      if (list.length) {
        curFocusIndex.value = 1;
      }
      searchValue.value = list;
      props.trackFilter?.(list);
    };
    const handleClear = () => {
      curFocusIndex.value = 0;
      props.clearSearch?.();
    };
    const handlePaste = (text: string) => [{ id: text, name: text }];
    const handlePrevResult = () => {
      if (curFocusIndex.value > 1) {
        curFocusIndex.value -= 1;
        props.prevResult?.();
      }
    };
    const handleNextResult = () => {
      if (curFocusIndex.value < props.resultCount) {
        curFocusIndex.value += 1;
        props.nextResult?.();
      }
    };

    expose({
      handleChange,
    });

    return {
      searchValue,
      curFocusIndex,
      handleChange,
      handleClear,
      handlePaste,
      handlePrevResult,
      handleNextResult,
      t,
    };
  },

  render() {
    const { showResultCount, resultCount, limitClassify } = this.$props;
    return (
      <div class='trace-search-bar'>
        <TagInput
          class='trace-search-input'
          v-model={this.searchValue}
          max-data={limitClassify ? 1 : -1}
          paste-fn={this.handlePaste}
          placeholder={this.t('搜索')}
          allow-auto-match
          allow-create
          has-delete-icon
          onChange={this.handleChange}
          onRemoveAll={this.handleClear}
        />
        {showResultCount && resultCount ? (
          <div class='navigable-wrapper'>
            <img
              alt='perv'
              src={AngleLeftIcon}
              onClick={this.handlePrevResult}
            />
            <span class='count'>
              <span>{this.curFocusIndex}</span>&nbsp;/&nbsp;<span>{resultCount}</span>
            </span>
            <img
              alt='next'
              src={AngleRightIcon}
              onClick={this.handleNextResult}
            />
          </div>
        ) : (
          ''
        )}
      </div>
    );
  },
});
