import { defineComponent, ref, computed, onMounted, onUnmounted } from 'vue';
import './grep-cli-result.scss';

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
  },
  setup(props) {
    const expanded = ref(false);
    const containerRef = ref<HTMLElement>();
    const contentRef = ref<HTMLElement>();
    const isOverflow = ref(false);
    const lineWidth = ref(0);
    const charWidth = ref(8); // 估算每个字符的平均宽度（像素）

    // 检查内容是否超过最大高度
    const checkOverflow = () => {
      if (contentRef.value && containerRef.value) {
        const contentHeight = contentRef.value.scrollHeight;
        isOverflow.value = contentHeight > props.maxHeight;
      }
    };

    // 计算每行可以容纳的字符数
    const calculateCharsPerLine = () => {
      if (containerRef.value) {
        // 获取父容器的实际宽度
        const parentWidth = containerRef.value.parentElement?.clientWidth || 0;
        // 减去行号宽度（40px）和其他padding（左右各10px）
        lineWidth.value = parentWidth - 60;
        return Math.floor(lineWidth.value / charWidth.value);
      }
      return 80; // 默认值
    };

    // 将长字符串分割成适合显示的行
    const splitIntoLines = (text: string) => {
      const charsPerLine = calculateCharsPerLine();
      const lines: string[] = [];
      let currentLine = '';
      let currentLength = 0;

      // 按空格分割文本
      const words = text.split(/\s+/);

      for (const word of words) {
        // 如果单词本身超过一行，需要强制换行
        if (word.length > charsPerLine) {
          if (currentLine) {
            lines.push(currentLine.trim());
            currentLine = '';
            currentLength = 0;
          }

          // 将长单词分段
          for (let i = 0; i < word.length; i += charsPerLine) {
            lines.push(word.slice(i, i + charsPerLine));
          }
          continue;
        }

        // 检查添加当前单词是否会超出当前行
        if (currentLength + word.length + 1 > charsPerLine) {
          lines.push(currentLine.trim());
          currentLine = word;
          currentLength = word.length;
        } else {
          if (currentLine) {
            currentLine += ' ' + word;
            currentLength += word.length + 1;
          } else {
            currentLine = word;
            currentLength = word.length;
          }
        }
      }

      if (currentLine) {
        lines.push(currentLine.trim());
      }

      return lines;
    };

    onMounted(() => {
      checkOverflow();
      // 监听窗口大小变化，重新计算换行
      window.addEventListener('resize', checkOverflow);
    });

    onUnmounted(() => {
      window.removeEventListener('resize', checkOverflow);
    });

    // 分割日志内容为行数组，用于行内虚拟滚动
    const logLines = computed(() => {
      return splitIntoLines(props.log);
    });

    // 判断是否需要截断
    const shouldTruncate = computed(() => {
      return logLines.value.length > 8;
    });

    // 显示的行数
    const displayLines = computed(() => {
      if (expanded.value || !shouldTruncate.value) {
        return logLines.value;
      }
      return logLines.value.slice(0, 8);
    });

    const toggleExpand = () => {
      expanded.value = !expanded.value;
    };

    return () => (
      <div
        class='cli-result-line'
        ref={containerRef}
      >
        <span class='cli-result-line-number'>{props.lineNumber}</span>
        <div class='cli-result-line-content-wrapper'>
          <div
            class={{
              'cli-result-line-content': true,
              expanded: expanded.value,
              truncated: !expanded.value && shouldTruncate.value,
            }}
            style={{
              maxHeight: expanded.value ? 'none' : `${props.maxHeight}px`,
            }}
            ref={contentRef}
          >
            {displayLines.value.map((line, idx) => (
              <div
                key={idx}
                class='log-line-item'
              >
                {line}
              </div>
            ))}
          </div>
          {shouldTruncate.value && (
            <button
              class='cli-result-expand-btn'
              onClick={toggleExpand}
            >
              {expanded.value ? '收起' : `展开更多 (${logLines.value.length - 8}行)`}
            </button>
          )}
        </div>
      </div>
    );
  },
});

// 主组件
export default defineComponent({
  name: 'CliResult',
  setup() {
    // 模拟大量数据
    const generateLargeLog = (index: number) => {
      const baseLog = `log: Mar 5 15:12:${String(index).padStart(2, '0')} VM_1_7_centos systemd:`;
      if (index % 3 === 0) {
        // 生成超长日志
        const lines = [];
        for (let i = 0; i < 50; i++) {
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
    const allLogs = ref<string[]>(Array.from({ length: 500 }, (_, i) => generateLargeLog(i + 1)));

    // 虚拟滚动配置
    const containerRef = ref<HTMLElement>();
    const itemHeight = 250; // 每个日志条目的估算高度
    const visibleCount = ref(20); // 可见条目数量
    const scrollTop = ref(0);
    const containerHeight = ref(600);

    // 计算可见范围
    const visibleRange = computed(() => {
      const start = Math.floor(scrollTop.value / itemHeight);
      const end = Math.min(
        start + visibleCount.value + 2, // 多渲染2个作为缓冲
        allLogs.value.length,
      );
      return { start: Math.max(0, start - 1), end }; // 前面也多渲染1个作为缓冲
    });

    // 可见的日志数据
    const visibleLogs = computed(() => {
      const { start, end } = visibleRange.value;
      return allLogs.value.slice(start, end).map((log, index) => ({
        log,
        originalIndex: start + index,
        lineNumber: start + index + 1,
      }));
    });

    // 总高度
    const totalHeight = computed(() => allLogs.value.length * itemHeight);

    // 偏移量
    const offsetY = computed(() => visibleRange.value.start * itemHeight);

    // 滚动处理
    const handleScroll = (event: Event) => {
      const target = event.target as HTMLElement;
      scrollTop.value = target.scrollTop;
    };

    // 更新容器尺寸
    const updateSize = () => {
      if (containerRef.value) {
        containerHeight.value = containerRef.value.clientHeight;
        visibleCount.value = Math.ceil(containerHeight.value / itemHeight) + 2;
      }
    };

    onMounted(() => {
      updateSize();
      window.addEventListener('resize', updateSize);
    });

    onUnmounted(() => {
      window.removeEventListener('resize', updateSize);
    });

    return () => (
      <div class='cli-result-container'>
        <div
          class='cli-result-log-panel'
          ref={containerRef}
          onScroll={handleScroll}
        >
          <div
            class='virtual-scroll-spacer'
            style={{ height: `${totalHeight.value}px` }}
          >
            <div
              class='virtual-scroll-content'
              style={{
                transform: `translateY(${offsetY.value}px)`,
                width: '100%',
              }}
            >
              {visibleLogs.value.map(item => (
                <VirtualLogLine
                  key={item.originalIndex}
                  log={item.log}
                  lineNumber={item.lineNumber}
                  maxHeight={200}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  },
});
