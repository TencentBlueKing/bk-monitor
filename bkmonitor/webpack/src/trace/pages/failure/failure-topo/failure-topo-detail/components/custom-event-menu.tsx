/* eslint-disable @typescript-eslint/naming-convention */
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
import { type PropType, computed, ref as deepRef, defineComponent, watch } from 'vue';

import { Progress } from 'bkui-vue';
import dayjs from 'dayjs';
import base64Svg from 'monitor-common/svg/base64';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import ExceptionComp from '../../../../../components/exception';
import { handleToEventPage } from '../../utils';
import { getIncidentEventTagDetails } from '../use-custom';

import type { IEventTagsItem, IPosition } from '../../types';
import type { ICustomEventDetail, ITargetInfo } from 'monitor-ui/chart-plugins/plugins/caller-line-chart/use-custom';

import './custom-event-menu.scss';

enum EventTab {
  All = 'all',
  Warning = 'warning',
}

export default defineComponent({
  name: 'CustomEventMenu',
  props: {
    position: {
      type: Object as PropType<IPosition>,
      required: true,
    },
    eventItem: {
      type: Object as PropType<Partial<IEventTagsItem>>,
      required: true,
    },
    nodeType: {
      type: String,
      required: true,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const route = useRoute();
    const router = useRouter();

    const warningData = deepRef<ICustomEventDetail>({});
    const allData = deepRef<ICustomEventDetail>({});
    const activeTab = deepRef<EventTab>(EventTab.Warning);
    const loading = deepRef(false);

    const menuData = computed(() => (activeTab.value === EventTab.Warning ? warningData.value : allData.value));

    // 是否为异常事件类型
    const isWarningEvent = computed(
      () => warningData.value?.total && warningData.value?.total > 0 && activeTab.value === EventTab.Warning
    );

    const fetchData = async () => {
      if (props.position?.left && props.position?.top && props.eventItem) {
        loading.value = true;
        try {
          const { interval, index_info, start_time, end_time } = props.eventItem;
          const { Warning, All } = await getIncidentEventTagDetails({
            app_name: '',
            service_name: '',
            expression: 'a',
            bk_biz_id: props.eventItem.bk_biz_id,
            interval,
            index_info,
            start_time,
            end_time,
          });

          warningData.value = Warning;
          allData.value = All;
          activeTab.value = warningData.value?.total > 0 ? EventTab.Warning : EventTab.All;
        } finally {
          loading.value = false;
        }
      }
    };

    watch(() => props.eventItem, fetchData, { deep: true, immediate: true });

    const handleTabChange = (tab: EventTab) => {
      activeTab.value = tab;
    };

    /** 跳转到apm/service页面 */
    const createApmEventExploreHref = (
      item: ICustomEventDetail['list'][number] | ICustomEventDetail['topk'][number],
      endTime: number,
      eventName = ''
    ) => {
      const { app_name, service_name } = item.target_info.dimensions;
      const baseWhere = [];
      // 为异常事件跳转时，添加type为Warning的where条件
      if (isWarningEvent.value) {
        baseWhere.push({ key: 'type', condition: 'and', value: ['Warning'], method: 'eq' });
      }
      if (eventName) {
        baseWhere.push({ key: 'event_name', condition: 'and', value: [eventName], method: 'eq' });
      }
      const queryConfigs: {
        data_source_label: string;
        data_type_label: string;
        filter_dict: object;
        group_by: any[];
        query_string: string;
        result_table_id?: string;
        where: any[];
      } = {
        data_type_label: 'event',
        data_source_label: 'apm',
        where: baseWhere,
        query_string: '',
        group_by: [],
        filter_dict: {},
      };
      if (item.target_info.table) {
        queryConfigs.result_table_id = item.target_info.table;
      }

      const targets = [
        {
          data: {
            query_configs: [queryConfigs],
          },
        },
      ];

      const query = {
        sceneId: 'apm_service',
        sceneType: 'overview',
        dashboardId: 'service-default-event',
        from: item.target_info.start_time.toString(),
        to: endTime.toString(),
        'filter-app_name': app_name,
        'filter-service_name': service_name,
        targets: JSON.stringify(targets),
      };

      const { href } = router.resolve({
        path: route.path,
        query,
      });
      // 由于route.path为'#/trace/incident/detail/xxx?'，要跳转至apm服务页面，需要将其替换为'#/apm/service?'
      const replacedHref = href.replace(/#.*?\?/, '#/apm/service?');
      window.open(location.href.replace(location.hash, replacedHref), '_blank');
    };

    /** 通用跳转到事件检索页函数 */
    const handlePodHostEvent = (
      item: ICustomEventDetail['list'][number] | ICustomEventDetail['topk'][number],
      isClickMore: boolean,
      endTime: number
    ) => {
      handleToEventPage(item.target_info as ITargetInfo, props.nodeType, isClickMore, isWarningEvent.value, endTime);
    };

    /** 查看更多 */
    const handleClickMore = (e: MouseEvent) => {
      e.preventDefault();
      const item = menuData.value.list?.length ? menuData.value.list[0] : menuData.value.topk[0];
      const endTime = menuData.value.list?.length
        ? Number(item.target_info.start_time) + 1000
        : Number(item.target_info.start_time) + Number(props.eventItem.interval) * 1000;
      if (['pod', 'host'].includes(props.nodeType)) {
        handlePodHostEvent(item, true, endTime);
      } else {
        createApmEventExploreHref(item, endTime);
      }
    };

    /** 查看事件详情函数 (列表项) */
    const handleListGotoEventDetail = (e: MouseEvent, item: ICustomEventDetail['list'][number]) => {
      e.preventDefault();
      const endTime = Number(item.target_info.start_time) + 1000;
      if (['pod', 'host'].includes(props.nodeType)) {
        handlePodHostEvent(item, false, endTime);
      } else {
        createApmEventExploreHref(item, endTime, item.target_info.event_name);
      }
    };

    /** 查看事件详情函数 (TopK项) */
    const handleTopKGotoEventDetail = (e: MouseEvent, item: ICustomEventDetail['topk'][number]) => {
      e.preventDefault();
      const endTime = Number(item.target_info.start_time) + Number(props.eventItem.interval) * 1000;
      if (['pod', 'host'].includes(props.nodeType)) {
        handlePodHostEvent(item, false, endTime);
      } else {
        createApmEventExploreHref(item, endTime, item.target_info.event_name);
      }
    };

    return {
      loading,
      menuData,
      warningData,
      allData,
      activeTab,
      handleTabChange,
      handleListGotoEventDetail,
      handleTopKGotoEventDetail,
      t,
      handleClickMore,
    };
  },
  render() {
    if (!this.position?.left || !this.position?.top) return null;

    // 辅助渲染方法
    const createTitle = () => {
      if (!this.menuData?.list?.length && !this.menuData.topk) return undefined;
      const { list, time, topk } = this.menuData;
      const data = list || topk;
      if (list?.length === 1) {
        const { event_name, source } = data[0];
        return (
          <div class='custom-event-menu-title'>
            <span
              style={{ backgroundImage: `url(${base64Svg[source.value?.toLowerCase() || 'bcs']})` }}
              class='event-icon'
              v-bk-tooltips={{ content: source.alias, extCls: 'event-analyze-tooltip' }}
            />
            <div class='event-name'>{event_name.alias}</div>
            <span
              class='detail-btn is-url'
              v-bk-tooltips={{
                content: this.t('查看事件详情'),
                allowHTML: false,
                extCls: 'event-analyze-tooltip',
              }}
              onMousedown={e => this.handleListGotoEventDetail(e, list[0])}
            >
              <i class='icon-monitor icon-xiangqing1 detail-icon' />
              {this.t('详情')}
            </span>
          </div>
        );
      }
      if (data?.length > 0) {
        // const { source } = data[0];
        return (
          <div class='custom-event-menu-title'>
            <div class='event-name'>
              {list?.length > 0 ? (
                <i18n-t keypath={'共 {0} 个事件，展示 {1}'}>
                  <span style='font-weight: bold;color:#EAEBF0;'> {this.menuData.total} </span>
                  <span style='font-weight: bold;color:#EAEBF0;'> {`Top${data.length}`} </span>
                </i18n-t>
              ) : (
                <i18n-t keypath={'共 {0} 个事件，已按事件名汇总'}>
                  <span style='font-weight: bold;color:#EAEBF0;'>{this.menuData.total}</span>
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
    };

    const createContent = () => {
      const { list, topk } = this.menuData || {};
      if (list?.length === 1) {
        const {
          'event.content': { detail },
        } = list[0];
        return (
          <div class='custom-event-menu-content'>
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
          <div class='custom-event-menu-content'>
            {list.map((item, index) => {
              return (
                <div
                  key={index}
                  class='content-item'
                >
                  <span
                    style={{ backgroundImage: `url(${base64Svg[item?.source.value?.toLowerCase() || 'bcs']})` }}
                    class='event-icon'
                    v-bk-tooltips={{ content: item?.source.alias, extCls: 'event-analyze-tooltip' }}
                  />
                  <div class='content-item-content'>
                    {item.event_name.alias}
                    <span
                      class='is-url '
                      v-bk-tooltips={{
                        content: this.t('查看资源'),
                        allowHTML: false,
                        extCls: 'event-analyze-tooltip',
                      }}
                      onMousedown={() => item.target.url && window.open(item.target.url, '_blank')}
                    >
                      （{item.target.alias}）
                    </span>
                  </div>
                  <i
                    class='icon-monitor icon-xiangqing1 link-icon'
                    v-bk-tooltips={{
                      content: this.t('查看事件详情'),
                      allowHTML: false,
                      extCls: 'event-analyze-tooltip',
                    }}
                    onMousedown={e => this.handleListGotoEventDetail(e, item)}
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
          <div class='custom-event-menu-content'>
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
                      v-bk-tooltips={{ content: item?.source.alias, extCls: 'event-analyze-tooltip' }}
                    />
                    {item.event_name.alias}
                    <span class='proportions-num'>{item.count}</span>
                    <i
                      style={{ marginLeft: '0px' }}
                      class='icon-monitor icon-xiangqing1 link-icon'
                      v-bk-tooltips={{
                        content: this.t('查看事件详情'),
                        allowHTML: false,
                        extCls: 'event-analyze-tooltip',
                      }}
                      onMousedown={e => this.handleTopKGotoEventDetail(e, item)}
                    />
                  </div>
                  <Progress
                    color={this.activeTab === EventTab.Warning ? '#F59500' : '#699DF4'}
                    // percent={Math.max(+(item.proportions / 100).toFixed(2), 0.01)}
                    percent={Math.max(+item.proportions.toFixed(2), 0.01)}
                    show-text={false}
                    size='small'
                  />
                </div>
              );
            })}
            {createContentMore()}
          </div>
        );
      }
      return (
        <ExceptionComp
          imgHeight={100}
          isDarkTheme={true}
          isError={false}
          title={this.t('暂无数据')}
        />
      );
    };

    const createHeader = () => {
      if (!this.warningData?.total || this.loading || !this.menuData?.total) return undefined;
      return (
        <div class='custom-event-menu-header'>
          {[EventTab.Warning, EventTab.All].map(level => {
            return (
              <div
                key={level}
                style={{
                  borderTopColor:
                    level !== this.activeTab ? 'transparent' : level === EventTab.Warning ? '#F59500' : '#699DF4',
                  backgroundColor: level === this.activeTab ? 'transparent' : '#3F4247',
                  color: level === this.activeTab ? '#EAEBF0' : '#C4C6CC',
                }}
                class='header-tab'
                onMousedown={() => this.handleTabChange(level)}
              >
                {level === EventTab.Warning
                  ? this.t('异常事件 ({0})', [this.warningData.total || 0])
                  : this.t('全部事件 ({0})', [this.allData.total])}
              </div>
            );
          })}
        </div>
      );
    };

    const createContentMore = () => {
      const topk = this.menuData?.topk ? this.menuData?.topk.length >= this.menuData.total : true;
      if (this.menuData?.list?.length >= this.menuData.total && topk) return undefined;
      return (
        <div
          class='common-more'
          onMousedown={e => this.handleClickMore(e)}
        >
          ...
          <span>{this.t('更多')}</span>
          <i class='icon-monitor icon-mc-goto' />
        </div>
      );
    };

    return (
      <div
        style={{
          left: `${this.position.left}px`,
          top: `${this.position.top}px`,
        }}
        class='custom-event-menu'
      >
        {this.loading && (
          <>
            <div class='custom-event-menu-title'>
              <div
                style='width: 33%'
                class='skeleton-element custom-menu-skeleton'
              />
            </div>
            <div class='custom-event-menu-content'>
              {[90, 70, 50].map(width => (
                <div
                  key={`skeleton-${width}`}
                  style={`width: ${width}%`}
                  class='skeleton-element custom-menu-skeleton'
                />
              ))}
            </div>
          </>
        )}

        {!this.loading && (
          <>
            {createHeader()}
            {createTitle()}
            {createContent()}
          </>
        )}
      </div>
    );
  },
});
