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

import { type PropType, computed, defineComponent, shallowRef, useTemplateRef, watch } from 'vue';

import { Button, Exception, Progress } from 'bkui-vue';
import dayjs from 'dayjs';
import base64Svg from 'monitor-common/svg/base64';
import { useI18n } from 'vue-i18n';

import { getAlertEventTagDetails } from '../../../../services/alarm-detail';
import {
  type AlertScatterClickEvent,
  type IEventListItem,
  type IEventTopkItem,
  type IPosition,
  EventTab,
} from '../../../../typings';

import type { ICustomEventDetail } from 'monitor-ui/chart-plugins/plugins/caller-line-chart/use-custom';

import './alarm-chart-event-detail.scss';

// 常量定义
/** 标签颜色配置 */
const TAB_COLORS = {
  [EventTab.Warning]: '#F59500',
  [EventTab.All]: '#3A84FF',
} as const;

/** 默认SVG图标 */
const DEFAULT_SVG = 'bcs';

export default defineComponent({
  name: 'AlarmChartEventDetail',
  props: {
    position: {
      type: Object as PropType<IPosition>,
      required: true,
    },
    eventItem: {
      type: Object as PropType<Partial<AlertScatterClickEvent>>,
      required: true,
    },
  },
  setup(props) {
    const { t } = useI18n();

    /** 组件DOM引用，用于获取实际高度 */
    const eventDetailRef = useTemplateRef<HTMLDivElement>('eventDetailRef');

    /** 异常事件数据 */
    const warningData = shallowRef<ICustomEventDetail>({});
    /** 全部事件数据 */
    const allData = shallowRef<ICustomEventDetail>({});
    /** 当前激活的标签页 */
    const activeTab = shallowRef<EventTab>(EventTab.Warning);
    /** 加载状态 */
    const loading = shallowRef(false);

    /** 当前菜单数据，根据激活标签页动态计算 */
    const menuData = computed<ICustomEventDetail>(() => {
      return activeTab.value === EventTab.Warning ? warningData.value : allData.value;
    });

    /**
     * @description 获取组件实际高度
     * @returns {number} 组件高度，默认返回200
     */
    const getComponentHeight = (): number => {
      if (eventDetailRef.value) {
        return eventDetailRef.value.offsetHeight || 200;
      }
      return 200;
    };

    /**
     * @description 生成基础URL
     * @param {string} hash - URL的hash部分
     * @param {number} [bizId] - 业务ID，可选
     * @returns {string} 生成的URL
     */
    const generateBaseUrl = (hash: string, bizId?: number): string => {
      if (process.env.NODE_ENV === 'development') {
        return `${process.env.proxyUrl}?bizId=${bizId || window.cc_biz_id}${hash}`;
      }
      return location.href.replace(location.hash, hash);
    };

    /**
     * @description 创建查询配置
     * @param {string} [eventName] - 事件名称，可选
     * @param {Record<string, any>[]} [defaultWhere=[]] - 默认查询条件
     * @param {boolean} [isApm=false] - 是否为APM配置
     * @returns {object} 查询配置对象
     */
    const createQueryConfig = (eventName?: string, defaultWhere: Record<string, any>[] = [], isApm = false) => {
      const eventTarget = props.eventItem?.query_config;
      const queryConfig = eventTarget?.query_configs?.[0];

      // 构建 where 条件
      const where: Record<string, any>[] = [...defaultWhere, ...(isApm ? [] : (queryConfig?.where ?? []))];
      if (eventName) {
        where.push({ key: 'event_name', condition: 'and', value: [eventName], method: 'eq' });
      }

      // 异常 tab 增加 type 过滤条件
      if (activeTab.value === EventTab.Warning) {
        where.push({ key: 'type', condition: 'and', value: ['Warning'], method: 'eq' });
      }

      const baseConfig = {
        data_type_label: 'event',
        where,
        query_string: '',
        group_by: [],
        filter_dict: {},
      };

      if (isApm) {
        return {
          ...baseConfig,
          result_table_id: 'builtin',
          data_source_label: 'apm',
        };
      }

      return {
        ...baseConfig,
        data_source_label: 'custom',
        result_table_id: queryConfig?.table ?? undefined,
      };
    };

    /**
     * @description 创建搜索参数
     * @param {any[]} targets - 目标查询配置数组
     * @param {number} startTime - 开始时间戳
     * @param {number} endTime - 结束时间戳
     * @param {Record<string, string>} [additionalParams={}] - 额外参数
     * @returns {URLSearchParams} URL搜索参数对象
     */
    const createSearchParams = (
      targets: any[],
      startTime: number,
      endTime: number,
      additionalParams: Record<string, string> = {}
    ): URLSearchParams => {
      const baseParams = {
        from: (startTime * 1000).toString(),
        to: (endTime * 1000).toString(),
        targets: JSON.stringify(targets),
        ...additionalParams,
      };
      return new URLSearchParams(baseParams);
    };

    /**
     * @description 获取事件详情数据
     * @returns {Promise<void>}
     */
    const getCustomEventTagDetailsData = async (): Promise<void> => {
      if (!props.position.left || !props.position.top || !props.eventItem) return;

      loading.value = true;
      try {
        // eslint-disable-next-line @typescript-eslint/naming-convention
        const { query_config, bizId, ...requestParams } = props.eventItem;
        const interval = query_config?.query_configs?.[0]?.interval ?? 300;
        const { Warning: warning, All: all } = await getAlertEventTagDetails({
          ...requestParams,
          bk_biz_id: bizId,
          interval,
        });

        warningData.value = warning;
        allData.value = all;
        activeTab.value = warningData.value?.total > 0 ? EventTab.Warning : EventTab.All;
      } catch (error) {
        console.error('获取事件详情失败:', error);
      } finally {
        loading.value = false;
      }
    };

    /**
     * @description APM事件检索页跳转
     * @param {number} [startTime] - 开始时间，可选
     * @param {string} [eventName=''] - 事件名称
     * @param {Record<string, any>[]} [defaultWhere=[]] - 默认查询条件
     */
    const navigateToApmEventExplore = (
      startTime?: number,
      eventName = '',
      defaultWhere: Record<string, any>[] = []
    ): void => {
      const eventTarget = props.eventItem?.query_config;
      const queryConfig = createQueryConfig(eventName, defaultWhere, true);
      const targets = [{ data: { query_configs: [queryConfig] } }];

      const calculatedStartTime = startTime || props.eventItem.start_time;
      const endTime = calculatedStartTime + Number(props.eventItem.interval ?? 300);

      const searchParams = createSearchParams(targets, calculatedStartTime, endTime, {
        sceneId: 'apm_service',
        sceneType: 'overview',
        dashboardId: 'service-default-event',
        'filter-app_name': eventTarget?.app_name,
        'filter-service_name': eventTarget?.service_name,
      });

      const url = generateBaseUrl('#/apm/service', props.eventItem.bizId);
      window.open(`${url}?${searchParams.toString()}`, '_blank');
    };

    /**
     * @description 事件检索页跳转
     * @param {number} [startTime] - 开始时间，可选
     * @param {string} [eventName=''] - 事件名称
     * @param {Record<string, any>[]} [defaultWhere=[]] - 默认查询条件
     */
    const navigateToEventExplore = (
      startTime?: number,
      eventName = '',
      defaultWhere: Record<string, any>[] = []
    ): void => {
      const queryConfig = createQueryConfig(eventName, defaultWhere, false);
      const targets = [{ data: { query_configs: [queryConfig] } }];

      const calculatedStartTime = startTime || props.eventItem.start_time;
      const endTime = calculatedStartTime + Number(props.eventItem.interval ?? 300);

      const searchParams = createSearchParams(targets, calculatedStartTime, endTime, {
        filterMode: 'ui',
        commonWhere: JSON.stringify([]),
        showResidentBtn: 'false',
      });

      // 对targets进行URL编码
      searchParams.set('targets', encodeURIComponent(JSON.stringify(targets)));

      const url = generateBaseUrl('#/event-explore', props.eventItem.bizId);
      window.open(`${url}?${searchParams.toString()}`, '_blank');
    };

    /**
     * @description Tab切换处理
     * @param {EventTab} tab - 切换到的Tab
     */
    const handleTabChange = (tab: EventTab): void => {
      activeTab.value = tab;
    };

    /**
     * @description 通用事件详情跳转处理
     * @param {number} [startTime] - 开始时间，可选
     * @param {string} [eventName=''] - 事件名称
     * @param {Record<string, any>[]} [defaultWhere=[]] - 默认查询条件
     */
    const handleEventDetailNavigation = (
      startTime?: number,
      eventName = '',
      defaultWhere: Record<string, any>[] = []
    ): void => {
      const eventTarget = props.eventItem?.query_config;
      const hasApmConfig = eventTarget?.app_name && eventTarget?.service_name;

      if (hasApmConfig) {
        navigateToApmEventExplore(startTime, eventName, defaultWhere);
      } else {
        navigateToEventExplore(startTime, eventName, defaultWhere);
      }
    };

    /**
     * @description 事件列表项详情跳转
     * @param {MouseEvent} event - 鼠标事件
     * @param {IEventListItem} item - 事件列表项
     */
    const handleListGotoEventDetail = (event: MouseEvent, item: IEventListItem): void => {
      event.preventDefault();
      const timeValue = item.time?.value ? +item.time.value / 1000 : undefined;
      const defaultWhere = item.time?.value
        ? [{ key: 'time', value: [item.time.value], method: 'eq', condition: 'and' }]
        : [];

      handleEventDetailNavigation(timeValue, item.event_name.value, defaultWhere);
    };

    /**
     * @description 事件汇总项详情跳转
     * @param {MouseEvent} event - 鼠标事件
     * @param {IEventTopkItem} item - 事件汇总项
     */
    const handleTopKGotoEventDetail = (event: MouseEvent, item: IEventTopkItem): void => {
      event.preventDefault();
      handleEventDetailNavigation(menuData.value.time, item.event_name.value);
    };

    /**
     * @description 渲染事件图标
     * @param {object} source - 事件源对象
     * @param {string} [source.alias] - 别名，可选
     * @param {string} source.value - 值
     * @returns {JSX.Element} 图标元素
     */
    const renderEventIcon = (source: { alias?: string; value: string }) => (
      <span
        style={{ backgroundImage: `url(${base64Svg[source.value?.toLowerCase() || DEFAULT_SVG]})` }}
        class='event-icon'
        v-bk-tooltips={{ content: source.alias || source.value }}
      />
    );

    /**
     * @description 渲染详情按钮
     * @param {(e: MouseEvent) => void} onClick - 点击事件处理函数
     * @param {string} [tooltipContent=t('查看事件详情')] - 提示内容
     * @returns {JSX.Element} 按钮元素
     */
    const renderDetailButton = (onClick: (e: MouseEvent) => void, tooltipContent = t('查看事件详情')) => (
      <i
        class='icon-monitor icon-xiangqing1 link-icon'
        v-bk-tooltips={{
          content: tooltipContent,
          allowHTML: false,
        }}
        onMousedown={onClick}
      />
    );

    /**
     * @description 渲染单个事件标题
     * @param {IEventListItem} item - 事件列表项
     * @returns {JSX.Element} 标题元素
     */
    const renderSingleEventTitle = (item: IEventListItem) => (
      <div class='alarm-chart-event-detail-title'>
        {renderEventIcon(item.source)}
        <div class='event-name'>{item.event_name.alias}</div>
        <span
          class='detail-btn is-url'
          v-bk-tooltips={{
            content: t('查看事件详情'),
            allowHTML: false,
          }}
          onMousedown={e => handleListGotoEventDetail(e, item)}
        >
          <i class='icon-monitor icon-xiangqing1 detail-icon' />
          {t('详情')}
        </span>
      </div>
    );

    /**
     * @description 渲染多事件标题
     * @param {IEventListItem[] | IEventTopkItem[]} data - 事件数据数组
     * @param {boolean} isList - 是否为列表数据
     * @returns {JSX.Element} 标题元素
     */
    const renderMultiEventTitle = (data: IEventListItem[] | IEventTopkItem[], isList: boolean) => (
      <div class='alarm-chart-event-detail-title'>
        <div class='event-name'>
          {isList ? (
            <i18n-t keypath={'共 {0} 个事件，展示 Top{1}'}>
              <span style='font-weight: bold;color:#313238;'> {menuData.value.total} </span>
              <span style='font-weight: bold;color:#313238;'> {data.length} </span>
            </i18n-t>
          ) : (
            <i18n-t keypath={'共 {0} 个事件，已按事件名汇总'}>
              <span style='font-weight: bold;color:#313238;'> {menuData.value.total} </span>
            </i18n-t>
          )}
        </div>
        <span
          style='color: #979BA5;'
          class='detail-btn'
        >
          {dayjs(menuData.value.time * 1000).format('YYYY-MM-DD HH:mm:ssZZ')}
        </span>
      </div>
    );

    /**
     * @description 创建标题渲染
     * @returns {JSX.Element | null} 标题元素或null
     */
    const createTitleRender = () => {
      if (!menuData.value?.list?.length && !menuData.value.topk) return null;

      const { list, topk } = menuData.value;
      const data = list || topk;

      if (list?.length === 1) {
        return renderSingleEventTitle(list[0] as unknown as IEventListItem);
      }

      if (data?.length > 0) {
        return renderMultiEventTitle(data as unknown as IEventListItem[] | IEventTopkItem[], !!list?.length);
      }

      return null;
    };

    /**
     * @description 创建更多按钮
     * @returns {JSX.Element | null} 更多按钮元素或null
     */
    const createContentMore = () => {
      const shouldShowMore =
        menuData.value?.list?.length < menuData.value.total || menuData.value?.topk?.length < menuData.value.total;

      if (!shouldShowMore) return null;

      return (
        <div
          class='common-more'
          onMousedown={e => {
            e.preventDefault();
            handleEventDetailNavigation(menuData.value.time);
          }}
        >
          ...
          <Button
            size='small'
            theme='primary'
            text
          >
            {t('更多')}
            <i class='icon-monitor icon-mc-goto' />
          </Button>
        </div>
      );
    };

    /**
     * @description 渲染单个事件内容详情
     * @param {IEventListItem} item - 事件列表项
     * @returns {JSX.Element} 内容元素
     */
    const renderSingleEventContent = (item: IEventListItem) => (
      <div class='alarm-chart-event-detail-content'>
        {Object.values(item['event.content'].detail).map(detailItem => (
          <div
            key={detailItem.label}
            class='content-item'
          >
            <div class='content-item-label'>{detailItem.label}:</div>
            <div class='content-item-value'>
              {detailItem.url ? (
                <span
                  class='is-url'
                  onMousedown={() => window.open(detailItem.url, '_blank')}
                >
                  {detailItem.alias || detailItem.value}
                </span>
              ) : (
                detailItem.alias || detailItem.value
              )}
            </div>
          </div>
        ))}
      </div>
    );

    /**
     * @description 渲染事件列表内容
     * @param {IEventListItem[]} list - 事件列表数组
     * @returns {JSX.Element} 内容元素
     */
    const renderEventListContent = (list: IEventListItem[]) => (
      <div class='alarm-chart-event-detail-content'>
        {list.map((item, index) => (
          <div
            key={item.event_name?.value || index}
            class='content-item'
          >
            {renderEventIcon(item.source)}
            <div class='content-item-content'>
              {item.event_name.alias}
              <span
                class='is-url'
                v-bk-tooltips={{
                  content: t('查看资源'),
                  allowHTML: false,
                }}
                onMousedown={() => item.target.url && window.open(item.target.url, '_blank')}
              >
                （{item.target.alias}）
              </span>
            </div>
            {renderDetailButton(e => handleListGotoEventDetail(e, item))}
          </div>
        ))}
        {createContentMore()}
      </div>
    );

    /**
     * @description 渲染TopK进度条内容
     * @param {IEventTopkItem[]} topk - TopK事件数组
     * @returns {JSX.Element} 内容元素
     */
    const renderTopKContent = (topk: IEventTopkItem[]) => (
      <div class='alarm-chart-event-detail-content'>
        {topk.map((item, index) => (
          <div
            key={item.event_name?.value || index}
            class='content-progress'
          >
            <div class='progress-title'>
              {renderEventIcon(item.source)}
              {item.event_name.alias}
              <span class='proportions-num'>{item.count}</span>
              {renderDetailButton(e => handleTopKGotoEventDetail(e, item))}
            </div>
            <Progress
              color={TAB_COLORS[activeTab.value === EventTab.Warning ? EventTab.Warning : EventTab.All]}
              percent={Math.max(+item.proportions.toFixed(2), 0.01)}
              show-text={false}
            />
          </div>
        ))}
        {createContentMore()}
      </div>
    );

    /**
     * @description 创建内容渲染
     * @returns {JSX.Element} 内容元素
     */
    const createContentRender = () => {
      const { list, topk } = menuData.value || {};

      if (list?.length === 1) {
        return renderSingleEventContent(list[0] as unknown as IEventListItem);
      }

      if (list?.length > 1) {
        return renderEventListContent(list as unknown as IEventListItem[]);
      }

      if (topk?.length) {
        return renderTopKContent(topk as unknown as IEventTopkItem[]);
      }

      return (
        <Exception
          class='no-data'
          scene='part'
          type='empty'
        >
          {t('暂无数据')}
        </Exception>
      );
    };

    /**
     * @description 创建头部标签渲染
     * @returns {JSX.Element | null} 头部元素或null
     */
    const createHeaderRender = () => {
      if (!warningData.value?.total || loading.value || !menuData.value?.total) return null;

      return (
        <div class='alarm-chart-event-detail-header'>
          {[EventTab.Warning, EventTab.All].map(level => (
            <div
              key={level}
              style={{
                borderTopColor: level !== activeTab.value ? '#F0F1F5' : TAB_COLORS[level],
                backgroundColor: level === activeTab.value ? 'transparent' : '#F0F1F5',
              }}
              class='header-tab'
              onMousedown={() => handleTabChange(level)}
            >
              {level === EventTab.Warning
                ? t('异常事件 ({0})', [warningData.value.total || 0])
                : t('全部事件 ({0})', [allData.value.total])}
            </div>
          ))}
        </div>
      );
    };

    /**
     * @description 创建加载状态渲染
     * @returns {JSX.Element[]} 加载状态元素数组
     */
    const createLoadingRender = () => [
      <div
        key='title'
        class='alarm-chart-event-detail-title'
      >
        <div
          style='width: 33%'
          class='skeleton-element custom-menu-skeleton'
        />
      </div>,
      <div
        key='content'
        class='alarm-chart-event-detail-content'
      >
        <div
          style='width: 90%'
          class='skeleton-element custom-menu-skeleton'
        />
        <div
          style='width: 70%'
          class='skeleton-element custom-menu-skeleton'
        />
        <div
          style='width: 50%'
          class='skeleton-element custom-menu-skeleton'
        />
      </div>,
    ];

    // 监听eventItem变化，重新获取数据
    watch(() => props.eventItem, getCustomEventTagDetailsData, { deep: true, immediate: true });

    return {
      loading,
      getComponentHeight,
      createTitleRender,
      createContentRender,
      createHeaderRender,
      createLoadingRender,
    };
  },
  render() {
    // 位置校验
    if (!this.position?.left || !this.position?.top) return null;

    return (
      <div
        ref='eventDetailRef'
        style={{
          left: `${this.position.left}px`,
          top: `${this.position.top}px`,
        }}
        class='alarm-chart-event-detail'
      >
        {this.loading && this.createLoadingRender()}
        {!this.loading && [this.createHeaderRender(), this.createTitleRender(), this.createContentRender()]}
      </div>
    );
  },
});
