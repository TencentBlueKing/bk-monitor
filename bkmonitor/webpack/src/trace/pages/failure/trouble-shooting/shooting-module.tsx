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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
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
import { Collapse, Message, Popover } from 'bkui-vue';
import base64Svg from 'monitor-common/svg/base64';
import { copyText } from 'monitor-common/utils/utils';

import MarkdownViewer from '../../../components/markdown-editor/viewer';
import { EVENTS_TYPE_MAP } from '../constant';
import { handleEndTime } from '../failure-topo/utils';
import { TRACE_FIELD_CONFIG } from '../utils';

import type {
  IAlertData,
  IAnomalyAnalysis,
  IContentList,
  IEventsAnalysis,
  IEventsContentsData,
  ILogAnalysis,
  IStrategyMapItem,
  ISummaryList,
  ITraceAnalysis,
  OverflowPopType,
} from '../types';

/**
 * 公共组件 - 表格内容项。用于统一渲染标签-值对的数据展示项
 * @param label 标签文本
 * @param needTitle 是否需要在值元素上添加title属性（用于悬停显示完整内容）
 * @param showLabel 是否显示标签部分
 * @param value 要显示的值
 */
const TableContentItem = (props: { label: string; needTitle: boolean; showLabel: boolean; value: any }) => (
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
const renderLogJSONTips = (log: any, isChild = false, isArray = false) => {
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
          class='log-popover-content_item'
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
const generateUrl = (key: string, value: Record<string, any>, item: ITraceAnalysis, options: any) => {
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

/**
 * 创建故障诊断展示模块
 * 主工厂函数，负责创建各个诊断模块的渲染逻辑
 * @param options - 配置选项对象
 * @param options.activeIndex - 各折叠面板的激活状态索引
 * @param options.bkzIds - 业务ID列表
 * @param options.contentList - 内容数据列表
 * @param options.eventsData - 事件分析数据
 * @param options.goAlertList - 跳转到告警列表的回调函数
 * @param options.goDetail - 跳转到策略详情的回调函数
 * @param options.handleMouseEnter - 鼠标悬停事件处理函数
 * @param options.handlePopoverClose - Popover关闭事件处理函数
 * @param options.incidentDetailData - 故障详情数据
 * @param options.popoverState - Popover状态管理对象
 * @param options.summaryList - 各模块的总结内容
 * @param $t - 国际化翻译函数
 * @returns 包含各模块渲染函数的对象
 */
export function createShootingModule(
  options: {
    activeIndex: Record<string, number[] | Record<string, number[]>>;
    bkzIds: string[];
    contentList: IContentList;
    eventsData: IEventsAnalysis[];
    goAlertList: (list: IAlertData[]) => void;
    goDetail: (data: IStrategyMapItem) => void;
    handleMouseEnter: (e: MouseEvent, index: number, type: OverflowPopType) => void;
    handlePopoverClose: (item: { isShow: boolean }) => void;
    incidentDetailData: Record<string, any>;
    popoverState: {
      currentPopover: null | { index: number; type: OverflowPopType };
      overflowMap: Record<string, boolean>;
    };
    summaryList: ISummaryList;
  },
  $t: (key: string) => string
) {
  /**
   * 通用的Popover渲染函数
   * 用于统一处理各种类型的文本溢出提示框
   * @param content - 要显示的内容
   * @param index - 当前项的索引（用于控制显示状态）
   * @param popoverType - Popover类型标识
   * @param renderContent - 自定义内容渲染函数
   * @returns Popover组件的JSX
   */
  const renderCommonPopover = (
    content: string,
    index: number,
    popoverType: OverflowPopType,
    renderContent?: (content: string) => JSX.Element
  ) => {
    // 判断当前Popover是否应该显示
    const isVisible =
      options.popoverState.currentPopover?.type === popoverType && options.popoverState.currentPopover?.index === index;

    return (
      <Popover
        key={`${index}-${popoverType}`}
        width={560}
        extCls='log-content-tips_popover'
        disabled={!content}
        isShow={isVisible}
        placement='right-start'
        popoverDelay={[500, 0]}
        theme='light'
        trigger='manual'
        onClickoutside={options.handlePopoverClose}
      >
        {{
          content: () => (
            <div class='log-popover-content'>
              {/* 复制按钮 */}
              <i
                class={['icon-monitor', 'copy-icon', 'icon-mc-copy']}
                onClick={() => handleCopy(content, $t)}
              />
              <div class='log-popover-content__text'>{renderContent ? renderContent(content) : content}</div>
            </div>
          ),
          default: () => (
            <span
              class={`log-tips__default log-tips__${popoverType}`}
              data-index={index}
              onMouseenter={e => options.handleMouseEnter(e, index, popoverType)}
            >
              {content}
            </span>
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
    const renderContent = (content: string) => {
      if (contentType === 'json') {
        try {
          // 尝试解析JSON并格式化显示
          const jsonData = JSON.parse(content);
          return <div class='log-popover-content_json'>{renderLogJSONTips(jsonData)}</div>;
        } catch {
          // 解析失败时回退到普通文本显示
          return <div class='log-popover-content_json'>{content}</div>;
        }
      }
      return <div class='log-pattern'>{content}</div>;
    };

    return (
      <div class='log-content'>
        <div class='log-content-title'>
          <span>{title}</span>
        </div>
        {renderCommonPopover(content, index, popoverType, renderContent)}
      </div>
    );
  };

  /**
   * 处置建议模块
   * @returns {JSX.Element} 配置内容元素
   */
  const renderDisposalSlot = () => {
    return <MarkdownViewer value={options.contentList?.suggestion} />;
  };

  // 告警异常维度分析标题
  const dimensionalTitle = (item: IAnomalyAnalysis) => (
    <span class='dimensional-title'>
      {/* 显示维度名称或默认标题 */}
      {item.name || `${$t('异常维度（组合）')} ${item.$index + 1}`}
      {/* 国际化显示的异常程度 */}
      <i18n-t
        class='red-font'
        keypath='异常程度 {0}'
        tag='span'
      >
        <span style='font-weight: 700;'> {((item?.score || 0) * 100).toFixed(2)}% </span>
      </i18n-t>
    </span>
  );
  // 告警异常维度分析内容
  const dimensionalContent = (item: IAnomalyAnalysis) => {
    return (
      <span class='table-content'>
        {Object.keys(item.dimension_values || {}).map(key => (
          <TableContentItem
            key={key}
            label={key}
            needTitle={true}
            showLabel={true}
            value={(item.dimension_values[key] || []).join('、')}
          />
        ))}

        {/* 告警信息展示区域 */}
        {item.alerts.length > 0 && (
          <div class='dimensional-footer'>
            <i18n-t
              class='dimensional-footer-item'
              keypath='包含 {0} 个告警，来源于以下 {1} 个策略：'
              tag='span'
            >
              <b
                class='blue-txt'
                onClick={() => options.goAlertList(item.alerts)}
              >
                {item.alert_count}
              </b>
              <span style='font-weight: 700;'> {[Object.values(item.strategy_alerts_mapping || {}).length]} </span>
            </i18n-t>

            {/* 策略列表 */}
            {Object.values(item.strategy_alerts_mapping || {}).map((ele: IStrategyMapItem) => (
              <span
                key={ele.strategy_id}
                class='dimensional-footer-item'
                onClick={() => options.goDetail(ele)}
              >
                <span class='blue-txt'>
                  {ele.strategy_name} - {ele.strategy_id}
                </span>
              </span>
            ))}
          </div>
        )}
      </span>
    );
  };
  /**
   * 告警异常维度分析模块
   * @returns {JSX.Element} 配置内容元素
   */
  const renderDimensionalSlot = () => {
    const len = options.contentList?.alerts_analysis?.length;
    return (
      <div>
        <div class='mb-8'>{$t('故障关联的告警，统计出最异常的维度（组合）：')}</div>
        {len > 0 && (
          <Collapse
            class='dimensional-collapse inner-collapse'
            v-model={options.activeIndex.dimensional}
            v-slots={{
              default: item => dimensionalTitle(item),
              content: item => dimensionalContent(item),
            }}
            header-icon='right-shape'
            list={options.contentList?.alerts_analysis || []}
            accordion
          />
        )}
      </div>
    );
  };

  // 事件分析标题
  const eventTitle = (item: IEventsAnalysis, subContent = null) => {
    // 判断是否为子级标题
    const isChild = !!subContent;
    const config = EVENTS_TYPE_MAP[item.type as keyof typeof EVENTS_TYPE_MAP];

    const renderTitleInfo = () => {
      // 父级Collapse title
      if (!isChild) {
        const keypath = item.total > 3 ? config.keypath : config.keypath2;
        return (
          <>
            <span
              style={{ fontWeight: '700' }}
              class='mr-2'
            >
              {item.title}
            </span>
            <span style={{ fontWeight: 'normal' }}>
              <i18n-t keypath={keypath}>
                <span style={{ fontWeight: '700' }}>{item.total}</span>
                <span>{item.unit}</span>
                {item.total > 3 && <span style={{ fontWeight: '700' }}>Top{item.top}</span>}
              </i18n-t>
            </span>
          </>
        );
      }
      // 子项Collapse根据类型返回title
      if (item.type === 'tmp_events') {
        return <span style={{ fontWeight: '600' }}>{subContent.event_name}</span>;
      }
      if (['k8s_warning_events', 'alert_system_events'].includes(item.type)) {
        return (
          <>
            <span
              style={{ fontWeight: '600' }}
              class='mr-2'
            >
              {subContent.event_name}
            </span>
            <span style={{ fontWeight: 'normal' }}>
              <i18n-t keypath={'（共 {0} 个{1}）'}>
                <span style={{ fontWeight: '700' }}>{subContent._sub_count}</span>
                <span>{subContent._sub_unit}</span>
              </i18n-t>
            </span>
          </>
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
        {!isChild && (
          <span
            style={{ backgroundImage: `url(${base64Svg[config.iconType]})` }}
            class='event-icon'
          />
        )}
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
        accordion
      />
    );
  };
  // 事件分析子Collapse内容
  const eventChildContent = (item: IEventsAnalysis, subContent: IEventsContentsData) => (
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
            needTitle={false}
            showLabel={item.type !== 'tencent_cloud_notice_events'} // 特殊类型不显示label
            value={subContent[key]}
          />
        );
      })}
    </span>
  );
  /**
   * 事件分析模块
   * @returns {JSX.Element} 配置内容元素
   */
  const renderEventsSlot = () => {
    const len = options.eventsData?.length || 0;
    return (
      <>
        {/* 事件分析总结区域 */}
        <div class='card-summary'>
          <div class='card-summary-title'>{$t('事件分析总结：')}</div>
          <MarkdownViewer value={options.summaryList.events_analysis} />
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

  // 日志分析标题
  const logTitle = (item: ILogAnalysis, itemIndex: number) => (
    <span class='log-title'>
      {`聚类结果 ${itemIndex + 1}`}
      <i18n-t
        class='log-title-count'
        keypath='（共 {0} 条日志）'
        tag='span'
      >
        <span style='font-weight: 700;margin: 0 2px;'> {item.log_count} </span>
      </i18n-t>
    </span>
  );
  // 日志分析内容
  const logContent = (item: ILogAnalysis, index: number) => {
    return (
      <div class='log-content-warpper'>
        {/* Pattern展示 */}
        {contentPopoverBlock('Pattern：', item.pattern, index, 'log_pattern', 'text')}
        {/* 示例日志展示（JSON格式） */}
        {contentPopoverBlock($t('示例日志：'), item.demo_log, index, 'demo_log', 'json')}
      </div>
    );
  };
  /**
   * 日志分析模块
   * @returns {JSX.Element} 配置内容元素
   */
  const renderLogsSlot = () => {
    const len = options.contentList.logs_analysis ? Object.keys(options.contentList.logs_analysis).length : 0;
    return (
      <>
        {/* 日志分析总结区域 */}
        <div class='card-summary'>
          <div class='card-summary-title'>{$t('日志分析总结：')}</div>
          <MarkdownViewer value={options.summaryList.logs_analysis} />
        </div>
        {/* 日志分析详情折叠面板 */}
        {len > 0 && (
          <Collapse
            class='log-collapse inner-collapse'
            v-model={options.activeIndex.log}
            v-slots={{
              default: (item, index) => logTitle(item, index),
              content: (item, index) => logContent(item, index),
            }}
            header-icon='right-shape'
            list={Object.values(options.contentList?.logs_analysis)[0] || []}
            accordion
          />
        )}
      </>
    );
  };

  // Trace分析标题
  const traceTitle = (item: ITraceAnalysis, itemIndex: number) => (
    <span class='log-title'>
      {`${$t('分析结果')} ${itemIndex + 1}`}
      <i18n-t
        class='log-title-count'
        keypath='（共 {0} 条异常信息）'
        tag='span'
      >
        <span style='font-weight: 700;margin: 0 2px;'> {item.log_count} </span>
      </i18n-t>
    </span>
  );

  // Trace分析子Collapse内容
  const traceChildContent = (item: ITraceAnalysis) => {
    // 字段点击跳转处理函数
    const handleFieldClick = (key: string, value: Record<string, any>) => {
      const url = generateUrl(key, value, item, options);
      if (url) {
        window.open(url, '_blank');
      }
    };
    return (
      <span class='table-content'>
        {Object.entries(TRACE_FIELD_CONFIG).map(([key, value]) => {
          return (
            <span
              key={key}
              class='table-content-item'
            >
              <span class='item-label'>{value.label}</span>
              <span
                class={['item-value', { 'item-value-link': value.url }]}
                onClick={value.url ? () => handleFieldClick(key, value) : undefined}
              >
                {item[key]}
              </span>
            </span>
          );
        })}
      </span>
    );
  };
  // Trace分析内容
  const traceContent = (item: ITraceAnalysis, index: number) => {
    return (
      <div class='log-content-warpper'>
        {/* Pattern展示 */}
        {contentPopoverBlock('Pattern：', item.pattern, index, 'trace_pattern', 'text')}

        <div class='log-content'>
          <div class='log-content-title'>
            <span>{$t('示例 span：')}</span>
          </div>
          {/* Trace详情表格 */}
          {traceChildContent(item)}
        </div>
      </div>
    );
  };
  /**
   * Trace分析模块
   * @returns {JSX.Element} 配置内容元素
   */
  const renderTraceSlot = () => {
    const len = options.contentList.trace_analysis?.length || 0;
    return (
      <>
        {/* Trace分析总结区域 */}
        <div class='card-summary'>
          <div class='card-summary-title'>{$t('Trace 分析总结：')}</div>
          <MarkdownViewer value={options.summaryList.trace_analysis} />
        </div>
        {/* Trace分析详情折叠面板 */}
        {len > 0 && (
          <Collapse
            class='trace-collapse log-collapse inner-collapse'
            v-model={options.activeIndex.trace}
            v-slots={{
              default: (item, index) => traceTitle(item, index),
              content: (item, index) => traceContent(item, index),
            }}
            header-icon='right-shape'
            list={options.contentList?.trace_analysis || []}
            accordion
          />
        )}
      </>
    );
  };

  /**
   * 渲染故障诊断各模块内容
   * alerts_analysis: 告警异常维度分析模块
   * events_analysis: 事件分析模块
   * logs_analysis: 日志分析模块
   * trace_analysis: Trace分析模块
   * @returns {JSX.Element}
   */
  const slots: Record<string, () => JSX.Element | null> = {
    suggestion: () => renderDisposalSlot(),
    alerts_analysis: () => renderDimensionalSlot(),
    events_analysis: () => renderEventsSlot(),
    logs_analysis: () => renderLogsSlot(),
    trace_analysis: () => renderTraceSlot(),
  };

  return {
    slots,
  };
}

/** 拷贝操作 */
function handleCopy(text: string, $t) {
  copyText(text);
  Message({
    theme: 'success',
    message: $t('复制成功'),
  });
}
