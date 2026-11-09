import { type PropType, type Ref, computed, defineComponent, inject, nextTick, shallowRef, watch } from 'vue';

import { useResizeObserver } from '@vueuse/core';
import { Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import MessageTooltip from '../../../../components/message-tooltip/message-tooltip';
import { useTraceStore } from '../../../../store/modules/trace';
import SpanIoKvs from '../../inquire-content/llm-observation/components/span-io-kvs';
import { useElementInView } from '../hooks/use-element-in-view';
import { LLM_TOOL_CALL_MAP_KEY } from '../hooks/use-llm-tool-calls';
import { findRelatedToolSpan } from '../utils/find-related-tool-span';
import { formatJsonDisplay, isRecord, parseJsonValue, stringifyContent } from '../utils/helpers';
import { formatToolCallDuration } from '../utils/match-tool-call';
import { LLM_OPEN_SPAN_DETAIL_KEY } from '../utils/open-span-detail';
import { flattenKvPairs } from '../utils/parse-input';
import { isActiveHitOnBlock, LLM_OBSERVATION_SEARCH_KEY } from '../utils/search';
import ErrorAlert from './error-alert';
import HighlightText from './highlight-text';
import JsonCodeBlock from './json-code-block';
import ToolDescBar from './tool-desc-bar';

import type { LlmDetailSliderContent } from './detail-slider';
import type { LlmTimelinePart, LlmTimelineRole } from '../utils/typings';

import './timeline-message-row.scss';

const ROLE_META: Record<LlmTimelineRole, { icon: string; labelKey: string }> = {
  user: { icon: 'icon-a-chatqipao', labelKey: '用户' },
  model: { icon: 'icon-LLM', labelKey: '模型' },
  system: { icon: 'icon-neizhi', labelKey: '系统' },
  thinking: { icon: 'icon-tuiliguocheng', labelKey: '思考' },
  tool: { icon: 'icon-Tool', labelKey: '工具' },
};

/** 空输入 / 输出的占位文本：这些值只需占「--」宽度，不撑满整行 */
const EMPTY_PREVIEW_TEXT = new Set(['--', '{}', '[]', 'null']);

export default defineComponent({
  name: 'LlmTimelineMessageRow',
  props: {
    part: {
      type: Object as PropType<LlmTimelinePart>,
      required: true,
    },
    connectTop: {
      type: Boolean,
      default: false,
    },
    connectBottom: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    viewAlone: (_detail: LlmDetailSliderContent) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const store = useTraceStore();
    const expanded = shallowRef(false);
    const search = inject(LLM_OBSERVATION_SEARCH_KEY, null);
    const currentSpanId = inject<Ref<string>>('spanId', shallowRef(''));
    const openSpanDetail = inject(LLM_OPEN_SPAN_DETAIL_KEY, null);
    const toolCallMap = inject(LLM_TOOL_CALL_MAP_KEY, null);
    const matchedToolCall = computed(() =>
      props.part.role === 'tool' ? toolCallMap?.value.get(props.part.id) : undefined
    );
    const durationText = computed(() => {
      const toolCall = matchedToolCall.value;
      if (!toolCall) return '';
      return formatToolCallDuration(toolCall.startTime, toolCall.elapsedTime);
    });
    const canViewSpan = computed(() => Boolean(matchedToolCall.value?.spanId));
    /** 工具执行失败时的报错信息，接口 status.message 优先 */
    const toolErrorMessage = computed(() =>
      props.part.role === 'tool' && props.part.isError ? matchedToolCall.value?.statusMessage.trim() || '' : ''
    );
    const roleMeta = computed(() => ROLE_META[props.part.role]);
    const argumentsPreview = computed(() => toPreview(props.part.arguments));
    const responsePreview = computed(() => toPreview(props.part.response));
    const hasDescription = computed(() => Boolean(props.part.description?.trim()));
    const isEmptyArguments = computed(() => {
      // 参数缺省时上游会补成 {}，与空对象一并按「暂无参数」处理
      const parsed = parseJsonValue(props.part.arguments ?? {});
      return isRecord(parsed) && !Object.keys(parsed).length;
    });
    const canExpand = computed(
      () => !props.part.isPlaceholder && (props.part.role === 'tool' || Boolean(props.part.content))
    );
    // 行内 KV 预览会为每个键值创建测量与 Popover 实例，屏外行先只渲染纯文本占位
    const rowRef = shallowRef<HTMLElement>();
    const setRowRef = (el: unknown) => {
      rowRef.value = el instanceof HTMLElement ? el : undefined;
    };
    const { inView } = useElementInView(rowRef);
    // 展开后的系统 / 模型正文元素，「独立查看」仅在正文超过一行时才需要
    const systemBodyRef = shallowRef<HTMLElement>();
    const setSystemBodyRef = (el: unknown) => {
      systemBodyRef.value = el instanceof HTMLElement ? el : undefined;
    };
    const isSystemBodyMultiline = shallowRef(false);
    const syncSystemBodyLines = () => {
      const el = systemBodyRef.value;
      if (!el) {
        isSystemBodyMultiline.value = false;
        return;
      }
      const lineHeight = Number.parseFloat(getComputedStyle(el).lineHeight) || 20;
      isSystemBodyMultiline.value = el.scrollHeight > lineHeight + 1;
    };
    useResizeObserver(systemBodyRef, syncSystemBodyLines);
    watch(
      () => [expanded.value, props.part.content],
      () => nextTick(syncSystemBodyLines),
      { immediate: true }
    );

    watch(
      () => [search?.activeIndex.value, search?.activeHit.value] as const,
      ([, hit]) => {
        if (!canExpand.value || !hit) return;
        if (hit.expandId === props.part.id || isActiveHitOnBlock(hit, props.part.searchBlockId)) {
          expanded.value = true;
        }
      },
      { immediate: true }
    );

    const handleToggle = () => {
      if (!canExpand.value) return;
      expanded.value = !expanded.value;
    };

    const handleCopy = () => {
      copyText(props.part.content, (msg: string) => {
        Message({ message: msg, theme: 'error' });
      });
      Message({ message: t('复制成功'), theme: 'success' });
    };

    const handleCopyTool = (event: Event) => {
      event.stopPropagation();
      const text = formatJsonDisplay({
        name: props.part.toolName || '',
        arguments: props.part.arguments ?? {},
        ...(props.part.response !== undefined ? { response: props.part.response } : {}),
      });
      copyText(text, (msg: string) => {
        Message({ message: msg, theme: 'error' });
      });
      Message({ message: t('复制成功'), theme: 'success' });
    };

    const handleViewSpan = (event: Event) => {
      event.stopPropagation();
      const spanId = matchedToolCall.value?.spanId || '';
      if (!spanId || !openSpanDetail) {
        Message({ message: t('暂无关联 Span'), theme: 'warning' });
        return;
      }
      const related = findRelatedToolSpan(store.traceTree?.spans || [], currentSpanId.value, {
        ...props.part,
        spanId,
      });
      if (related) {
        openSpanDetail(related);
        return;
      }
      openSpanDetail({ span_id: spanId, spanID: spanId });
    };

    const renderPairs = (preview: ReturnType<typeof toPreview>, className?: string) => {
      // 空参数只渲染占位符，容器按内容宽度收缩，避免箭头左侧留出大片空白
      const isEmpty = !preview.pairs.length && EMPTY_PREVIEW_TEXT.has(preview.text);
      return (
        <div class={['llm-timeline-row-pairs', className, { 'is-empty': isEmpty }]}>
          {preview.pairs.length ? (
            inView.value ? (
              // KV 按剩余宽度依次铺开，放不下的直接隐藏，避免 value 过长把 key 压没
              <SpanIoKvs pairs={preview.pairs} />
            ) : (
              // 屏外先出 key: value 纯文本，进入视口后再换成可测量、可悬浮的 KV 预览
              <span class='llm-timeline-row-pairs-text'>
                {preview.pairs.map(pair => `${pair.key}:${pair.value}`).join(' ')}
              </span>
            )
          ) : (
            <MessageTooltip
              title={t('详细信息')}
              detail={preview.text}
              placement='top'
              onlyOnOverflow
            >
              <span class='llm-timeline-row-pairs-text'>{preview.text}</span>
            </MessageTooltip>
          )}
        </div>
      );
    };

    const renderPreview = () => {
      if (props.part.role === 'tool') {
        return (
          <div class='llm-timeline-row-tool'>
            <span
              class='llm-timeline-row-tool-name'
              v-overflow-tips
            >
              {props.part.searchBlockId ? (
                <HighlightText
                  blockId={`${props.part.searchBlockId}:name`}
                  text={props.part.toolName || t('未命名工具')}
                />
              ) : (
                props.part.toolName || t('未命名工具')
              )}
            </span>
            {durationText.value ? (
              <span class='llm-timeline-row-duration'>
                <i class='icon-monitor icon-jishiqi' />
                <span>{durationText.value}</span>
              </span>
            ) : null}
            <div class='llm-timeline-row-io'>
              {renderPairs(argumentsPreview.value)}
              {props.part.response !== undefined ? (
                <>
                  <i class='icon-monitor icon-next-one llm-timeline-row-arrow' />
                  {renderPairs(responsePreview.value, 'llm-timeline-row-result')}
                </>
              ) : null}
            </div>
          </div>
        );
      }
      if (props.part.isPlaceholder) {
        return <span class='llm-timeline-row-placeholder'>{t('仅工具调用')}</span>;
      }
      return (
        <div class='llm-timeline-row-text'>
          {props.part.searchBlockId ? (
            <HighlightText
              blockId={props.part.searchBlockId}
              text={props.part.content}
            />
          ) : (
            props.part.content
          )}
        </div>
      );
    };

    return () => (
      <div
        ref={setRowRef}
        class={[
          'llm-timeline-row',
          `is-${props.part.role}`,
          { 'is-expanded': expanded.value, 'is-error': props.part.isError },
        ]}
      >
        {props.connectTop ? <span class='llm-timeline-row-line is-top' /> : null}
        {props.connectBottom && !expanded.value ? <span class='llm-timeline-row-line is-bottom' /> : null}
        <div
          class='llm-timeline-row-main'
          onClick={handleToggle}
        >
          {props.part.showIndex ? <span class='llm-timeline-row-index'>[{props.part.messageIndex}]</span> : null}
          <span class={['llm-timeline-row-tag', `is-${props.part.role}`]}>
            <i class={['icon-monitor', roleMeta.value.icon]} />
            <span>{t(roleMeta.value.labelKey)}</span>
          </span>
          {props.part.isError ? (
            <MessageTooltip
              detail={matchedToolCall.value?.statusMessage}
              placement='top'
            >
              <i class='icon-monitor icon-yichang llm-timeline-row-error' />
            </MessageTooltip>
          ) : null}
          <div class='llm-timeline-row-preview'>{renderPreview()}</div>
          {props.part.role === 'tool' || canExpand.value ? (
            <div class='llm-timeline-row-aside'>
              {props.part.role === 'tool' ? (
                <div class='llm-timeline-row-actions'>
                  {canViewSpan.value ? (
                    <div
                      class='llm-timeline-row-action'
                      onClick={handleViewSpan}
                    >
                      <i class='icon-monitor icon-chakan' />
                      <span>{t('详情')}</span>
                    </div>
                  ) : null}
                  <div
                    class='llm-timeline-row-action'
                    onClick={handleCopyTool}
                  >
                    <i class='icon-monitor icon-mc-copy' />
                    <span>{t('复制')}</span>
                  </div>
                </div>
              ) : null}
              {canExpand.value ? (
                <i
                  class={[
                    'icon-monitor',
                    expanded.value ? 'icon-arrow-down' : 'icon-arrow-right',
                    'llm-timeline-row-toggle',
                  ]}
                />
              ) : null}
            </div>
          ) : null}
        </div>
        {expanded.value ? (
          <div class='llm-timeline-row-detail'>
            {props.part.role === 'tool' ? (
              <div class='llm-timeline-row-tool-detail'>
                {hasDescription.value ? (
                  <ToolDescBar
                    descBlockId={`${props.part.searchBlockId}:desc`}
                    description={props.part.description || ''}
                    name={t('工具描述')}
                  />
                ) : null}
                {toolErrorMessage.value ? <ErrorAlert message={toolErrorMessage.value} /> : null}
                <div class='llm-timeline-row-tool-panels'>
                  <JsonCodeBlock
                    data={props.part.arguments ?? {}}
                    empty={isEmptyArguments.value}
                    emptyText={t('暂无参数')}
                    searchBlockId={`${props.part.searchBlockId}:args`}
                    title={t('调用参数')}
                    onViewAlone={(data, title) => emit('viewAlone', { kind: 'json', data, title })}
                  />
                  {props.part.response !== undefined ? (
                    <JsonCodeBlock
                      data={props.part.response}
                      searchBlockId={`${props.part.searchBlockId}:resp`}
                      title={t('返回结果')}
                      onViewAlone={(data, title) => emit('viewAlone', { kind: 'json', data, title })}
                    />
                  ) : null}
                </div>
              </div>
            ) : (
              <div class='llm-timeline-row-system-detail'>
                <div class='llm-timeline-row-system-actions'>
                  <div
                    class='llm-timeline-row-system-action'
                    onClick={handleCopy}
                  >
                    <i class='icon-monitor icon-mc-copy' />
                    <span>{t('复制信息')}</span>
                  </div>
                  {isSystemBodyMultiline.value ? (
                    <div
                      class='llm-timeline-row-system-action'
                      onClick={() =>
                        emit('viewAlone', { kind: 'text', text: props.part.content, title: t(roleMeta.value.labelKey) })
                      }
                    >
                      <i class='icon-monitor icon-sidebar' />
                      <span>{t('独立查看')}</span>
                    </div>
                  ) : null}
                </div>
                <div
                  ref={setSystemBodyRef}
                  class='llm-timeline-row-system-body'
                >
                  {props.part.searchBlockId ? (
                    <HighlightText
                      blockId={props.part.searchBlockId}
                      text={props.part.content}
                    />
                  ) : (
                    props.part.content
                  )}
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    );
  },
});

function toPreview(value: unknown) {
  const parsed = parseJsonValue(value);
  const pairs = flattenKvPairs(parsed);
  return {
    pairs,
    text: pairs.length ? '' : (parsed === null ? 'null' : stringifyContent(parsed)).replace(/\s+/g, ' ').trim() || '--',
  };
}
