import { defineComponent, ref, computed } from 'vue';
import './grep-cli-result.scss';

export default defineComponent({
  name: 'CliResult',
  setup() {
    // 示例数据，可替换为实际传入
    const logs = ref<string[]>(
      Array.from(
        { length: 24 },
        (_, i) => `log: Mar 5 15:12:01 VM_1_7_centos systemd:Started Session 81700023 of user root.`,
      ),
    );

    // 行号
    const lineNumbers = computed(() => logs.value.map((_, idx) => idx + 1));

    return () => (
      <div class='cli-result-container'>
        {/* 左侧日志区 */}
        <div class='cli-result-log-panel'>
          {logs.value.map((line, idx) => (
            <div
              class='cli-result-line'
              key={idx}
            >
              <span class='cli-result-line-number'>{lineNumbers.value[idx]}</span>
              <span class='cli-result-line-content'>{line}</span>
            </div>
          ))}
        </div>
      </div>
    );
  },
});
