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
import {
  type Ref,
  computed,
  defineComponent,
  inject,
  onBeforeUnmount,
  onMounted,
  reactive,
  shallowRef,
  watch,
} from 'vue';

import { bkTooltips, Collapse, Dropdown, Exception, Loading, Message, Popover, Sideslider } from 'bkui-vue';
import { incidentDiagnosis } from 'monitor-api/modules/incident';
import base64Svg from 'monitor-common/svg/base64';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import MarkdownViewer from '../../../components/markdown-editor/viewer';
import { EVENTS_TYPE_MAP } from '../constant';
import { checkOverflow } from '../utils';

import type {
  IAlertData,
  IAnomalyAnalysis,
  IContentList,
  IEventsAnalysis,
  IEventsContentsData,
  IListItem,
  ILogAnalysis,
  IStrategyMapItem,
  ISummaryList,
} from '../types';

import './trouble-shooting.scss';

export default defineComponent({
  name: 'TroubleShooting',
  directives: {
    bkTooltips,
  },
  props: {
    panelConfig: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['alertList', 'strategy'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const route = useRoute();
    const isAllCollapsed = shallowRef(true);
    const contentList: IContentList = reactive({});
    // 总结信息汇总
    const summaryList: ISummaryList = reactive({});
    // 事件分析数据整理
    const eventsData = shallowRef<IEventsAnalysis[]>([]);
    const loadingList = reactive({
      summary: false,
    });
    const dimensionalActiveIndex = shallowRef([0]);
    const eventActiveIndex = shallowRef([0]);
    const eventChildActiveIndex = shallowRef<Record<string, number[]>>({});
    const logActiveIndex = shallowRef([0]);
    const bkzIds = inject<Ref<string[]>>('bkzIds');
    // 是否展示详情侧边栏
    const showSideSlider = shallowRef(false);
    // 当前选中的card
    const curSliderId = shallowRef('');
    const subPanels = computed(() => {
      return props.panelConfig.sub_panels || {};
    });
    const aiLoading = computed(() => {
      return subPanels.value?.summary?.status;
    });

    const showList = computed(() => {
      return list.filter(item => subPanels.value?.[item.key]?.enabled);
    });

    const showPatternPop = reactive<Record<number, boolean>>({});
    const patternOverflowMap = reactive<Record<number, boolean>>({});
    // 每个示例日志项的popover展示状态
    const showDemoLogPop = reactive<Record<number, boolean>>({});
    // 存储每个示例日志项的溢出状态
    const demoLogOverflowMap = reactive<Record<number, boolean>>({});

    /** 跳转到告警tab带上策路ID过滤 */
    const goDetail = (data: IStrategyMapItem) => {
      emit('strategy', data);
    };

    /** 跳转到告警tab */
    const goAlertList = (list: IAlertData[]) => {
      emit('alertList', list);
    };

    /** 拷贝操作 */
    const handleCopy = (text: string) => {
      copyText(text);
      Message({
        theme: 'success',
        message: t('复制成功'),
      });
    };

    const dimensionalTitleSlot = (item: IAnomalyAnalysis) => (
      <span class='dimensional-title'>
        {item.name || `异常维度（组合）${item.$index + 1}`}
        <i18n-t
          class='red-font'
          keypath='异常程度 {0}'
          tag='span'
        >
          <span style='font-weight: 700;'> {((item?.score || 0) * 100).toFixed(2)}% </span>
        </i18n-t>
      </span>
    );

    const dimensionalContentSlot = (item: IAnomalyAnalysis) => {
      return (
        <span class='table-content'>
          {Object.keys(item.dimension_values || {}).map(key => (
            <span
              key={key}
              class='table-content-item'
            >
              <span
                class='item-label'
                v-overflow-tips={{
                  content: key,
                  placement: 'top',
                }}
              >
                {key}
              </span>
              <span
                class='item-value'
                title={(item.dimension_values[key] || []).join('、')}
              >
                {(item.dimension_values[key] || []).join('、')}
              </span>
            </span>
          ))}

          {item.alerts.length > 0 && (
            <div class='dimensional-footer'>
              <i18n-t
                class='dimensional-footer-item'
                keypath='包含 {0} 个告警，来源于以下 {1} 个策略：'
                tag='span'
              >
                <b
                  class='blue-txt'
                  onClick={() => goAlertList(item.alerts)}
                >
                  {item.alert_count}
                </b>
                <span style='font-weight: 700;'> {[Object.values(item.strategy_alerts_mapping || {}).length]} </span>
              </i18n-t>

              {Object.values(item.strategy_alerts_mapping || {}).map((ele: IStrategyMapItem) => (
                <span
                  key={ele.strategy_id}
                  class='dimensional-footer-item'
                  onClick={() => goDetail(ele)}
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

    const renderDisposal = () => {
      return <MarkdownViewer value={contentList?.suggestion} />;
    };

    const renderDimensional = () => {
      const len = contentList?.alerts_analysis?.length;
      return (
        <div>
          <div class='mb-8'>{t('故障关联的告警，统计出最异常的维度（组合）：')}</div>
          {len > 0 && (
            <Collapse
              class='dimensional-collapse inner-collapse'
              v-model={dimensionalActiveIndex.value}
              v-slots={{
                default: item => dimensionalTitleSlot(item),
                content: item => dimensionalContentSlot(item),
              }}
              header-icon='right-shape'
              list={contentList?.alerts_analysis || []}
              accordion
            />
          )}
        </div>
      );
    };

    // 事件分析标题
    const eventTitleSlot = (item: IEventsAnalysis, subContent = null) => {
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
        return (
          <span style={{ fontWeight: '600' }}>
            {`${item.total > 3 ? t('示例事件') : t('事件')} ${subContent.$index + 1}`}
          </span>
        );
      };

      return (
        <span class='event-title'>
          {/* 渲染标题icon */}
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
    const eventContentSlot = (item: IEventsAnalysis) => {
      // 确保当前项的展开状态已初始化
      if (eventChildActiveIndex.value[item.$index] === undefined) {
        eventChildActiveIndex.value[item.$index] = item.contents?.map((_, i) => i) || [];
      }

      return (
        <Collapse
          class='event-collapse inner-collapse'
          v-model={eventChildActiveIndex.value[item.$index]}
          v-slots={{
            default: subContent => eventTitleSlot(item, subContent),
            content: subContent => eventChildContentSlot(item, subContent),
          }}
          header-icon='right-shape'
          list={item.contents || []}
          accordion
        />
      );
    };

    // 事件分析子Collapse内容
    const eventChildContentSlot = (item: IEventsAnalysis, subContent: IEventsContentsData) => (
      <span class='table-content'>
        {Object.entries(item.fields).map(([key, value]) => {
          // tmp告警事件需要特殊处理，event_name已经作为子标题展示
          if (
            (item.type === 'tmp_events' && key === 'event_name') ||
            (['k8s_warning_events', 'alert_system_events'].includes(item.type) &&
              ['event_name', '_sub_unit', '_sub_count'].includes(key))
          )
            return;
          return (
            <span
              key={key}
              class='table-content-item'
            >
              {item.type !== 'tencent_cloud_notice_events' && (
                <span
                  class='item-label'
                  v-overflow-tips={{
                    content: value,
                    placement: 'top',
                  }}
                >
                  {value}
                </span>
              )}
              <span class='item-value'>{subContent[key]}</span>
            </span>
          );
        })}
      </span>
    );

    // 渲染事件分析卡片
    const renderEvent = () => {
      const len = eventsData.value?.length || 0;
      return (
        <>
          <div class='card-summary'>
            <div class='card-summary-title'>{t('事件分析总结：')}</div>
            <MarkdownViewer value={summaryList.events_analysis} />
          </div>
          {len > 0 && (
            <Collapse
              class='event-collapse'
              v-model={eventActiveIndex.value}
              v-slots={{
                default: item => eventTitleSlot(item),
                content: item => eventContentSlot(item),
              }}
              header-icon='right-shape'
              list={eventsData.value}
            />
          )}
        </>
      );
    };

    const handleMouseEnter = async (event: MouseEvent, index: number, type: string) => {
      if (!event.target) return;

      const target = event.currentTarget as HTMLElement;
      if (type === 'demo_log') {
        if (!demoLogOverflowMap[index]) {
          // 首次检查时计算并缓存
          demoLogOverflowMap[index] = checkOverflow(target);
        }
        showDemoLogPop[index] = demoLogOverflowMap[index];
        // 将Pattern项的popover隐藏，避免popover重叠
        showPatternPop[index] = false;
      } else {
        if (!patternOverflowMap[index]) {
          // 首次检查时计算并缓存
          patternOverflowMap[index] = checkOverflow(target);
        }
        showPatternPop[index] = patternOverflowMap[index];
        // 将示例日志项的popover隐藏，避免popover重叠
        showDemoLogPop[index] = false;
      }
    };

    // 响应窗口变化重新计算
    const handleResize = () => {
      for (const key of Object.keys(demoLogOverflowMap)) {
        const index = Number(key);
        const el = document.querySelector(`.log-tips__demo_log[data-index="${index}"]`);
        if (el) demoLogOverflowMap[index] = checkOverflow(el as HTMLElement);
      }

      for (const key of Object.keys(patternOverflowMap)) {
        const index = Number(key);
        const el = document.querySelector(`.log-tips__pattern[data-index="${index}`);
        if (el) patternOverflowMap[index] = checkOverflow(el as HTMLElement);
      }
    };

    onMounted(() => {
      window.addEventListener('resize', handleResize);
    });

    onBeforeUnmount(() => {
      window.removeEventListener('resize', handleResize);
    });

    // 日志分析标题
    const logTitleSlot = (item: ILogAnalysis, itemIndex: number) => (
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

    const renderLogJSONTips = (log: any, isChild = false) => {
      return (
        <>
          <span style='color: #9D694C;'>{'{'}</span>
          {Object.entries(log).map(([key, value]) => (
            <div
              key={key}
              style={{ marginLeft: isChild ? '8px' : '28px' }}
              class='log-popover-content_item'
            >
              <span class='item-label'>"{key}":</span>
              <span class='item-value'>
                {typeof value === 'number'
                  ? value
                  : typeof value === 'object'
                    ? renderLogJSONTips(value, true)
                    : `"${value}"`}
              </span>
            </div>
          ))}
          <span style='color: #9D694C;'>{'}'}</span>
        </>
      );
    };

    // 日志分析内容
    const logContentSlot = (item: ILogAnalysis, index: number) => {
      return (
        <div class='log-content-warpper'>
          <div class='log-content'>
            <div class='log-content-title'>
              <span>Pattern：</span>
              {/* <i class='icon-monitor icon-fenxiang right-icon' /> */}
            </div>
            <Popover
              key={`${index}-pattern`}
              width={560}
              extCls='log-content-tips_popover'
              disabled={!item.pattern}
              isShow={showPatternPop[index]}
              placement='right-start'
              popoverDelay={[500, 0]}
              theme='light'
              trigger='manual'
              onClickoutside={() => {
                showPatternPop[index] = false;
              }}
            >
              {{
                content: () => (
                  <div class='log-popover-content'>
                    <i
                      class={['icon-monitor', 'copy-icon', 'icon-mc-copy']}
                      onClick={handleCopy.bind(this, item.pattern)}
                    />
                    <span class='log-pattern'>{item.pattern}</span>
                  </div>
                ),
                default: () => (
                  <span
                    class='log-tips__default log-tips__pattern'
                    data-index={index}
                    onMouseenter={e => handleMouseEnter(e, index, 'pattern')}
                  >
                    {item.pattern}
                  </span>
                ),
              }}
            </Popover>
          </div>

          <div class='log-content'>
            <div class='log-content-title'>
              <span>{t('示例日志：')}</span>
              {/* <i class='icon-monitor icon-fenxiang right-icon' /> */}
            </div>
            <Popover
              key={`${index}-demo_log`}
              width={560}
              extCls='log-content-tips_popover'
              disabled={!item.demo_log || item.demo_log === '{}'}
              isShow={showDemoLogPop[index]}
              placement='right-start'
              popoverDelay={[500, 0]}
              theme='light'
              trigger='manual'
              onClickoutside={() => {
                showDemoLogPop[index] = false;
              }}
            >
              {{
                content: () => (
                  <div class='log-popover-content'>
                    <i
                      class={['icon-monitor', 'copy-icon', 'icon-mc-copy']}
                      onClick={handleCopy.bind(this, item.demo_log)}
                    />
                    {renderLogJSONTips(JSON.parse(item.demo_log))}
                  </div>
                ),
                default: () => (
                  <span
                    class='log-tips__default log-tips__demo_log'
                    data-index={index}
                    onMouseenter={e => handleMouseEnter(e, index, 'demo_log')}
                  >
                    {item.demo_log}
                  </span>
                ),
              }}
            </Popover>
          </div>
        </div>
      );
    };

    // 渲染日志分析卡片
    const renderLog = () => {
      const len = contentList.logs_analysis ? Object.keys(contentList.logs_analysis).length : 0;
      return (
        <>
          <div class='card-summary'>
            <div class='card-summary-title'>{t('日志分析总结：')}</div>
            <MarkdownViewer value={summaryList.logs_analysis} />
          </div>
          {len > 0 && (
            <Collapse
              class='log-collapse inner-collapse'
              v-model={logActiveIndex.value}
              v-slots={{
                default: (item, index) => logTitleSlot(item, index),
                content: (item, index) => logContentSlot(item, index),
              }}
              header-icon='right-shape'
              list={Object.values(contentList?.logs_analysis)[0] || []}
              accordion
            />
          )}
        </>
      );
    };

    const renderEmpty = (data: IListItem) => (
      <Exception
        class='exception-wrap-item'
        description={data.message}
        scene='part'
        title={t('超时错误')}
        type='500'
      />
    );
    const list = reactive([
      {
        name: t('处置建议'),
        key: 'suggestion',
        icon: 'icon-chulijilu',
        render: renderDisposal,
        id: 'panel-suggestion',
      },
      {
        name: t('告警异常维度分析'),
        key: 'alerts_analysis',
        icon: 'icon-dimension-line',
        render: renderDimensional,
        id: 'panel-alerts_analysis',
      },
      {
        name: t('事件分析'),
        key: 'events_analysis',
        icon: 'icon-shijianjiansuo',
        render: renderEvent,
        id: 'panel-events_analysis',
      },
      {
        name: t('日志分析'),
        key: 'logs_analysis',
        icon: 'icon-a-logrizhi',
        render: renderLog,
        id: 'panel-logs_analysis',
      },
    ]);
    const aiConfig = reactive([
      {
        name: t('故障总结'),
        key: 'summary',
        id: 'panel-summary',
      },
    ]);

    const getIncidentDiagnosis = (key: string) => {
      loadingList[key] = true;
      incidentDiagnosis({
        bk_biz_ids: bkzIds.value,
        id: route.params.id,
        sub_panel: key,
      })
        .then(res => {
          if (key === 'events_analysis') {
            eventsData.value = Object.keys(res.contents).length
              ? Object.entries(res.contents)
                  .map(([key, value]) => {
                    return {
                      type: key,
                      title: res.display?.labels_mapping[key]?.label || '',
                      top: res.display?.labels_mapping[key]?.top || 0,
                      unit: res.display?.labels_mapping[key]?.unit || '',
                      total: res.display?.statistics[key]?.total || 0,
                      contents: (value as IEventsContentsData[]).slice(0, 3), // 只展示前3条
                      fields: res.display?.fields[key] || {},
                    };
                  })
                  .filter(Boolean)
              : [];

            // 事件分析模块第二层Collapse默认展开第一条
            const newIndex: Record<string, number[]> = {};
            eventsData.value.forEach((item, index) => {
              if (item.contents?.length) {
                newIndex[index] = [0];
              }
            });
            eventChildActiveIndex.value = newIndex;
          } else {
            contentList[key] = res.contents || '';
          }
          summaryList[key] = res.individual_summary || '';
          const { sub_panels } = props.panelConfig;
          loadingList[key] = sub_panels[key].status === 'running';
        })
        .catch(() => {
          contentList[key] = '';
          summaryList[key] = '';
          loadingList[key] = false;
        });
    };
    /** 获取tab的展示内容 */
    const getTabContent = () => {
      const { status, sub_panels } = props.panelConfig;
      let keys = Object.keys(sub_panels);
      if (status === 'running') {
        keys = Object.keys(sub_panels || {}).filter(
          key => sub_panels[key].enabled && sub_panels[key].status === 'running'
        );
      }
      keys.map(key => {
        getIncidentDiagnosis(key);
      });
    };
    watch(
      () => bkzIds.value,
      val => {
        val.length > 0 && getTabContent();
      }
    );
    watch(
      () => props.panelConfig,
      () => {
        bkzIds.value.length > 0 && getTabContent();
      },
      { deep: true, immediate: true }
    );

    const handleToPanel = (key: string) => {
      const id = `panel-${key}`;
      setTimeout(() => {
        const el = document.getElementById(id);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    };

    const toggleSlider = (id: string) => {
      curSliderId.value = id;
      showSideSlider.value = true;
    };

    return {
      t,
      list,
      isAllCollapsed,
      contentList,
      aiLoading,
      loadingList,
      renderEmpty,
      showList,
      subPanels,
      aiConfig,
      handleToPanel,
      curSliderId,
      showSideSlider,
      toggleSlider,
    };
  },
  render() {
    const titleSlot = (item: IListItem) => (
      <div
        id={`panel-${item.key}`}
        class='failure-item-title'
      >
        <i class={`icon-monitor ${item.icon} title-icon-circle`} />
        <span class='field-name'>{item.name}</span>
      </div>
    );
    const contentSlot = (item: IListItem) => {
      if (this.subPanels[item.key]?.status === 'failed') {
        return this.renderEmpty(this.subPanels[item.key]);
      }
      return (
        <Loading
          class={{ 'ai-card-loading': this.loadingList[item.key] }}
          loading={this.loadingList[item.key]}
        >
          {!this.loadingList[item.key] && item.render()}
        </Loading>
      );
    };
    const aiCardRender = () => {
      if (this.subPanels.summary.status === 'failed') {
        return this.renderEmpty(this.subPanels.summary);
      }
      return !this.loadingList.summary && <MarkdownViewer value={this.contentList?.summary} />;
    };
    return (
      <>
        <div class='failure-trouble-shooting'>
          <div class='trouble-shooting-header'>
            <Dropdown
              v-slots={{
                default: () => (
                  <span
                    class='collapse-handle-btn'
                    v-bk-tooltips={{
                      content: this.t('快速定位'),
                      placements: ['top'],
                    }}
                  >
                    <i class='icon-monitor icon-a-Contentmulu' />
                  </span>
                ),
                content: () => {
                  return (
                    <Dropdown.DropdownMenu>
                      {[...this.aiConfig, ...this.showList].map(item => (
                        <Dropdown.DropdownItem
                          key={item.key}
                          extCls='text-active'
                          onClick={() => this.handleToPanel(item.key)}
                        >
                          {item.name}
                        </Dropdown.DropdownItem>
                      ))}
                    </Dropdown.DropdownMenu>
                  );
                },
              }}
              popoverOptions={{
                extCls: 'collapse-handle-popover',
                clickContentAutoHide: true,
              }}
              placement='bottom-end'
              trigger='click'
            />
          </div>
          <div class='trouble-shooting-main'>
            {this.subPanels.summary?.enabled && (
              <div
                id='panel-summary'
                class='ai-card'
              >
                <i
                  class='icon-monitor icon-chakan1 slider-icon'
                  v-bk-tooltips={this.t('独立查看')}
                  onClick={() => {
                    this.toggleSlider('panel-summary');
                  }}
                />
                <div class='ai-card-title'>
                  <span class='ai-card-title-icon' />
                  {this.t('故障总结')}
                </div>
                <Loading
                  class={{ 'ai-card-loading': this.loadingList.summary }}
                  color={'#f3f6ff'}
                  loading={this.loadingList.summary}
                >
                  <div class='ai-card-main'>
                    {aiCardRender()}
                    {this.subPanels.summary.status !== 'failed' && <span class='ai-bot-bg' />}
                  </div>
                </Loading>
              </div>
            )}
            {this.showList.length > 0 &&
              this.showList.map(item => {
                return (
                  <div
                    id={item.id}
                    key={item.id}
                    class='failure-item-wrapper'
                  >
                    <i
                      class='icon-monitor icon-chakan1 slider-icon'
                      v-bk-tooltips={this.t('独立查看')}
                      onClick={() => {
                        this.toggleSlider(item.id);
                      }}
                    />
                    {titleSlot(item)}
                    <div class='failure-item-content'>{contentSlot(item)}</div>
                  </div>
                );
              })}
          </div>
        </div>
        <Sideslider
          width={640}
          extCls={'trouble-shooting-slider'}
          isShow={this.showSideSlider}
          quickClose={true}
          onClosed={() => {
            this.showSideSlider = false;
          }}
        >
          {{
            header: () =>
              this.curSliderId === 'panel-summary'
                ? this.aiConfig[0].name
                : this.showList.find(item => item.id === this.curSliderId).name,
            default: () => (
              <div class='trouble-shooting-main trouble-shooting-slider-main'>
                {this.curSliderId === 'panel-summary'
                  ? aiCardRender()
                  : this.showList.map(item => {
                      return (
                        item.id === this.curSliderId && (
                          <div class='failure-item-wrapper'>
                            <div class='failure-item-content'>{contentSlot(item)}</div>
                          </div>
                        )
                      );
                    })}
              </div>
            ),
          }}
        </Sideslider>
      </>
    );
  },
});
