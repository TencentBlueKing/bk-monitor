import { defineComponent, ref } from 'vue';
import TextSegmentation from '../../retrieve-v2/search-result-panel/log-result/text-segmentation';

import './grep-cli-result.scss';

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
        {allLogs.value.map((log, index) => (
          <div class='cli-result-line'>
            <span class='cli-result-line-number'>{index + 1}</span>
            <div class='cli-result-line-content-wrapper'>
              <TextSegmentation
                field={{ field_name: 'log' }}
                content={log}
                data={{}}
              />
            </div>
          </div>
        ))}
      </div>
    );
  },
});
