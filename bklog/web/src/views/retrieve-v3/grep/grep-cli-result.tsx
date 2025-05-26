import { defineComponent, ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import './grep-cli-result.scss';
import Mark from 'mark.js';

// 虚拟滚动行组件
const VirtualLogLine = defineComponent({
  name: 'VirtualLogLine',
  props: {
    log: {
      type: String,
      required: true,
    },
    lineNumber: {
      type: Number,
      required: true,
    },
    maxHeight: {
      type: Number,
      default: 200,
    },
    searchValue: {
      type: String,
      default: '',
    },
    matchMode: {
      type: Object,
      default: () => ({
        caseSensitive: false,
        regexMode: false,
        wordMatch: false,
      }),
    },
    currentIndex: {
      type: Number,
      default: 0,
    },
    chunkSize: {
      type: Number,
      default: 300,
    },
  },
  setup(props, { emit }) {
    const expanded = ref(false);
    const containerRef = ref<HTMLElement>();
    const contentRef = ref<HTMLElement>();
    const isOverflow = ref(false);
    const markInstance = ref<Mark | null>(null);
    const currentChunk = ref(0);
    const isLoading = ref(false);
    const chunks = ref<string[]>([]);
    const renderChunks = ref<string[]>([]);
    const CHUNKS_PER_RENDER = 10;

    // 将长文本分割成固定大小的块
    const splitIntoChunks = (text: string) => {
      const result: string[] = [];
      for (let i = 0; i < text.length; i += props.chunkSize) {
        result.push(text.slice(i, i + props.chunkSize));
      }
      return result;
    };

    // 初始化渲染
    const initRender = () => {
      chunks.value = splitIntoChunks(props.log);
      renderChunks.value = chunks.value.slice(0, CHUNKS_PER_RENDER);
      currentChunk.value = CHUNKS_PER_RENDER - 1;
      nextTick(() => {
        checkOverflow();
      });
    };

    // 检查内容是否超过最大高度
    const checkOverflow = () => {
      if (contentRef.value) {
        const { scrollHeight, offsetHeight } = contentRef.value;
        isOverflow.value = scrollHeight > offsetHeight;
      }
    };

    // 加载更多内容
    const loadMore = () => {
      if (isLoading.value || currentChunk.value >= chunks.value.length - 1) return;

      isLoading.value = true;
      setTimeout(() => {
        const nextChunk = Math.min(currentChunk.value + CHUNKS_PER_RENDER, chunks.value.length - 1);
        renderChunks.value = chunks.value.slice(0, nextChunk + 1);
        currentChunk.value = nextChunk;
        isLoading.value = false;
        updateHighlight();
      }, 50);
    };

    // 检查是否需要加载更多
    const checkLoadMore = () => {
      if (!contentRef.value || isLoading.value) return;
      const { scrollTop, scrollHeight, clientHeight } = contentRef.value;
      if (scrollHeight - scrollTop - clientHeight < 1) {
        loadMore();
      }
    };

    // 展开/收起处理
    const toggleExpand = () => {
      expanded.value = !expanded.value;
      if (expanded.value) {
        // 展开时，如果内容不足，加载更多
        if (currentChunk.value < CHUNKS_PER_RENDER - 1) {
          loadMore();
        }
      } else {
        // 收起时，恢复到初始渲染状态
        renderChunks.value = chunks.value.slice(0, CHUNKS_PER_RENDER);
        currentChunk.value = CHUNKS_PER_RENDER - 1;
        if (contentRef.value) {
          contentRef.value.scrollTop = 0;
        }
      }
    };

    // 更新高亮
    const updateHighlight = () => {
      if (!markInstance.value || !props.searchValue) {
        markInstance.value?.unmark();
        return;
      }

      const options = {
        caseSensitive: props.matchMode.caseSensitive,
        separateWordSearch: props.matchMode.wordMatch,
        wildcards: props.matchMode.regexMode ? 'enabled' : 'disabled',
        each: (element: Element, index: number) => {
          if (index === props.currentIndex - 1) {
            element.classList.add('current');
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
          } else {
            element.classList.remove('current');
          }
        },
      };

      markInstance.value.unmark();
      markInstance.value.mark(props.searchValue, options);
    };

    onMounted(() => {
      initRender();
      window.addEventListener('resize', checkOverflow);
      if (contentRef.value) {
        markInstance.value = new Mark(contentRef.value);
        contentRef.value.addEventListener('scroll', checkLoadMore);
      }
    });

    onUnmounted(() => {
      window.removeEventListener('resize', checkOverflow);
      if (contentRef.value) {
        contentRef.value.removeEventListener('scroll', checkLoadMore);
      }
    });

    // 监听 props.log 变化
    watch(
      () => props.log,
      () => {
        initRender();
      },
    );

    // 监听搜索条件变化
    watch(() => props.searchValue, updateHighlight);
    watch(() => props.matchMode, updateHighlight, { deep: true });
    watch(() => props.currentIndex, updateHighlight);

    return () => (
      <div
        class='cli-result-line'
        ref={containerRef}
      >
        <span class='cli-result-line-number'>{props.lineNumber}</span>
        <div class='cli-result-line-content-wrapper'>
          <div
            class={['cli-result-line-content', { 'is-expanded': expanded.value }]}
            ref={contentRef}
          >
            {renderChunks.value.map((line, idx) => (
              <span
                key={idx}
                class='log-line-item'
              >
                {line}
              </span>
            ))}
            {isLoading.value && (
              <div class='loading-more'>
                <span class='loading-spinner'></span>
                加载更多...
              </div>
            )}
          </div>
          {isOverflow.value && !expanded.value && (
            <div
              class='expand-button'
              onClick={toggleExpand}
            >
              展开更多
            </div>
          )}
          {expanded.value && (
            <div
              class='collapse-button'
              onClick={toggleExpand}
            >
              收起
            </div>
          )}
        </div>
      </div>
    );
  },
});

// 主组件
export default defineComponent({
  name: 'CliResult',
  props: {
    searchValue: {
      type: String,
      default: '',
    },
    matchMode: {
      type: Object,
      default: () => ({
        caseSensitive: false,
        regexMode: false,
        wordMatch: false,
      }),
    },
    currentIndex: {
      type: Number,
      default: 0,
    },
  },
  setup(props) {
    // 模拟大量数据
    const generateLargeLog = (index: number) => {
      const baseLog = `log: Mar 5 15:12:${String(index).padStart(2, '0')} VM_1_7_centos systemd:`;
      if (index % 3 === 0) {
        // 生成超长日志
        const lines = [];
        for (let i = 0; i < 10000; i++) {
          lines.push(
            `Line ${i + 1}: This is a very long log line with detailed information about system operations and events that occurred at timestamp ${Date.now() + i}`,
          );
        }
        return baseLog + '\n' + lines.join('\n');
      } else if (index % 5 === 0) {
        // 生成中等长度日志
        const lines = [];
        for (let i = 0; i < 15; i++) {
          lines.push(`Error line ${i + 1}: Error details and stack trace information`);
        }
        return baseLog + '\n' + lines.join('\n');
      } else {
        // 普通短日志
        return baseLog + ` Regular log entry ${index}`;
      }
    };

    // 生成测试数据（500条）
    const allLogs = ref<string[]>(Array.from({ length: 1 }, (_, i) => generateLargeLog(i)));

    return () => (
      <div class='cli-result-container'>
        <div class='cli-result-content'>
          {allLogs.value.map((log, index) => (
            <VirtualLogLine
              key={index}
              log={log}
              lineNumber={index + 1}
              maxHeight={200}
              searchValue={props.searchValue}
              matchMode={props.matchMode}
              currentIndex={props.currentIndex}
            />
          ))}
        </div>
      </div>
    );
  },
});
