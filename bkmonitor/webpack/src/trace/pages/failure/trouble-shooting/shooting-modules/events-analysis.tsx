/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { Collapse } from 'bkui-vue';
import base64Svg from 'monitor-common/svg/base64';
import VueJsonPretty from 'vue-json-pretty';

import MarkdownViewer from '../../../../components/markdown-editor/viewer';
import {
  EVENTS_NEED_ALL_SUB_EVENTS,
  EVENTS_NEED_AVAILABILITY_CHECK,
  EVENTS_NEED_JUMP_PAGE,
  EVENTS_TYPE_MAP,
} from '../../constant';
import { replaceEntityInText } from '../entity-replace';
import { GENERAL_EVENT_MAX_EXPANDED_LINES, isExpandedJsonOverLineLimit } from '../json-expanded-lines';
import { createInteractionExecutor, handleCopy, TableContentItem } from './common';

import type { IEventsAnalysis, IEventsContentsData, IInteraction } from '../../types';
import type { IShootingModuleContext, TranslateFn } from './module-context';

/**
 * 事件分析模块工厂
 * @param options - 模块上下文
 * @param $t - 国际化翻译函数
 * @returns { renderSlot, eventTitle, eventChildContent }
 */
export const createEventsAnalysisModule = (options: IShootingModuleContext, $t: TranslateFn) => {
  // 统一消费后端 interaction，并补充仅用于展示的侧滑标题
  const executeInteraction = createInteractionExecutor(options);
  const executeEventInteraction = (
    interaction?: IInteraction,
    title?: string,
    availabilityRef?: IInteraction['detail_ref']
  ) => {
    const detailRef = availabilityRef;
    const eventInteraction = interaction ? { ...interaction, drawer_type: 'event' as const } : interaction;
    executeInteraction(eventInteraction, title, detailRef);
  };

  const hasInteractiveAction = (interaction?: IInteraction) => ['drawer', 'link'].includes(interaction?.action);
  const canOpenInteraction = (interaction?: IInteraction) => hasInteractiveAction(interaction);
  const executeItemInteraction = (
    type: string,
    interaction?: IInteraction,
    title?: string,
    availabilityRef?: IInteraction['detail_ref']
  ) => {
    // 仅 K8S/TMP 链接跳转前固定使用 event 类型做数据可用性校验
    if (EVENTS_NEED_AVAILABILITY_CHECK.has(type)) {
      executeEventInteraction(interaction, title, availabilityRef);
    } else {
      // 主机事件及其他事件不做可用性校验，但仍透传引用
      executeInteraction(interaction, title, availabilityRef, true);
    }
  };
  const handleItemInteractionClick = (
    event: MouseEvent,
    canInteract: boolean,
    type: string,
    interaction?: IInteraction,
    title?: string,
    availabilityRef?: IInteraction['detail_ref']
  ) => {
    if (!canInteract) return;
    event.stopPropagation();
    executeItemInteraction(type, interaction, title, availabilityRef);
  };

  /**
   * 解析事件类型父级标题可用的 interaction。
   * 优先用 labels_mapping 类型层；general / 发布变更等无类型层时，回退到首条可交互记录（通常为 drawer）。
   */
  const resolveParentInteraction = (item: IEventsAnalysis): IInteraction | undefined => {
    if (hasInteractiveAction(item.interaction)) {
      return item.interaction;
    }
    const records = (item.allContents || item.contents || []) as IEventsContentsData[];
    const record = records.find(r => hasInteractiveAction(r?.interaction));
    return record?.interaction;
  };

  // 事件分析标题
  const eventTitle = (item: IEventsAnalysis, subContent = null) => {
    // 判断是否为子级标题
    const isChild = !!subContent;
    // 根据类型获取配置，不在EVENTS_TYPE_MAP中，则默认使用general通用配置
    const config = EVENTS_TYPE_MAP[item.type as keyof typeof EVENTS_TYPE_MAP] ?? EVENTS_TYPE_MAP.general;

    const renderTitleInfo = () => {
      // 父级Collapse title：类型层 interaction；general 等可回退到首条记录
      if (!isChild) {
        const keypath = item.total > 3 ? config.keypath : config.keypath2;
        const isAllEventsType = EVENTS_NEED_ALL_SUB_EVENTS.has(item.type);
        const canOpenAllEvents = isAllEventsType && item.total > 3;
        // ITSM / 应急 / 腾讯云走全部子事件侧滑，不消费 interaction
        const parentInteraction = isAllEventsType ? undefined : resolveParentInteraction(item);
        const hasInteraction = !!parentInteraction;
        return (
          <>
            <span
              style={{ fontWeight: '700' }}
              class='mr-2'
            >
              {item.title || $t('通用事件')}
            </span>
            <span style={{ fontWeight: 'normal' }}>
              <i18n-t keypath={keypath}>
                {/* 有单位的类型始终渲染单位槽，避免 unit 为空时 Top 滑进 {1} */}
                <span
                  style={{ fontWeight: '700' }}
                  class={canOpenAllEvents || hasInteraction ? 'cursor-link' : ''}
                  onClick={(e: MouseEvent) => {
                    const canOpenParent = isAllEventsType ? canOpenAllEvents : hasInteraction;
                    if (!canOpenParent) return;
                    e.stopPropagation();
                    // ITSM、应急、腾讯云事件继续使用已有的全部子事件侧滑
                    if (isAllEventsType) {
                      options.onViewAllEvents?.(item);
                      return;
                    }
                    executeItemInteraction(
                      item.type || '',
                      parentInteraction,
                      item.title || $t('事件详情'),
                      item.availability_ref
                    );
                  }}
                >
                  {item.total}
                </span>
                {item.unit && <span>{item.unit}</span>}
                {item.total > 3 && <span style={{ fontWeight: '700' }}>Top{item.top}</span>}
              </i18n-t>
            </span>
          </>
        );
      }
      // 子项Collapse——tmp事件title
      if (item.type === 'tmp_events') {
        const canInteract = canOpenInteraction(subContent.interaction);
        const interactionTitle = String(subContent.event_name || $t('事件详情'));
        return (
          <span
            style={{ fontWeight: '600' }}
            class={canInteract ? 'cursor-link' : ''}
            onClick={e =>
              handleItemInteractionClick(
                e,
                canInteract,
                item.type || '',
                subContent.interaction,
                interactionTitle,
                subContent.availability_ref
              )
            }
          >
            {subContent.event_name}
          </span>
        );
      }
      // 子项Collapse——k8s、host事件title
      if (['k8s_warning_events', 'alert_system_events'].includes(item.type)) {
        const canInteract = canOpenInteraction(subContent.interaction);
        const interactionTitle = String(subContent.event_name || $t('事件详情'));
        return (
          <>
            <span
              style={{ fontWeight: '600' }}
              class={['mr-2', { 'cursor-link': canInteract }]}
              onClick={e =>
                handleItemInteractionClick(
                  e,
                  canInteract,
                  item.type || '',
                  subContent.interaction,
                  interactionTitle,
                  subContent.availability_ref
                )
              }
            >
              {subContent.event_name}
            </span>
            <span style={{ fontWeight: 'normal' }}>
              <i18n-t keypath={'（共 {0} 个{1}）'}>
                <span
                  style={{ fontWeight: '700' }}
                  class={canInteract ? 'cursor-link' : ''}
                  onClick={e =>
                    handleItemInteractionClick(
                      e,
                      canInteract,
                      item.type || '',
                      subContent.interaction,
                      interactionTitle,
                      subContent.availability_ref
                    )
                  }
                >
                  {subContent._sub_count}
                </span>
                <span>{subContent._sub_unit}</span>
              </i18n-t>
            </span>
          </>
        );
      }
      // 子项Collapse——通用事件title
      if (item.isGeneral) {
        return (
          <span class='sub-event-title-general'>
            <span style={{ fontWeight: '600' }}>{`${$t('示例事件')} ${subContent.$index + 1}`}</span>
            <i
              class='icon-monitor icon-mc-copy cursor-link'
              v-bk-tooltips={{ content: $t('复制') }}
              onClick={e => {
                e.stopPropagation();
                handleCopy(subContent, $t, true);
              }}
            />
          </span>
        );
      }
      // 默认子项标题
      return (
        <span style={{ fontWeight: '600' }}>
          {`${item.total > 3 ? $t('示例事件') : $t('事件')} ${subContent.$index + 1}`}
        </span>
      );
    };

    return (
      <span class='event-title'>
        {/* 渲染标题icon（仅父级显示）*/}
        {!isChild &&
          (config.iconType ? (
            <span
              style={{ backgroundImage: `url(${base64Svg[config.iconType]})` }}
              class='event-icon'
            />
          ) : (
            <span class='general-icon-wrapper event-icon'>
              <i class='icon-monitor icon-shijianjiansuo general-icon' />
            </span>
          ))}
        {/* 渲染标题内容 */}
        {renderTitleInfo()}
      </span>
    );
  };
  // 事件分析内容
  const eventContent = (item: IEventsAnalysis) => {
    // 确保当前项的展开状态已初始化
    if (options.activeIndex.eventChild[item.$index] === undefined) {
      options.activeIndex.eventChild[item.$index] = item.contents?.map((_, i) => i) || [];
    }

    return (
      <Collapse
        class='event-collapse inner-collapse'
        v-model={options.activeIndex.eventChild[item.$index]}
        v-slots={{
          default: subContent => eventTitle(item, subContent),
          content: subContent => eventChildContent(item, subContent),
        }}
        header-icon='right-shape'
        list={item.contents || []}
      />
    );
  };
  // 事件分析子Collapse内容
  const eventChildContent = (item: IEventsAnalysis, subContent: IEventsContentsData) => {
    // 通用事件渲染 JSON 预览
    if (item.isGeneral) {
      const rawData = subContent || {};
      const jsonData: Record<string, any> = rawData && typeof rawData === 'object' ? { ...rawData } : rawData;
      if (jsonData) {
        delete jsonData.$index;
        // interaction 是前端行为元数据，不属于事件原始内容
        delete jsonData.interaction;
      }
      const hasOnViewFullJson = typeof options.onViewFullJson === 'function';

      // 按完全展开后的行数判断是否截断；超过上限即可提前结束递归
      const isTruncated = isExpandedJsonOverLineLimit(jsonData, GENERAL_EVENT_MAX_EXPANDED_LINES);

      // 预览仍只取前 N 个顶层 key，减少 DOM 节点
      const limitedData = (() => {
        if (typeof jsonData !== 'object' || jsonData === null) {
          return jsonData;
        }
        const entries = Object.entries(jsonData).slice(0, GENERAL_EVENT_MAX_EXPANDED_LINES);
        // 当需要显示"查看完整"时，添加一个特殊key作为下一行
        if (isTruncated && hasOnViewFullJson) {
          entries.push(['__viewMore__', '__VIEW_MORE_PLACEHOLDER__']);
        }
        return Object.fromEntries(entries);
      })();

      return (
        <div class='general-event-content'>
          <VueJsonPretty
            renderNodeKey={({ node, defaultKey }) => {
              // 伪造的"查看完整"行
              if (node.key === '__viewMore__') {
                return (
                  <span
                    class='view-full-action cursor-link'
                    onClick={(e: MouseEvent) => {
                      e.stopPropagation();
                      options.onViewFullJson?.(jsonData, Number(subContent.$index));
                    }}
                  >
                    ... {$t('查看完整')}
                  </span>
                );
              }
              return defaultKey;
            }}
            renderNodeValue={({ node, defaultValue }) => {
              // 伪造的"查看完整"行，隐藏value部分
              if (node.key === '__viewMore__') {
                return null;
              }
              return defaultValue; // 使用默认渲染
            }}
            collapsedOnClickBrackets={false}
            data={limitedData}
            deep={1}
            showIcon={true}
            showKeyValueSpace={true}
            showLine={false}
          />
        </div>
      );
    }
    // 否则渲染表格
    return (
      <span class='table-content'>
        {Object.entries(item.fields).map(([key, value]) => {
          // tmp告警事件需要特殊处理，event_name已经作为子标题展示
          if (
            (item.type === 'tmp_events' && key === 'event_name') ||
            (['k8s_warning_events', 'alert_system_events'].includes(item.type) &&
              ['event_name', '_sub_unit', '_sub_count'].includes(key))
          ) {
            return null;
          }
          return (
            <TableContentItem
              key={key}
              label={value}
              needJumpIcon={EVENTS_NEED_JUMP_PAGE.has(item.type) && key === 'event_name'}
              needTitle={false}
              showLabel={item.type !== 'tencent_cloud_notice_events'} // 特殊类型不显示label
              value={subContent[key]}
            />
          );
        })}
      </span>
    );
  };
  /**
   * 事件分析模块
   * @returns {JSX.Element} 配置内容元素
   */
  const renderSlot = () => {
    const len = options.eventsData?.length || 0;
    return (
      <>
        {/* 事件分析总结区域 */}
        <div class='card-summary'>
          <div class='card-summary-title'>{$t('事件分析总结：')}</div>
          <MarkdownViewer
            class='markdown-viewer-has-link'
            value={replaceEntityInText(options.summaryList.events_analysis, options.extractedInfoList?.events_analysis)}
          />
        </div>
        {/* 事件分析详情折叠面板 */}
        {len > 0 && (
          <Collapse
            class='event-collapse'
            v-model={options.activeIndex.event}
            v-slots={{
              default: item => eventTitle(item),
              content: item => eventContent(item),
            }}
            header-icon='right-shape'
            list={options.eventsData}
          />
        )}
      </>
    );
  };

  return {
    renderSlot,
    eventTitle,
    eventChildContent,
  };
};
