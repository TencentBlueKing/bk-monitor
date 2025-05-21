import { defineComponent, ref } from 'vue';
import './grep-cli.scss';

const fieldList = [{ id: 'log', name: 'log' }];

export default defineComponent({
  name: 'GrepCli',
  setup() {
    const field = ref('log');
    const value = ref('');

    // 选择字段
    const handleFieldChange = (id: string) => {
      field.value = id;
    };
    // 输入
    const handleInput = (e: Event) => {
      value.value = (e.target as HTMLTextAreaElement).value;
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
            <textarea
              class='grep-cli-textarea'
              placeholder='-- INSERT --'
              value={value.value}
              onInput={handleInput}
              style='height: 36px; font-size: 14px; border-radius: 2px; resize: none;'
            />
          </div>
        </div>
        {/* 右侧匹配栏 */}
        <div class='grep-cli-right'>
          <div class='grep-cli-ui-tools'>
            <bk-input
              placeholder='搜索'
              size='small'
              style='width: 160px;'
            ></bk-input>
            <button class='grep-cli-tool-btn'>Aa</button>
            <button class='grep-cli-tool-btn'>ab</button>
            <button class='grep-cli-tool-btn'>*</button>
          </div>
          <span class='grep-cli-no-result'>无结果</span>
        </div>
      </div>
    );
  },
});
