import { defineComponent, ref, computed } from 'vue';
import GrepCliEditor from './grep-cli-editor';
import useStore from '../../../hooks/use-store';
import { useRoute } from 'vue-router/composables';
import BklogPopover from '@/components/bklog-popover';

import './grep-cli.scss';
import useLocale from '@/hooks/use-locale';

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
    const currentMatchIndex = ref(1);

    const store = useStore();
    const fieldList = computed(() => store.state.indexFieldInfo.fields ?? []);

    // 计算是否有搜索结果
    const hasResults = computed(() => {
      return props.searchCount > 0;
    });

    // 计算结果显示文本
    const resultText = computed(() => {
      if (!props.searchCount || !props.searchValue) {
        return { text: '无结果', type: 'placeholder' };
      }

      if (props.searchCount === 0) {
        return { text: '无结果', type: 'no-result' };
      }

      return {
        text: `${currentMatchIndex.value}/${props.searchCount}`,
        type: 'success',
      };
    });

    // 选择字段
    const handleFieldChange = (id: string) => {
      emit('field-change', id);
    };

    // 编辑器内容变化
    const handleEditorChange = (newValue: string) => {
      grepValue.value = newValue;
    };

    // 搜索输入
    const handleSearchInput = (value: string) => {
      emit('search-change', {
        content: value,
        searchValue: value,
        matchMode: {
          caseSensitive: isCaseSensitive.value,
          regexMode: isRegexMode.value,
          wordMatch: isWordMatch.value,
        },
      });
    };

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
    const gotoPrevMatch = () => {
      if (hasResults.value) {
        emit('search-change', {
          content: grepValue.value,
          searchValue: props.searchValue,
          matchMode: {
            caseSensitive: isCaseSensitive.value,
            regexMode: isRegexMode.value,
            wordMatch: isWordMatch.value,
          },
        });
      }
    };

    // 下一个匹配
    const gotoNextMatch = () => {
      if (hasResults.value) {
        emit('search-change', {
          content: grepValue.value,
          searchValue: props.searchValue,
          matchMode: {
            caseSensitive: isCaseSensitive.value,
            regexMode: isRegexMode.value,
            wordMatch: isWordMatch.value,
          },
        });
      }
    };

    const handleEditorEnter = (value: string) => {
      emit('grep-enter', value);
    };

    // 处理导航点击事件
    const handlePrevClick = () => {
      if (hasResults.value) {
        gotoPrevMatch();
      }
    };

    const handleNextClick = () => {
      if (hasResults.value) {
        gotoNextMatch();
      }
    };

    return () => (
      <div class='grep-cli-container grep-cli-flex'>
        <div class='grep-cli-left'>
          <div style={{ display: 'flex', width: '128px' }}>
            <span class='grep-cli-label'>{t('字段')}:</span>
            <bk-select
              class='grep-cli-select'
              value={props.fieldValue}
              on-change={handleFieldChange}
              popover-min-width={200}
              size='small'
              style='min-width: 80px; border: none;'
            >
              {fieldList.value.map(option => (
                <bk-option
                  key={option.field_name}
                  id={option.field_name}
                  name={option.field_name}
                />
              ))}
            </bk-select>
          </div>
          <div class='grep-cli-editor'>
            <GrepCliEditor
              value={grepValue.value}
              placeholder={`'-- INSERT, Ctrl + Enter ${t('提交查询')} --'`}
              autoHeight={true}
              minHeight='34px'
              maxHeight='160px'
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
              placeholder={t('搜索')}
              value={props.searchValue}
              on-enter={handleSearchInput}
              size='small'
            />
            <div class='grep-cli-tools'>
              <BklogPopover
                trigger='hover'
                content={t('大小写匹配')}
                options={{ placement: 'top', theme: 'dark' } as any}
              >
                <span
                  class={['grep-cli-tool-icon', 'bklog-icon', 'bklog-daxiaoxie', { active: isCaseSensitive.value }]}
                  onClick={toggleCaseSensitive}
                />
              </BklogPopover>

              <BklogPopover
                trigger='hover'
                content={t('精确匹配')}
                options={{ placement: 'top', theme: 'dark' } as any}
              >
                <span
                  class={['grep-cli-tool-icon', 'bklog-icon', 'bklog-ab', { active: isWordMatch.value }]}
                  onClick={toggleWordMatch}
                />
              </BklogPopover>

              <BklogPopover
                trigger='hover'
                content={t('正则匹配')}
                options={{ placement: 'top', theme: 'dark' } as any}
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
