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
import { defineComponent, ref, computed } from 'vue';

import BklogPopover from '@/components/bklog-popover';
import useLocale from '@/hooks/use-locale';
import { debounce } from 'lodash';
import { useRoute } from 'vue-router/composables';

import useStore from '../../../hooks/use-store';
import GrepCliEditor from './grep-cli-editor';

import './grep-cli.scss';

export default defineComponent({
  name: 'GrepCli',
  components: {
    GrepCliEditor,
    BklogPopover,
  },
  props: {
    searchCount: {
      type: Number,
      default: null,
    },
    searchValue: {
      type: String,
      default: '',
    },
    fieldValue: {
      type: String,
      default: '',
    },
  },
  emits: ['search-change', 'match-mode', 'grep-enter', 'field-change'],
  setup(props, { emit }) {
    const route = useRoute();
    const { t } = useLocale();
    const grepValue = ref((route.query.grep_query as string) ?? '');

    const isCaseSensitive = ref(false);
    const isRegexMode = ref(false);
    const isWordMatch = ref(false);
    // const currentMatchIndex = ref(1);

    const store = useStore();
    const fieldList = computed(() =>
      (store.state.indexFieldInfo.fields ?? []).filter(field => field.field_type === 'text'),
    );

    // 计算是否有搜索结果
    // const hasResults = computed(() => {
    //   return props.searchCount > 0;
    // });

    // 计算结果显示文本
    // const resultText = computed(() => {
    //   if (!props.searchCount || !props.searchValue) {
    //     return { text: '无结果', type: 'placeholder' };
    //   }

    //   if (props.searchCount === 0) {
    //     return { text: '无结果', type: 'no-result' };
    //   }

    //   return {
    //     text: `${currentMatchIndex.value}/${props.searchCount}`,
    //     type: 'success',
    //   };
    // });

    // 选择字段
    const handleFieldChange = (id: string) => {
      emit('field-change', id);
    };

    // 编辑器内容变化
    const handleEditorChange = (newValue: string) => {
      grepValue.value = newValue;
    };

    // 搜索输入
    const handleSearchInput = debounce((value: string) => {
      emit('search-change', {
        content: value,
        searchValue: value,
        matchMode: {
          caseSensitive: isCaseSensitive.value,
          regexMode: isRegexMode.value,
          wordMatch: isWordMatch.value,
        },
      });
    }, 300);

    // 切换大小写敏感
    const toggleCaseSensitive = () => {
      isCaseSensitive.value = !isCaseSensitive.value;
      emit('match-mode', {
        caseSensitive: isCaseSensitive.value,
        regexMode: isRegexMode.value,
        wordMatch: isWordMatch.value,
      });
    };

    // 切换正则模式
    const toggleRegexMode = () => {
      isRegexMode.value = !isRegexMode.value;
      emit('match-mode', {
        caseSensitive: isCaseSensitive.value,
        regexMode: isRegexMode.value,
        wordMatch: isWordMatch.value,
      });
    };

    // 切换整词匹配
    const toggleWordMatch = () => {
      isWordMatch.value = !isWordMatch.value;
      emit('match-mode', {
        caseSensitive: isCaseSensitive.value,
        regexMode: isRegexMode.value,
        wordMatch: isWordMatch.value,
      });
    };

    // 上一个匹配
    // const gotoPrevMatch = () => {
    //   if (hasResults.value) {
    //     emit('search-change', {
    //       content: grepValue.value,
    //       searchValue: props.searchValue,
    //       matchMode: {
    //         caseSensitive: isCaseSensitive.value,
    //         regexMode: isRegexMode.value,
    //         wordMatch: isWordMatch.value,
    //       },
    //     });
    //   }
    // };

    // 下一个匹配
    // const gotoNextMatch = () => {
    //   if (hasResults.value) {
    //     emit('search-change', {
    //       content: grepValue.value,
    //       searchValue: props.searchValue,
    //       matchMode: {
    //         caseSensitive: isCaseSensitive.value,
    //         regexMode: isRegexMode.value,
    //         wordMatch: isWordMatch.value,
    //       },
    //     });
    //   }
    // };

    const handleEditorEnter = (value: string) => {
      emit('grep-enter', value);
    };

    // 处理导航点击事件
    // const handlePrevClick = () => {
    //   if (hasResults.value) {
    //     gotoPrevMatch();
    //   }
    // };

    // const handleNextClick = () => {
    //   if (hasResults.value) {
    //     gotoNextMatch();
    //   }
    // };

    return () => (
      <div class='grep-cli-container grep-cli-flex'>
        <div class='grep-cli-left'>
          <div style={{ display: 'flex', width: '128px' }}>
            <span class='grep-cli-label'>{t('字段')}:</span>
            <bk-select
              style='min-width: 80px; border: none;'
              class='grep-cli-select'
              popover-min-width={200}
              size='small'
              value={props.fieldValue}
              on-change={handleFieldChange}
            >
              {fieldList.value.map(option => (
                <bk-option
                  id={option.field_name}
                  key={option.field_name}
                  name={option.field_name}
                />
              ))}
            </bk-select>
          </div>
          <div class='grep-cli-editor'>
            <GrepCliEditor
              placeholder={
                '"Common Text" | -i "ignore-case text" | -v "excluded text" | -E "regex match like [0-9]+" | -iv -E "multiple options"'
              }
              autoHeight={true}
              maxHeight='160px'
              minHeight='34px'
              value={grepValue.value}
              on-change={handleEditorChange}
              on-enter={handleEditorEnter}
            />
          </div>
        </div>

        {/* 右侧匹配栏 */}
        <div class='grep-cli-right'>
          <div class='grep-cli-search-section'>
            <bk-input
              class='grep-cli-search-input'
              clearable={true}
              placeholder={t('搜索')}
              size='small'
              value={props.searchValue}
              on-change={handleSearchInput}
            />
            <div class='grep-cli-tools'>
              <BklogPopover
                content={t('大小写匹配')}
                options={{ placement: 'top', theme: 'dark', appendTo: document.body } as any}
                trigger='hover'
              >
                <span
                  class={['grep-cli-tool-icon', 'bklog-icon', 'bklog-daxiaoxie', { active: isCaseSensitive.value }]}
                  onClick={toggleCaseSensitive}
                />
              </BklogPopover>

              <BklogPopover
                content={t('精确匹配')}
                options={{ placement: 'top', theme: 'dark', appendTo: document.body } as any}
                trigger='hover'
              >
                <span
                  class={['grep-cli-tool-icon', 'bklog-icon', 'bklog-ab', { active: isWordMatch.value }]}
                  onClick={toggleWordMatch}
                />
              </BklogPopover>

              <BklogPopover
                content={t('正则匹配')}
                options={{ placement: 'top', theme: 'dark', appendTo: document.body } as any}
                trigger='hover'
              >
                <span
                  class={['grep-cli-tool-icon', 'bklog-icon', 'bklog-tongpeifu', { active: isRegexMode.value }]}
                  onClick={toggleRegexMode}
                />
              </BklogPopover>
            </div>
          </div>

          {/* <div class='grep-cli-result-section'>
            <span class={['grep-cli-result-text', resultText.value.type]}>{resultText.value.text}</span>
            <div class='grep-cli-navigation'>
              <span
                class={['grep-cli-nav-icon', 'grep-cli-nav-up', { disabled: !hasResults.value }]}
                onClick={handlePrevClick}
                title='上一个匹配'
              >
                ↑
              </span>
              <span
                class={['grep-cli-nav-icon', 'grep-cli-nav-down', { disabled: !hasResults.value }]}
                onClick={handleNextClick}
                title='下一个匹配'
              >
                ↓
              </span>
            </div>
          </div> */}
        </div>
      </div>
    );
  },
});
