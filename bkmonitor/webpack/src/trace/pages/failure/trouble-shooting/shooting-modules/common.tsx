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
import { Message, Popover } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';

import { handleEndTime } from '../../failure-topo/utils';
import { type IOpenDrawerContext, handleInteraction } from '../interaction-handler';

import type { IInteraction, ITraceAnalysis, OverflowPopType } from '../../types';
import type { IShootingModuleContext, TranslateFn } from './module-context';

/**
 * 公共组件 - 表格内容项。用于统一渲染标签-值对的数据展示项
 * @param label 标签文本
 * @param needTitle 是否需要在值元素上添加title属性（用于悬停显示完整内容）
 * @param showLabel 是否显示标签部分
 * @param value 要显示的值
 */
export const TableContentItem = (props: {
  label: string;
  needJumpIcon?: boolean;
  needTitle: boolean;
  showLabel: boolean;
  value: any;
}) => (
  <span class='table-content-item'>
    {props.showLabel && (
      <span
        class='item-label'
        v-overflow-tips={{
          content: props.label,
          placement: 'top',
        }}
      >
        {props.label}
      </span>
    )}
    <span
      class='item-value'
      title={props.needTitle ? String(props.value) : null}
    >
      {props.value}
      {props.needJumpIcon && <i class='icon-monitor icon-fenxiang icon-jump-page' />}
    </span>
  </span>
);

/**
 * JSON数据格式化展示组件
 * 递归渲染JSON对象，以美观的树形结构展示
 * @param log - 要展示的JSON数据
 * @param isChild - 是否为子级（用于控制缩进）
 * @param isArray - 当前数据是否为数组类型
 * @returns JSX.Element
 */
export const renderLogJSONTips = (log: any, isChild = false, isArray = false) => {
  // 处理空值情况
  if (!log) return 'null';
  return (
    <>
      {/* 根据数据类型显示不同的括号 */}
      <span style='color: #9D694C;'>{`${isArray ? '[' : '{'}`}</span>
      {/* 遍历对象的所有属性 */}
      {Object.entries(log).map(([key, value]) => (
        <div
          key={key}
          style={{ marginLeft: isChild ? '8px' : '28px' }}
          class='overflow-popover-content_item'
        >
          {/* 属性名 */}
          <span class='item-label'>"{key}":</span>
          {/* 属性值，根据数据类型采用不同的显示方式 */}
          <span class='item-value'>
            {typeof value === 'number'
              ? value
              : typeof value === 'object'
                ? renderLogJSONTips(value, true, Array.isArray(value)) // 对象类型递归渲染
                : `"${value}"`}
          </span>
        </div>
      ))}
      {/* 闭合括号 */}
      <span style='color: #9D694C;'>{`${isArray ? ']' : '}'}`}</span>
    </>
  );
};

/**
 * 生成跳转URL
 * 根据字段配置和当前数据项生成完整的跳转链接
 * @param key - 字段标识符
 * @param value - 字段配置信息
 * @param item - 当前数据项
 * @param options - 全局配置选项
 * @returns string 完整的跳转URL
 */
export const generateUrl = (
  key: string,
  value: Record<string, any>,
  item: ITraceAnalysis,
  options: Pick<IShootingModuleContext, 'bkzIds' | 'incidentDetailData'>
) => {
  if (!value.query) return '';

  // 获取基础查询参数
  const query = value.query(item);
  const { begin_time, end_time } = options.incidentDetailData;
  const realEndTime = handleEndTime(begin_time, end_time);

  // 根据字段类型添加不同的时间参数
  if (['service_name', 'app_name'].includes(key)) {
    query.from = (begin_time * 1000).toString();
    query.to = (realEndTime * 1000).toString();
  } else {
    query.start_time = (begin_time * 1000).toString();
    query.end_time = (realEndTime * 1000).toString();
  }

  // 构建查询字符串
  const queryString = new URLSearchParams(query).toString();
  const { origin, pathname } = window.location;
  const baseUrl = options.bkzIds[0] ? `${origin}${pathname}?bizId=${options.bkzIds[0]}` : '';

  return `${baseUrl}#${value.url}?${queryString}`;
};

/** 拷贝操作。复制失败只提示错误，不再接着提示成功 */
export function handleCopy(data, $t, isGeneralEvent = false) {
  const reportCopyError = msg => {
    Message({
      message: msg,
      theme: 'error',
    });
  };
  let copied = false;
  if (isGeneralEvent) {
    const { $index, interaction, ...rest } = data;
    copied = copyText(JSON.stringify(rest, null, 4), reportCopyError);
  } else {
    copied = copyText(data, reportCopyError);
  }
  if (!copied) return;

  Message({
    message: $t('复制成功'),
    theme: 'success',
  });
}

/**
 * 创建 interaction 执行器
 * 统一消费后端 interaction，并补充仅用于展示的侧滑标题
 * @param options - 含 interaction 回调和弹窗清理回调的上下文
 * @returns 执行函数 (interaction, title?, availabilityRef?, skipAvailabilityCheck?) => void
 */
