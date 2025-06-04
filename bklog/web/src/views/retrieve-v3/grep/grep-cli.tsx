import { defineComponent, ref, computed } from 'vue';
import GrepCliEditor from './grep-cli-editor';
import useStore from '../../../hooks/use-store';
import './grep-cli.scss';

export default defineComponent({
  name: 'GrepCli',
  components: {
    GrepCliEditor,
  },
  props: {
    searchCount: {
      type: Number,
      default: null,
    },
  },
  emits: ['search-change', 'match-mode', 'grep-enter', 'field-change'],
  setup(props, { emit }) {
    const field = ref();
    const grepValue = ref('');
    const searchValue = ref('');
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
      if (!props.searchCount || !searchValue.value) {
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
      field.value = id;
      emit('field-change', id);
    };

    // 编辑器内容变化
    const handleEditorChange = (newValue: string) => {
      grepValue.value = newValue;
    };

    // 搜索输入
    const handleSearchInput = (value: string) => {
      searchValue.value = value;
      emit('search-change', {
        content: value,
        searchValue: searchValue.value,
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
        currentMatchIndex.value = currentMatchIndex.value > 1 ? currentMatchIndex.value - 1 : props.searchCount;
        emit('search-change', {
          content: grepValue.value,
          searchValue: searchValue.value,
          matchMode: {
            caseSensitive: isCaseSensitive.value,
            regexMode: isRegexMode.value,
            wordMatch: isWordMatch.value,
          },
          currentIndex: currentMatchIndex.value,
        });
      }
    };

    // 下一个匹配
    const gotoNextMatch = () => {
      if (hasResults.value) {
        currentMatchIndex.value = currentMatchIndex.value < props.searchCount ? currentMatchIndex.value + 1 : 1;
        emit('search-change', {
          content: grepValue.value,
          searchValue: searchValue.value,
          matchMode: {
            caseSensitive: isCaseSensitive.value,
            regexMode: isRegexMode.value,
            wordMatch: isWordMatch.value,
          },
          currentIndex: currentMatchIndex.value,
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
          <span class='grep-cli-label'>字段：</span>
          <bk-select
            class='grep-cli-select'
            value={field.value}
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
          <div class='grep-cli-editor'>
            <GrepCliEditor
              value={grepValue.value}
              placeholder='-- INSERT, Ctrl +Enter提交查询 --'
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
              placeholder='搜索'
              value={searchValue.value}
              on-enter={handleSearchInput}
              size='small'
            />
            <div class='grep-cli-tools'>
              <span
                class={['grep-cli-tool-icon', 'bklog-icon', 'bklog-daxiaoxie', { active: isCaseSensitive.value }]}
                title='大小写匹配'
                onClick={toggleCaseSensitive}
              />
              <span
                class={['grep-cli-tool-icon', 'bklog-icon', 'bklog-ab', { active: isRegexMode.value }]}
                title='精准匹配'
                onClick={toggleRegexMode}
              />
              <span
                class={['grep-cli-tool-icon', 'bklog-icon', 'bklog-tongpeifu', { active: isWordMatch.value }]}
                title='通配符'
                onClick={toggleWordMatch}
              />
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
