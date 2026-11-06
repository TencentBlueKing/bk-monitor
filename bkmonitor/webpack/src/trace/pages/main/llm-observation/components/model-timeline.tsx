import { type PropType, computed, defineComponent, inject, provide, shallowRef, watch } from 'vue';

import { Radio } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { LLM_TOOL_CALL_MAP_KEY, useLlmToolCalls } from '../hooks/use-llm-tool-calls';
import { useProgressiveRender } from '../hooks/use-progressive-render';
import { applyToolCallStatus, matchTimelineToolCalls } from '../utils/match-tool-call';
import { parseModelTimeline } from '../utils/parse-model-timeline';
import { isActiveHitOnBlock, LLM_OBSERVATION_SEARCH_KEY, LLM_SEARCH_SECTION } from '../utils/search';
import CollapseSection from './collapse-section';
import DetailSlider, { type LlmDetailSliderContent } from './detail-slider';
import HighlightText from './highlight-text';
import JsonCodeBlock from './json-code-block';
import TimelineMessageRow from './timeline-message-row';
import ToolDescBar from './tool-desc-bar';

import type { LlmSearchHit } from '../utils/search';
import type { LlmTimelineFilter, LlmTimelineMessage, LlmToolDefinition } from '../utils/typings';

import './model-timeline.scss';

type FilterTab = {
  disabled?: boolean;
  icon?: string;
  id: LlmTimelineFilter;
  label: string;
};