export const createInteractionExecutor = (
  options: Pick<IShootingModuleContext, 'checkInteractionAvailability' | 'closeAnalysisPopovers' | 'onOpenDrawer'>
) => {
  const executeInteraction = (
    interaction?: IInteraction,
    title?: string,
    availabilityRef?: IInteraction['detail_ref'],
    skipAvailabilityCheck = false
  ) => {
    options.closeAnalysisPopovers?.();
    void handleInteraction(
      interaction,
      (context: IOpenDrawerContext) => {
        options.onOpenDrawer?.({ ...context, title });
      },
      options.checkInteractionAvailability,
      availabilityRef,
      skipAvailabilityCheck
    );
  };
  return executeInteraction;
};

/**
 * 创建通用的溢出 Popover 渲染器
 * 用于统一处理各种类型的文本溢出提示框（多行溢出检测：scrollHeight > clientHeight）
 * @param options - 含 popoverState / handlePopoverClose 的上下文
 * @param $t - 国际化翻译函数
 * @returns renderCommonPopover / contentPopoverBlock 两个渲染函数
 */
export const createPopoverRenderers = (
  options: Pick<IShootingModuleContext, 'handlePopoverClose' | 'popoverState'>,
  $t: TranslateFn
) => {
  /**
   * 通用的Popover渲染函数
   * 用于统一处理各种类型的文本溢出提示框（多行溢出检测：scrollHeight > clientHeight）
   * @param content - 要显示的内容
   * @param index - 当前项的索引（用于控制显示状态）
   * @param popoverType - Popover类型标识
   * @param options.config - 可选配置项
   * @param options.config.renderContent - 自定义弹窗内容渲染函数
   * @param options.config.renderDefault - 自定义触发元素渲染函数，接收 onMouseenter 回调用于溢出检测
   * @param options.config.contentCls - 弹窗内容区自定义 class（用于样式隔离）
   */
  const renderCommonPopover = (
    content: string,
    index: number,
    popoverType: OverflowPopType,
    {
      contentCls = 'overflow-popover-content__text',
      renderContent,
      renderDefault,
    }: {
      contentCls?: string;
      renderContent?: (content: string) => JSX.Element;
      renderDefault?: (onMouseenter: (e: MouseEvent) => void) => JSX.Element;
    } = {}
  ) => {
    const popoverKey = `${popoverType}_${index}`;
    const isVisible =
      options.popoverState.currentPopover?.type === popoverType && options.popoverState.currentPopover?.index === index;

    // 统一的鼠标进入处理：多行溢出检测 + 设置当前 Popover
    const handleMouseEnter = (e: MouseEvent) => {
      const el = e.currentTarget as HTMLElement;
      const overflow = el.scrollHeight > el.clientHeight;
      options.popoverState.overflowMap[popoverKey] = overflow;
      if (overflow) {
        options.popoverState.currentPopover = { type: popoverType, index };
      }
    };

    // disabled 逻辑：无内容时禁用（溢出控制由 isShow 通过 handleMouseEnter 间接实现）
    const disabled = !content;

    return (
      <Popover
        key={`${index}-${popoverType}`}
        width={560}
        extCls='overflow-popover'
        disabled={disabled}
        isShow={isVisible}
        placement='right-start'
        popoverDelay={[500, 0]}
        theme='light'
        trigger='manual'
        onClickoutside={options.handlePopoverClose}
      >
        {{
          content: () => (
            <div class='overflow-popover-content'>
              <i
                class='icon-monitor icon-mc-copy copy-icon'
                onClick={() => handleCopy(content, $t)}
              />
              <div class={contentCls}>{renderContent ? renderContent(content) : content}</div>
            </div>
          ),
          default: () =>
            renderDefault ? (
              renderDefault(handleMouseEnter)
            ) : (
              <div
                class={`overflow-popover-trigger overflow-popover-trigger--${popoverType}`}
                data-index={index}
                onMouseenter={handleMouseEnter}
              >
                {content}
              </div>
            ),
        }}
      </Popover>
    );
  };

  /**
   * Popover内容块渲染函数
   * 封装了标题+内容的完整Popover块
   * @param title - 内容块标题
   * @param content - 主要内容
   * @param index - 索引值
   * @param popoverType - Popover类型
   * @param contentType - 内容类型（json/text）
   * @returns 完整的Popover内容块JSX
   */
  const contentPopoverBlock = (
    title: string,
    content: string,
    index: number,
    popoverType: OverflowPopType,
    contentType: 'json' | 'text' = 'text'
  ) => {
    // 内容渲染函数，根据类型选择不同的渲染方式
    const renderContent = (c: string) => {
      if (contentType === 'json') {
        try {
          const jsonData = JSON.parse(c);
          return <div class='overflow-popover-content_json'>{renderLogJSONTips(jsonData)}</div>;
        } catch {
          return <div class='overflow-popover-content_json'>{c}</div>;
        }
      }
      return <div class='overflow-popover-pattern'>{c}</div>;
    };

    return (
      <div class='log-content'>
        <div class='log-content-title'>
          <span>{title}</span>
        </div>
        {renderCommonPopover(content, index, popoverType, { renderContent })}
      </div>
    );
  };

  return {
    renderCommonPopover,
    contentPopoverBlock,
  };
};
