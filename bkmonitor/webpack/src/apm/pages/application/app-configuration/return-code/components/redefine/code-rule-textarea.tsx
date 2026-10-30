import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './code-rule-textarea.scss';

interface IEvents {
  onChange: (value: string) => void;
}

interface IProps {
  value: string;
}

/** 最大高度（10 行 × 20px 行高 + 上下内边距 10px），超出后纵向滚动 */
const MAX_HEIGHT = 210;

/** 返回码输入框：bk-input 的 textarea 不支持 autosize，这里按内容自适应高度 */
@Component
export default class CodeRuleTextarea extends tsc<IProps, IEvents> {
  @Prop({ type: String, default: '' }) value: string;

  @Ref('inputRef') inputRef!: any;

  resizeObserver: ResizeObserver = null;
  lastWidth = 0;

  get textareaEl(): HTMLTextAreaElement {
    return this.inputRef?.$refs?.textarea;
  }

  @Watch('value')
  handleValueChange() {
    this.$nextTick(this.resize);
  }

  mounted() {
    this.$nextTick(() => {
      this.resize();
      if (!this.textareaEl) return;
      this.lastWidth = this.textareaEl.clientWidth;
      // 列宽或窗口变化会改变折行数，仅宽度变化时重算，避免设置高度后自身触发循环
      this.resizeObserver = new ResizeObserver(entries => {
        const width = entries[0]?.contentRect?.width ?? 0;
        if (width === this.lastWidth) return;
        this.lastWidth = width;
        this.resize();
      });
      this.resizeObserver.observe(this.textareaEl);
    });
  }

  beforeDestroy() {
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
  }

  resize() {
    const el = this.textareaEl;
    if (!el) return;
    el.style.height = 'auto';
    const { scrollHeight } = el;
    el.style.height = `${Math.min(scrollHeight, MAX_HEIGHT)}px`;
    el.style.overflowY = scrollHeight > MAX_HEIGHT ? 'auto' : 'hidden';
  }

  handleKeydown(_value: string, event: KeyboardEvent) {
    // 返回码以逗号分隔，禁止回车换行，保持与原单行输入一致
    if (event.key === 'Enter') {
      event.preventDefault();
    }
  }

  handleChange(value: string) {
    // 粘贴内容中的换行与原单行 input 一样丢弃，避免影响逗号分隔的格式校验
    const newValue = (value ?? '').replace(/[\r\n]/g, '');
    if (newValue !== value) {
      // 去除换行后值可能与 prop 相同而不触发 bk-input 的 value watch，需主动同步其内部值
      this.inputRef?.setCurValue?.(newValue);
    }
    this.$emit('change', newValue);
  }

  render() {
    return (
      <bk-input
        ref='inputRef'
        ext-cls='code-rule-textarea'
        rows={1}
        type='textarea'
        value={this.value}
        on-change={this.handleChange}
        on-keydown={this.handleKeydown}
      />
    );
  }
}