export default defineComponent({
  name: 'LlmModelTimeline',
  props: {
    attributes: {
      type: Object as PropType<Record<string, unknown>>,
      default: () => ({}),
    },
  },
  setup(props) {
    const { t } = useI18n();
    const { toolCalls } = useLlmToolCalls();

    const search = inject(LLM_OBSERVATION_SEARCH_KEY, null);

    const filter = shallowRef<LlmTimelineFilter>('all');
    const inputExpanded = shallowRef(false);
    const selectedToolName = shallowRef('');
    const detail = shallowRef<LlmDetailSliderContent | null>(null);
  
    const parsedTimeline = computed(() => parseModelTimeline(props.attributes));
    const toolCallMap = computed(() => {
      const parts = [...parsedTimeline.value.inputMessages, ...parsedTimeline.value.outputMessages].flatMap(item =>
        item.parts.filter(part => part.role === 'tool')
      );
      return matchTimelineToolCalls(parts, toolCalls.value);
    });

    provide(LLM_TOOL_CALL_MAP_KEY, toolCallMap);
    
    const timeline = computed(() => applyToolCallStatus(parsedTimeline.value, toolCallMap.value));
    const lastInputIndex = computed(
      () => timeline.value.inputMessages[timeline.value.inputMessages.length - 1]?.index ?? 0
    );
    const selectedTool = computed(
      () =>
        timeline.value.availableTools.find(item => item.name === selectedToolName.value) ||
        timeline.value.availableTools[0]
    );
    const filterTabs = computed<FilterTab[]>(() => [
      { id: 'all', label: t('全部') },
      { id: 'last-input', label: t('最后一轮输入') },
      { id: 'output', label: t('输出') },
      {
        id: 'error',
        icon: 'icon-yichang',
        label: t('异常({0})', [timeline.value.errorCount]),
        disabled: timeline.value.errorCount === 0,
      },
    ]);

    // 过滤后的完整消息列表（不含「只留首尾」的省略），分片渲染与省略展示都基于它
    const filteredInputMessages = computed(() =>
      filterMessages(timeline.value.inputMessages, filter.value, lastInputIndex.value)
    );
    const filteredOutputMessages = computed(() =>
      filterMessages(timeline.value.outputMessages, filter.value, lastInputIndex.value)
    );
    // 上千行同步创建会阻塞主线程数秒，改为分批提交：首屏 30 条，其余按帧补齐
    const inputRender = useProgressiveRender(() => filteredInputMessages.value.length);
    const outputRender = useProgressiveRender(() => filteredOutputMessages.value.length);
    const showSystem = computed(() => filter.value === 'all' && timeline.value.systemPrompts.length > 0);
    const showTools = computed(() => filter.value === 'all' && timeline.value.availableTools.length > 0);
    const showInput = computed(
      () =>
        (filter.value === 'all' || filter.value === 'last-input' || filter.value === 'error') &&
        (filter.value === 'error' ? filteredInputMessages.value.length > 0 : timeline.value.inputMessages.length > 0)
    );
    const showOutput = computed(
      () =>
        (filter.value === 'all' || filter.value === 'output' || filter.value === 'error') &&
        (filter.value === 'error' ? filteredOutputMessages.value.length > 0 : timeline.value.outputMessages.length > 0)
    );
    // 输入区只有在「非全部筛选」或已展开时才走分片渲染；折叠态只渲染首尾两条，无需分片
    const inputNeedsPaging = computed(() => filter.value !== 'all' || inputExpanded.value);
    const activeHit = computed(() => search?.activeHit.value ?? null);
    // 搜索命中所处的消息序号 + 1，保证定位目标一定落在本批已渲染范围内。
    // 命中判定按 tab 而非分区 id —— 消息命中的分区是 input-user / output-model 等子分区，
    // 与折叠分区 timeline-input / timeline-output 不会相等，须与定位 watch 保持同一口径。
    const activeInputHitCount = computed(() =>
      activeHit.value?.tab === 'input' ? resolveHitMessageCount(filteredInputMessages.value, activeHit.value) : 0
    );
    const activeOutputHitCount = computed(() =>
      activeHit.value?.tab === 'output' ? resolveHitMessageCount(filteredOutputMessages.value, activeHit.value) : 0
    );
    const hasContent = computed(
      () =>
        showSystem.value ||
        showTools.value ||
        showInput.value ||
        showOutput.value ||
        timeline.value.inputMessages.length > 0 ||
        timeline.value.outputMessages.length > 0
    );

    watch(
      () => props.attributes,
      () => {
        filter.value = 'all';
        inputExpanded.value = false;
        // 快照变更后消息 id 全变，必须丢弃上一份已渲染进度重新分片
        inputRender.reset();
        outputRender.reset();
        // 输出区始终走分片渲染，输入区仅在展开 / 非「全部」筛选时才需要
        outputRender.start();
      },
      { immediate: true }
    );

    watch(
      () => timeline.value.availableTools,
      tools => {
        if (!tools.find(item => item.name === selectedToolName.value)) {
          selectedToolName.value = tools[0]?.name || '';
        }
      },
      { immediate: true }
    );

    watch(
      () => [search?.activeIndex.value, search?.activeHit.value] as const,
      ([, hit]) => {
        if (!hit) return;
        if (hit.toolName && timeline.value.availableTools.some(item => item.name === hit.toolName)) {
          selectedToolName.value = hit.toolName;
        }
        if (hit.sectionId === LLM_SEARCH_SECTION.timelineInput || hit.tab === 'input') {
          const message = timeline.value.inputMessages.find(item =>
            item.parts.some(part => part.id === hit.expandId || hit.blockId.startsWith(part.searchBlockId))
          );
          if (message && filter.value !== 'all' && filter.value !== 'last-input' && filter.value !== 'error') {
            filter.value = 'all';
          }
          if (message && message.index !== 1 && message.index !== lastInputIndex.value) {
            inputExpanded.value = true;
            // 命中行可能在首批之外，按命中位置抬高本次渲染条数，避免定位时目标尚未挂载
            inputRender.start(activeInputHitCount.value);
          }
        }
        if (hit.sectionId === LLM_SEARCH_SECTION.timelineOutput || hit.tab === 'output') {
          if (filter.value === 'last-input') filter.value = 'all';
          outputRender.start(activeOutputHitCount.value);
        }
      }
    );

    const handleFilterChange = (value: LlmTimelineFilter) => {
      filter.value = value;
      if (value === 'last-input') inputExpanded.value = false;
      // 筛选变化后可见集合改变，重置再按新集合分片；未进入分片态时 start 不会真正启动计时器
      inputRender.reset();
      outputRender.reset();
      inputRender.start();
      outputRender.start();
    };

    const handleExpandInput = () => {
      inputExpanded.value = true;
      inputRender.start();
    };

    const handleResetInput = (event: Event) => {
      event.stopPropagation();
      inputExpanded.value = false;
      inputRender.reset();
    };

    const openJsonDetail = (data: unknown, title: string) => {
      detail.value = { kind: 'json', title, data };
    };

    const renderMessages = (messages: LlmTimelineMessage[]) =>
      messages.map(message =>
        message.parts.map((part, partIndex) => (
          <TimelineMessageRow
            key={part.id}
            connectBottom={partIndex < message.parts.length - 1}
            connectTop={partIndex > 0}
            part={part}
            onViewAlone={item => {
              detail.value = item;
            }}
          />
        ))
      );

    const renderAvailableTools = (tools: LlmToolDefinition[]) => (
      <div class='llm-model-timeline-tools'>
        <div class='llm-model-timeline-tool-tags'>
          {tools.map(tool => (
            <div
              key={tool.name}
              class={['llm-model-timeline-tool-tag', { 'is-active': selectedTool.value?.name === tool.name }]}
              onClick={() => {
                selectedToolName.value = tool.name;
              }}
            >
              <HighlightText
                blockId={`input:tool:${tool.name}:name`}
                text={tool.name.trim()}
              />
            </div>
          ))}
        </div>
        {selectedTool.value ? (
          <ToolDescBar
            descBlockId={`input:tool:${selectedTool.value.name}:desc`}
            description={selectedTool.value.description}
            name={t('工具描述')}
          />
        ) : null}
        <JsonCodeBlock
          data={selectedTool.value?.parameters ?? {}}
          searchBlockId={selectedTool.value ? `input:tool:${selectedTool.value.name}:params` : ''}
          title={t('调用参数')}
          onViewAlone={openJsonDetail}
        />
      </div>
    );

    return () => (
      <div class='llm-model-timeline'>
        <div
          aria-hidden='true'
          class='llm-model-timeline-sticky-mask'
        />
        <Radio.Group
          class='llm-model-timeline-filters'
          modelValue={filter.value}
          type='capsule'
          onChange={handleFilterChange}
        >
          {filterTabs.value.map(tab => (
            <Radio.Button
              key={tab.id}
              class='llm-model-timeline-filter'
              disabled={tab.disabled}
              label={tab.id}
            >
              <span class='llm-model-timeline-filter-inner'>
                {tab.icon ? <i class={['icon-monitor', tab.icon, 'llm-model-timeline-filter-icon']} /> : null}
                <span>{tab.label}</span>
              </span>
            </Radio.Button>
          ))}
        </Radio.Group>
        {!hasContent.value ? (
          <div class='llm-model-timeline-empty'>{t('暂无数据')}</div>
        ) : (
          <div class='llm-model-timeline-body'>
            {showSystem.value ? (
              <CollapseSection
                count={timeline.value.systemPrompts.length}
                defaultExpand={false}
                icon='icon-neizhi'
                sectionId={LLM_SEARCH_SECTION.inputSystem}
                title={t('系统 Prompts')}
              >
                {timeline.value.systemPrompts.map((item, index) => (
                  <TimelineMessageRow
                    key={item.id}
                    part={{
                      id: item.id,
                      role: 'system',
                      content: item.content,
                      isError: false,
                      messageIndex: index + 1,
                      searchBlockId: `input:system:${item.id}`,
                      showIndex: true,
                    }}
                    onViewAlone={content => {
                      detail.value = content;
                    }}
                  />
                ))}
              </CollapseSection>
            ) : null}
            {showTools.value ? (
              <CollapseSection
                count={timeline.value.availableTools.length}
                defaultExpand={false}
                icon='icon-Tool'
                sectionId={LLM_SEARCH_SECTION.inputTools}
                title={t('可用工具')}
              >
                {renderAvailableTools(timeline.value.availableTools)}
              </CollapseSection>
            ) : null}
            {showInput.value ? (
              <CollapseSection
                count={timeline.value.inputMessages.length}
                icon='icon-mc-ai-input'
                sectionId={LLM_SEARCH_SECTION.timelineInput}
                title={t('输入')}
              >
                {{
                  extra:
                    inputExpanded.value && filter.value === 'all' && timeline.value.inputMessages.length > 2
                      ? () => (
                          <span
                            class='llm-model-timeline-reset'
                            onClick={handleResetInput}
                          >
                            <i class='icon-monitor icon-chehui1' />
                            <span>{t('复位省略')}</span>
                          </span>
                        )
                      : null,
                  default: () => renderInput(),
                }}
              </CollapseSection>
            ) : null}
            {showOutput.value ? (
              <CollapseSection
                count={timeline.value.outputMessages.length}
                icon='icon-mc-ai-output'
                sectionId={LLM_SEARCH_SECTION.timelineOutput}
                title={t('输出')}
              >
                {renderOutput()}
              </CollapseSection>
            ) : null}
          </div>
        )}
        <DetailSlider
          detail={detail.value}
          onClose={() => {
            detail.value = null;
          }}
        />
      </div>
    );

    /** 折叠态只渲染首尾两条，中间用可点击的省略条代替 */
    function renderCollapsedInput() {
      const messages = filteredInputMessages.value;
      const first = messages[0] ? [messages[0]] : [];
      const last = messages.length > 1 ? [messages[messages.length - 1]] : [];
      return (
        <>
          {renderMessages(first)}
          <div
            class='llm-model-timeline-omit'
            onClick={handleExpandInput}
          >
            <i class='icon-monitor icon-mc-more llm-model-timeline-omit-icon' />
            <i18n-t keypath='已省略 {0} 项，可'>
              <span class='llm-model-timeline-omit-count'>{timeline.value.inputMessages.length - 2}</span>
            </i18n-t>
            <span class='llm-model-timeline-omit-action'>{t('展开')}</span>
            <i
              class='icon-monitor icon-double-down'
              style='font-size: 20px'
            />
          </div>
          {renderMessages(last)}
        </>
      );
    }

    function renderInput() {
      // 未进入分片态：条目多时只留首尾，条目少时直接全量渲染
      if (!inputNeedsPaging.value) {
        return timeline.value.inputMessages.length > 2
          ? renderCollapsedInput()
          : renderMessages(filteredInputMessages.value);
      }
      return renderPagedMessages(filteredInputMessages.value, inputRender.limit.value, inputRender.rendering.value);
    }

    function renderOutput() {
      return renderPagedMessages(filteredOutputMessages.value, outputRender.limit.value, outputRender.rendering.value);
    }

    /** 按已渲染条数切片；补齐未完成时在尾部挂一条极短的「渲染中」指示 */
    function renderPagedMessages(messages: LlmTimelineMessage[], limit: number, rendering: boolean) {
      return (
        <>
          {renderMessages(messages.slice(0, limit))}
          {rendering ? (
            <div class='llm-model-timeline-omit is-rendering'>
              <i class='icon-monitor icon-mc-more llm-model-timeline-omit-icon' />
              <span>{t('渲染中')}</span>
            </div>
          ) : null}
        </>
      );
    }
  },
});

/** 按页签筛选消息；「只留首尾」的省略由渲染层按展开态自行处理 */
function filterMessages(
  messages: LlmTimelineMessage[],
  filter: LlmTimelineFilter,
  lastInputIndex: number
): LlmTimelineMessage[] {
  if (filter === 'error') return messages.filter(item => item.isError);
  if (filter === 'last-input') return messages.filter(item => item.tab === 'input' && item.index === lastInputIndex);
  if (filter === 'output') return messages.filter(item => item.tab === 'output');
  return messages;
}

/** 命中所属消息的序号（1 起）；未命中任何消息时返回 0，供分片渲染抬高本批条数 */
function resolveHitMessageCount(messages: LlmTimelineMessage[], hit: LlmSearchHit | null | undefined): number {
  if (!hit) return 0;
  const index = messages.findIndex(message =>
    message.parts.some(part => part.id === hit.expandId || isActiveHitOnBlock(hit, part.searchBlockId))
  );
  return index < 0 ? 0 : index + 1;
}
