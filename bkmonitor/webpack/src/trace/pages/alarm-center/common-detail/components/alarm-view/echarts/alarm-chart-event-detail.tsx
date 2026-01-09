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

import { type PropType, computed, defineComponent, shallowRef, watch } from 'vue';

import { Button, Exception, Progress } from 'bkui-vue';
import dayjs from 'dayjs';
import base64Svg from 'monitor-common/svg/base64';
import { useI18n } from 'vue-i18n';

import { getAlertEventTagDetails } from '@/pages/alarm-center/services/alarm-detail';

import type { AlertEventTagDetailParams } from '@/pages/alarm-center/typings';
import type { ICustomEventDetail } from 'monitor-ui/chart-plugins/plugins/caller-line-chart/use-custom';

import './alarm-chart-event-detail.scss';

export enum EventTab {
  All = 'all',
  Warning = 'warning',
}

export interface IPosition {
  left: number;
  top: number;
}

export default defineComponent({
  name: 'AlarmChartEventDetail',
  props: {
    position: {
      type: Object as PropType<IPosition>,
      required: true,
    },
    eventItem: {
      type: Object as PropType<Partial<AlertEventTagDetailParams>>,
      required: true,
    },
  },
  setup(props) {
    const { t } = useI18n();

    const warningData = shallowRef<ICustomEventDetail>({});
    const allData = shallowRef<ICustomEventDetail>({});
    const activeTab = shallowRef<EventTab>(EventTab.Warning);
    const loading = shallowRef(false);

    const menuData = computed<ICustomEventDetail>(() => {
      return activeTab.value === EventTab.Warning ? warningData.value : allData.value;
    });

    const getCustomEventTagDetailsData = async () => {
      if (props.position.left && props.position.top && props.eventItem) {
        loading.value = true;
        // eslint-disable-next-line @typescript-eslint/naming-convention
        const { query_config: _, bizId: __, ...requestParams } = props.eventItem;
        try {
          const { Warning, All } = await getAlertEventTagDetails(requestParams);
          warningData.value = Warning;
          allData.value = All;
          activeTab.value = warningData.value?.total > 0 ? EventTab.Warning : EventTab.All;
        } catch (error) {
          console.error('获取事件详情失败:', error);
        } finally {
          loading.value = false;
        }
      }
    };

    /**
     * @description: 获取跳转url
     * @param {string} hash hash值
     * @param {number} bizId 业务ID
     * @return {*}
     */
    const commOpenUrl = (hash: string, bizId?: number) => {
      let url = '';
      if (process.env.NODE_ENV === 'development') {
        url = `${process.env.proxyUrl}?bizId=${bizId || window.cc_biz_id}${hash}`;
      } else {
        url = location.href.replace(location.hash, hash);
      }
      return url;
    };

    const handleTabChange = (tab: EventTab) => {
      activeTab.value = tab;
    };

    const createApmEventExploreHref = (
      startTime?: number,
      eventName = '',
      defaultWhere: Record<string, any>[] = []
    ) => {
      const eventTarget = props.eventItem?.query_config;
      const targets = [
        {
          data: {
            query_configs: [
              {
                result_table_id: 'builtin',
                data_type_label: 'event',
                data_source_label: 'apm',
                where: eventName
                  ? [
                      {
                        key: 'event_name',
                        condition: 'and',
                        value: [eventName],
                        method: 'eq',
                      },
                      ...defaultWhere,
                    ]
                  : [],
                query_string: '',
                group_by: [],
                filter_dict: {},
              },
            ],
          },
        },
      ];
      const searchParams = new URLSearchParams({
        sceneId: 'apm_service',
        sceneType: 'overview',
        dashboardId: 'service-default-event',
        from: ((startTime || props.eventItem.start_time) * 1000).toString(),
        to: `${((startTime || props.eventItem.start_time) + (props.eventItem.interval ?? 0)) * 1000}`,
        'filter-app_name': eventTarget?.app_name,
        'filter-service_name': eventTarget?.service_name,
        targets: JSON.stringify(targets),
      });
      const url = commOpenUrl('#/apm/service', props.eventItem.bizId);
      window.open(`${url}?${searchParams.toString()}`, '_blank');
    };

    /**
     * @description 跳转到事件检索页
     */
    const handleToEventExplore = (startTime?: number, eventName = '', defaultWhere: Record<string, any>[] = []) => {
      const eventTarget = props.eventItem?.query_config;
      const queryConfig = eventTarget?.query_configs?.[0];
      const targets = [
        {
          data: {
            query_configs: [
              {
                data_type_label: 'event',
                data_source_label: 'custom',
                where: eventName
                  ? [
                      {
                        key: 'event_name',
                        condition: 'and',
                        value: [eventName],
                        method: 'eq',
                      },
                      ...(queryConfig?.where ?? []),
                      ...defaultWhere,
                    ]
                  : [],
                query_string: '',
                group_by: [],
                filter_dict: {},
                result_table_id: queryConfig?.table ?? undefined,
              },
            ],
          },
        },
      ];
      const searchParams = new URLSearchParams({
        filterMode: 'ui',
        commonWhere: JSON.stringify([]),
        showResidentBtn: 'false',
        from: ((startTime || props.eventItem.start_time) * 1000).toString(),
        to: `${((startTime || props.eventItem.start_time) + (props.eventItem.interval ?? 0)) * 1000}`,
        targets: encodeURIComponent(JSON.stringify(targets)),
      });
      const url = commOpenUrl('#/event-explore', props.eventItem.bizId);
      window.open(`${url}?${searchParams.toString()}`, '_blank');
    };

    /**
     * @description 查看详情点击回调(事件列表项面板)
     * @param event MouseEvent鼠标事件
     * @param item 事件列表项
     */
    const handleListGotoEventDetail = (event: MouseEvent, item: ICustomEventDetail['list'][number]) => {
      event.preventDefault();
      console.log('handleListGotoEventDetail', item);
      const eventTarget = props.eventItem?.query_config;
      // 如果有app_name和service_name，跳转到APM事件检索页，否则跳转到事件检索页
      if (eventTarget?.app_name && eventTarget?.service_name) {
        createApmEventExploreHref(+item.time?.value / 1000, item.event_name.value, [
          { key: 'time', value: [item.time?.value], method: 'eq', condition: 'and' },
        ]);
      } else {
        handleToEventExplore(menuData.value.time, item.event_name.value);
      }
    };

    /**
     * @description 查看详情点击回调(事件汇总面板)
     * @param event MouseEvent鼠标事件
     * @param item 事件汇总项
     */
    const handleTopKGotoEventDetail = (event: MouseEvent, item: ICustomEventDetail['topk'][number]) => {
      event.preventDefault();
      console.log('handleListGotoEventDetail', item);
      const eventTarget = props.eventItem?.query_config;
      // 如果有app_name和service_name，跳转到APM事件检索页，否则跳转到事件检索页
      if (eventTarget?.app_name && eventTarget?.service_name) {
        createApmEventExploreHref(menuData.value.time, item.event_name.value);
      } else {
        handleToEventExplore(menuData.value.time, item.event_name.value);
      }
    };

    const createTitleRender = () => {
      if (!menuData.value?.list?.length && !menuData.value.topk) return null;
      const { list, time, topk } = menuData.value;
      const data = list || topk;

      if (list?.length === 1) {
        const { event_name, source } = data[0];
        return (
          <div class='alarm-chart-event-detail-title'>
            <span
              style={{ backgroundImage: `url(${base64Svg[source.value?.toLowerCase() || 'bcs']})` }}
              class='event-icon'
              v-bk-tooltips={{ content: source.alias }}
            />
            <div class='event-name'>{event_name.alias}</div>
            <span
              class='detail-btn is-url'
              v-bk-tooltips={{
                content: t('查看事件详情'),
                allowHTML: false,
              }}
              onMousedown={e => handleListGotoEventDetail(e, list[0])}
            >
              <i class='icon-monitor icon-xiangqing1 detail-icon' />
              {t('详情')}
            </span>
          </div>
        );
      }

      if (data?.length > 0) {
        return (
          <div class='alarm-chart-event-detail-title'>
            <div class='event-name'>
              {list?.length > 0 ? (
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
              {dayjs(time * 1000).format('YYYY-MM-DD HH:mm:ssZZ')}
            </span>
          </div>
        );
      }
      return null;
    };

    const createContentRender = () => {
      const { list, topk } = menuData.value || {};

      if (list?.length === 1) {
        const {
          'event.content': { detail },
        } = list[0];
        return (
          <div class='alarm-chart-event-detail-content'>
            {Object.values(detail).map(item => {
              return (
                <div
                  key={item.label}
                  class='content-item'
                >
                  <div class='content-item-label'>{item.label}:</div>
                  <div class={'content-item-value'}>
                    {item.url ? (
                      <span
                        class='is-url'
                        onMousedown={() => window.open(item.url, '_blank')}
                      >
                        {item.alias || item.value}
                      </span>
                    ) : (
                      item.alias || item.value
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        );
      }

      if (list?.length > 1) {
        return (
          <div class='alarm-chart-event-detail-content'>
            {list.map((item, index) => {
              return (
                <div
                  key={index}
                  class='content-item'
                >
                  <span
                    style={{ backgroundImage: `url(${base64Svg[item?.source.value?.toLowerCase() || 'bcs']})` }}
                    class='event-icon'
                    v-bk-tooltips={{ content: item?.source.alias }}
                  />
                  <div class='content-item-content'>
                    {item.event_name.alias}
                    <span
                      class='is-url '
                      v-bk-tooltips={{
                        content: t('查看资源'),
                        allowHTML: false,
                      }}
                      onMousedown={() => item.target.url && window.open(item.target.url, '_blank')}
                    >
                      （{item.target.alias}）
                    </span>
                  </div>
                  <i
                    class='icon-monitor icon-xiangqing1 link-icon'
                    v-bk-tooltips={{
                      content: t('查看事件详情'),
                      allowHTML: false,
                    }}
                    onMousedown={e => handleListGotoEventDetail(e, item)}
                  />
                </div>
              );
            })}
            {createContentMore()}
          </div>
        );
      }

      if (topk?.length) {
        return (
          <div class='alarm-chart-event-detail-content'>
            {topk.map((item, index) => {
              return (
                <div
                  key={index}
                  class='content-progress'
                >
                  <div class='progress-title'>
                    <span
                      style={{ backgroundImage: `url(${base64Svg[item?.source.value?.toLowerCase() || 'bcs']})` }}
                      class='event-icon'
                      v-bk-tooltips={{ content: item?.source.alias }}
                    />
                    {item.event_name.alias}
                    <span class='proportions-num'>{item.count}</span>
                    <i
                      style={{ marginLeft: '0px' }}
                      class='icon-monitor icon-xiangqing1 link-icon'
                      v-bk-tooltips={{
                        content: t('查看事件详情'),
                        allowHTML: false,
                      }}
                      onMousedown={e => handleTopKGotoEventDetail(e, item)}
                    />
                  </div>
                  <Progress
                    color={activeTab.value === EventTab.Warning ? '#F59500' : '#3A84FF'}
                    percent={Math.max(+item.proportions.toFixed(2), 0.01)}
                    show-text={false}
                  />
                </div>
              );
            })}
            {createContentMore()}
          </div>
        );
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

    const createHeaderRender = () => {
      if (!warningData.value?.total || loading.value || !menuData.value?.total) return null;
      return (
        <div class='alarm-chart-event-detail-header'>
          {[EventTab.Warning, EventTab.All].map(level => {
            return (
              <div
                key={level}
                style={{
                  borderTopColor:
                    level !== activeTab.value ? '#F0F1F5' : level === EventTab.Warning ? '#F59500' : '#3A84FF',
                  backgroundColor: level === activeTab.value ? 'transparent' : '#F0F1F5',
                }}
                class='header-tab'
                onMousedown={() => handleTabChange(level)}
              >
                {level === EventTab.Warning
                  ? t('异常事件 ({0})', [warningData.value.total || 0])
                  : t('全部事件 ({0})', [allData.value.total])}
              </div>
            );
          })}
        </div>
      );
    };

    const createContentMore = () => {
      if (menuData.value?.list?.length >= menuData.value.total && menuData.value?.topk?.length >= menuData.value.total)
        return null;
      return (
        <div
          class='common-more'
          onMousedown={e => {
            e.preventDefault();
            createApmEventExploreHref(menuData.value.time);
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

    const createLoadingRender = () => {
      return [
        <div
          key={'title'}
          class='alarm-chart-event-detail-title'
        >
          <div
            style='width: 33%'
            class='skeleton-element custom-menu-skeleton'
          />
        </div>,
        <div
          key={'content'}
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
    };

    watch(
      () => props.eventItem,
      () => {
        getCustomEventTagDetailsData();
      },
      { deep: true, immediate: true }
    );

    return {
      loading,
      createTitleRender,
      createContentRender,
      createHeaderRender,
      createLoadingRender,
    };
  },
  render() {
    if (!this.position?.left || !this.position?.top) return null;
    return (
      <div
        style={{
          left: `${this.position.left}px`,
          top: `${this.position.top}px`,
        }}
        class='alarm-chart-event-detail'
      >
        {this.loading && this.createLoadingRender()}
        {!this.loading && this.createHeaderRender()}
        {!this.loading && this.createTitleRender()}
        {!this.loading && this.createContentRender()}
      </div>
    );
  },
});
