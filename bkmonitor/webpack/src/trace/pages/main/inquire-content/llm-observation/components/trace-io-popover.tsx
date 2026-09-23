import { type PropType, defineComponent } from 'vue';

import { Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import { formatCompactToken } from '../utils/transform';

import type { LlmTraceView } from '../utils/typings';

import './trace-io-popover.scss';

/**
 * Trace 块标题悬停 Popover。
 * 文案来自 list_llm_flows traces[].input / output 汇总字段，非单个 Span 解析结果。
 */
type IoMetaItem = {
  label: string;
  value: string;
};

export default defineComponent({
  name: 'LlmTraceIoPopover',
  props: {
    trace: {
      type: Object as PropType<LlmTraceView>,
      required: true,
    },
  },
  setup(props) {
    const { t } = useI18n();

    /** 阻止冒泡，避免触发 Trace 块折叠/展开 */
    const handleCopy = (event: MouseEvent, text: string) => {
      event.preventDefault();
      event.stopPropagation();
      if (!text) return;
      copyText(text, (msg: string) => {
        Message({ message: msg, theme: 'error' });
      });
      Message({ message: t('复制成功'), theme: 'success' });
    };

    const renderMeta = (items: IoMetaItem[]) => {
      if (!items.length) return null;
      return (
        <div class='llm-trace-io-meta'>
          {items.flatMap((item, index) => {
            const nodes = [];
            if (index > 0) {
              nodes.push(
                <span
                  key={`divider-${item.label}`}
                  class='llm-trace-io-meta-divider'
                />
              );
            }
            nodes.push(
              <span
                key={item.label}
                class='llm-trace-io-meta-item'
              >
                {`${item.label}：${item.value}`}
              </span>
            );
            return nodes;
          })}
        </div>
      );
    };

    const renderPreview = (text: string, theme: 'input' | 'output') => (
      <div class={['llm-trace-io-preview', `is-${theme}`]}>
        <p class='llm-trace-io-preview-text'>{text}</p>
        <i
          class='icon-monitor icon-mc-copy llm-trace-io-copy'
          onClick={event => handleCopy(event, text)}
        />
      </div>
    );

    return () => {
      const { trace } = props;
      const inputMetas = [
        trace.userId ? { label: 'User ID', value: trace.userId } : null,
        trace.conversationId ? { label: t('会话'), value: trace.conversationId } : null,
      ].filter((item): item is IoMetaItem => Boolean(item));
      const outputMetas = [
        { label: t('总 Tokens'), value: formatCompactToken(trace.totalTokens) },
        { label: t('输入 Tokens'), value: formatCompactToken(trace.inputTokens) },
        { label: t('输出 Tokens'), value: formatCompactToken(trace.outputTokens) },
      ];

      return (
        <div class='llm-trace-io-content'>
          <section class='llm-trace-io-section'>
            <div class='llm-trace-io-head'>
              <span class='llm-trace-io-avatar is-input'>
                <i class='icon-monitor icon-a-useryonghu' />
              </span>
              <div class='llm-trace-io-head-main'>
                <p class='llm-trace-io-title'>{t('用户输入')}</p>
                {renderMeta(inputMetas)}
              </div>
            </div>
            {renderPreview(trace.input, 'input')}
          </section>
          <section class='llm-trace-io-section'>
            <div class='llm-trace-io-head'>
              <span class='llm-trace-io-avatar is-output'>
                <i class='icon-monitor icon-zhinengti' />
              </span>
              <div class='llm-trace-io-head-main'>
                <p class='llm-trace-io-title'>{t('最终输出')}</p>
                {renderMeta(outputMetas)}
              </div>
            </div>
            {renderPreview(trace.output, 'output')}
          </section>
        </div>
      );
    };
  },
});
