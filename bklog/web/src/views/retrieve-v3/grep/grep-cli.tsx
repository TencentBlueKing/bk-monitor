import { defineComponent, ref, computed } from 'vue';
import GrepCliEditor from './grep-cli-editor';
import './grep-cli.scss';

const fieldList = [{ id: 'log', name: 'log' }];

export default defineComponent({
  name: 'GrepCli',
  components: {
    GrepCliEditor,
  },
  setup() {
    const field = ref('log');
    const value = ref('');
    const searchValue = ref('');
    const isCaseSensitive = ref(false);
    const isRegexMode = ref(false);
    const isWordMatch = ref(false);
    const currentMatchIndex = ref(0);
    const totalMatches = ref(0);

    // 计算是否有搜索结果
    const hasResults = computed(() => {
      return searchValue.value && value.value && totalMatches.value > 0;
    });

    // 计算结果显示文本
    const resultText = computed(() => {
      if (!searchValue.value) {
        return { text: '无结果', type: 'placeholder' };
      }

      if (totalMatches.value === 0) {
        return { text: '无结果', type: 'no-result' };
      }

      return {
        text: `${currentMatchIndex.value}/${totalMatches.value}`,
        type: 'success',
      };
    });

    // 选择字段
    const handleFieldChange = (id: string) => {
      field.value = id;
    };

    // 编辑器内容变化
    const handleEditorChange = (newValue: string) => {
      value.value = newValue;
      updateSearchResults();
    };

    // 搜索输入
    const handleSearchInput = (e: Event) => {
      searchValue.value = (e.target as HTMLInputElement).value;
      updateSearchResults();
    };

    // 切换大小写敏感
    const toggleCaseSensitive = () => {
      isCaseSensitive.value = !isCaseSensitive.value;
      updateSearchResults();
    };

    // 切换正则模式
    const toggleRegexMode = () => {
      isRegexMode.value = !isRegexMode.value;
      updateSearchResults();
    };

    // 切换整词匹配
    const toggleWordMatch = () => {
      isWordMatch.value = !isWordMatch.value;
      updateSearchResults();
    };

    // 上一个匹配
    const gotoPrevMatch = () => {
      if (totalMatches.value > 0) {
        currentMatchIndex.value = currentMatchIndex.value > 1 ? currentMatchIndex.value - 1 : totalMatches.value;
      }
    };

    // 下一个匹配
    const gotoNextMatch = () => {
      if (totalMatches.value > 0) {
        currentMatchIndex.value = currentMatchIndex.value < totalMatches.value ? currentMatchIndex.value + 1 : 1;
      }
    };

    // 处理导航点击事件（包含禁用状态检查）
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

    // 更新搜索结果状态
    const updateSearchResults = () => {
      if (!searchValue.value || !value.value) {
        totalMatches.value = 0;
        currentMatchIndex.value = 0;
        return;
      }

      try {
        let content = value.value;
        let searchPattern = searchValue.value;

        // 大小写处理
        if (!isCaseSensitive.value) {
          content = content.toLowerCase();
          searchPattern = searchPattern.toLowerCase();
        }

        let matches: RegExpMatchArray[] = [];

        if (isRegexMode.value) {
          // 正则模式
          try {
            const flags = isCaseSensitive.value ? 'g' : 'gi';
            const regex = new RegExp(searchPattern, flags);
            matches = Array.from(content.matchAll(regex));
          } catch {
            // 正则表达式无效时回退到普通搜索
            matches = Array.from(content.matchAll(new RegExp(escapeRegExp(searchPattern), 'g')));
          }
        } else if (isWordMatch.value) {
          // 整词匹配
          const regex = new RegExp(`\\b${escapeRegExp(searchPattern)}\\b`, isCaseSensitive.value ? 'g' : 'gi');
          matches = Array.from(value.value.matchAll(regex));
        } else {
          // 普通搜索
          const regex = new RegExp(escapeRegExp(searchPattern), 'g');
          matches = Array.from(content.matchAll(regex));
        }

        totalMatches.value = matches.length;
        currentMatchIndex.value = totalMatches.value > 0 ? 1 : 0;
      } catch {
        totalMatches.value = 0;
        currentMatchIndex.value = 0;
      }
    };

    // 转义正则表达式特殊字符
    const escapeRegExp = (string: string) => {
      return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    };

    return () => (
      <div class='grep-cli-container grep-cli-flex'>
        <div class='grep-cli-left'>
          <span class='grep-cli-label'>字段：</span>
          <bk-select
            class='grep-cli-select'
            value={field.value}
            onChange={handleFieldChange}
            size='small'
            style='min-width: 80px; border: none;'
          >
            {fieldList.map(option => (
              <bk-option
                key={option.id}
                id={option.id}
                name={option.name}
              />
            ))}
          </bk-select>
          <div class='grep-cli-editor'>
            <GrepCliEditor
              value={value.value}
              placeholder='-- INSERT --'
              autoHeight={true}
              minHeight='34px'
              maxHeight='160px'
              onUpdate:value={handleEditorChange}
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
              onInput={handleSearchInput}
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

          <div class='grep-cli-result-section'>
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
          </div>
        </div>
      </div>
    );
  },
});
