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

import { bkTooltips, Dropdown, Exception, Loading, Sideslider } from 'bkui-vue';
import { incidentDiagnosis } from 'monitor-api/modules/incident';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import MarkdownViewer from '../../../components/markdown-editor/viewer';
import { checkOverflow } from '../utils';
import { createShootingModule } from './shooting-module';

import type { IncidentDetailData } from '../failure-topo/types';
import type {
  IAlertData,
  IContentList,
  IEventsAnalysis,
  IEventsContentsData,
  IListItem,
  IStrategyMapItem,
  ISummaryList,
  OverflowPopType,
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
      suggestion: false,
      alerts_analysis: false,
      events_analysis: false,
      logs_analysis: false,
    });
    // 当前展开的各模块Collapse索引
    const activeIndex = reactive<{
      dimensional: number[];
      event: number[];
      eventChild: Record<string, number[]>;
      log: number[];
      trace: number[];
    }>({
      dimensional: [0],
      event: [0],
      eventChild: {},
      log: [0],
      trace: [0],
    });
    const bkzIds = inject<Ref<string[]>>('bkzIds');
    const incidentDetail = inject<Ref<IncidentDetailData>>('incidentDetail');
    const incidentDetailData: Ref<IncidentDetailData> = computed(() => {
      return incidentDetail.value;
    });
    // 是否展示详情侧边栏
    const showSideSlider = shallowRef(false);
    // 当前选中的card
    const curSliderId = shallowRef('');
    const MODULE_LIST = [
      {
        name: t('处置建议'),
        key: 'suggestion',
        icon: 'icon-chulijilu',
        id: 'panel-suggestion',
      },
      {
        name: t('告警异常维度分析'),
        key: 'alerts_analysis',
        icon: 'icon-dimension-line',
        id: 'panel-alerts_analysis',
      },
      {
        name: t('事件分析'),
        key: 'events_analysis',
        icon: 'icon-shijianjiansuo',
        id: 'panel-events_analysis',
      },
      {
        name: t('日志分析'),
        key: 'logs_analysis',
        icon: 'icon-a-logrizhi',
        id: 'panel-logs_analysis',
      },
      {
        name: t('Trace 分析'),
        key: 'trace_analysis',
        icon: 'icon-Tracing',
        id: 'panel-trace_analysis',
      },
    ];

    const AI_CONFIG = [
      {
        name: t('故障总结'),
        key: 'summary',
        id: 'panel-summary',
      },
    ];
    // 主内容区的弹窗状态管理
    const popoverState = reactive({
      // 当前显示的弹窗信息
      currentPopover: null as null | { index: number; type: OverflowPopType },
      // 所有项的溢出状态缓存，Record<string, boolean>
      overflowMap: {},
    });
    // 侧边栏的弹窗状态管理
    const sliderPopoverState = reactive({
      currentPopover: null as null | { index: number; type: OverflowPopType },
      overflowMap: {},
    });

    const subPanels = computed(() => props.panelConfig.sub_panels || {});
    const showList = computed(() => MODULE_LIST.filter(item => subPanels.value?.[item.key]?.enabled));

    // 跳转到告警tab带上策路ID过滤
    const goDetail = (data: IStrategyMapItem) => {
      emit('strategy', data);
    };

    // 跳转到告警tab
    const goAlertList = (list: IAlertData[]) => {
      emit('alertList', list);
    };

    // 创建弹窗处理函数工厂
    const createPopoverHandlers = (state: typeof popoverState) => {
      // 处理鼠标进入事件
      const handleMouseEnter = async (event: MouseEvent, index: number, type: OverflowPopType) => {
        if (!event.target) return;
        const target = event.currentTarget as HTMLElement;
        const popoverKey = `${type}_${index}`;

        // 检查是否已缓存溢出状态，如果没有则计算并缓存
        if (state.overflowMap[popoverKey] === undefined) {
          state.overflowMap[popoverKey] = checkOverflow(target);
        }
        // 只有文本溢出时才显示弹窗
        if (state.overflowMap[popoverKey]) {
          state.currentPopover = { type, index };
        }
      };

      // 手动关闭弹窗
      const handlePopoverClose = (item: { isShow: boolean }) => {
        // 只有点击弹窗外区域时才关闭弹窗
        if (!item.isShow) return;

        state.currentPopover = null;
      };

      // 响应窗口变化重新计算文本是否溢出
      const handleResize = () => {
        // 重新计算所有已缓存项的溢出状态
        for (const key of Object.keys(state.overflowMap)) {
          const [type, indexStr] = key.split('_');
          const index = Number(indexStr);
          const selectorMap = {
            demo_log: `.log-tips__demo_log[data-index="${index}"]`,
            log_pattern: `.log-tips__pattern[data-index="${index}"]`,
            trace_pattern: `.trace-tips__pattern[data-index="${index}"]`,
          };

          const selector = selectorMap[type];
          if (selector) {
            const el = document.querySelector(selector);
            if (el) {
              state.overflowMap[key] = checkOverflow(el as HTMLElement);
            }
          }
        }
      };

      return {
        handleMouseEnter,
        handlePopoverClose,
        handleResize,
      };
    };

    // 主内容区弹窗处理
    const mainPopoverHandlers = createPopoverHandlers(popoverState);
    // 侧边栏弹窗处理
    const sliderPopoverHandlers = createPopoverHandlers(sliderPopoverState);

    // 响应窗口变化重新计算文本是否溢出（只主内容区需要）
    const handleResize = () => {
      mainPopoverHandlers.handleResize();
    };

    onMounted(() => {
      window.addEventListener('resize', handleResize);
    });

    onBeforeUnmount(() => {
      window.removeEventListener('resize', handleResize);
    });

    const renderEmpty = (data: IListItem) => (
      <Exception
        class='exception-wrap-item'
        description={data.message}
        scene='part'
        title={t('查询异常')}
        type='500'
      />
    );

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
            for (const [index, item] of eventsData.value.entries()) {
              if (item.contents?.length) {
                newIndex[index] = [0];
              }
            }
            activeIndex.eventChild = newIndex;
          } else if (key === 'trace_analysis') {
            contentList[key] = res.contents.trace_messages_analysis || [];
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

    // 获取tab的展示内容
    const getTabContent = () => {
      const { status, sub_panels } = props.panelConfig;
      let keys = Object.keys(sub_panels);
      if (status === 'running') {
        keys = Object.keys(sub_panels || {}).filter(
          key => sub_panels[key].enabled && sub_panels[key].status === 'running'
        );
      }
      for (const key of keys) {
        getIncidentDiagnosis(key);
      }
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
      bkzIds,
      incidentDetailData,
      isAllCollapsed,
      contentList,
      eventsData,
      summaryList,
      loadingList,
      showList,
      subPanels,
      AI_CONFIG,
      renderEmpty,
      handleToPanel,
      toggleSlider,
      curSliderId,
      showSideSlider,
      popoverState,
      sliderPopoverState,
      activeIndex,
      goAlertList,
      goDetail,
      handleMouseEnter: mainPopoverHandlers.handleMouseEnter,
      handlePopoverClose: mainPopoverHandlers.handlePopoverClose,
      handleSliderMouseEnter: sliderPopoverHandlers.handleMouseEnter,
      handleSliderPopoverClose: sliderPopoverHandlers.handlePopoverClose,
    };
  },
  render() {
    // 公共的故障诊断模块配置
    const getShootingModuleConfig = (type: 'main' | 'slider') => ({
      bkzIds: this.bkzIds,
      incidentDetailData: this.incidentDetailData,
      contentList: this.contentList,
      eventsData: this.eventsData,
      summaryList: this.summaryList,
      activeIndex: this.activeIndex,
      popoverState: type === 'main' ? this.popoverState : this.sliderPopoverState,
      handleMouseEnter: type === 'main' ? this.handleMouseEnter : this.handleSliderMouseEnter,
      handlePopoverClose: type === 'main' ? this.handlePopoverClose : this.handleSliderPopoverClose,
      goAlertList: this.goAlertList,
      goDetail: this.goDetail,
    });

    // 缓存主内容区和侧边栏的shooting modules
    const [mainShootingModule, sliderShootingModule] = ['main', 'slider'].map(type =>
      createShootingModule(getShootingModuleConfig(type as 'main' | 'slider'), this.t)
    );

    // 统一的title slot渲染
    const titleSlot = (item: IListItem) => (
      <div
        id={`panel-${item.key}`}
        class='failure-item-title'
      >
        <i class={`icon-monitor ${item.icon} title-icon-circle`} />
        <span class='field-name'>{item.name}</span>
      </div>
    );

    // 统一的content slot渲染
    const contentSlot = (item: IListItem, shootingModule: any) => {
      if (this.subPanels[item.key]?.status === 'failed') {
        return this.renderEmpty(this.subPanels[item.key]);
      }

      return (
        <Loading
          class={{ 'ai-card-loading': this.loadingList[item.key] }}
          loading={this.loadingList[item.key]}
        >
          {!this.loadingList[item.key] && shootingModule?.slots?.[item.key]?.()}
        </Loading>
      );
    };

    // AI卡片渲染逻辑
    const renderAICard = () => {
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
                      {[...this.AI_CONFIG, ...this.showList].map(item => (
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
            {/* AI故障总结卡片 */}
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
                    {renderAICard()}
                    {this.subPanels.summary.status !== 'failed' && <span class='ai-bot-bg' />}
                  </div>
                </Loading>
              </div>
            )}
            {/* 其他各模块卡片 */}
            {this.showList.length > 0 &&
              this.showList.map(item => {
                return (
                  <div
                    id={item.id}
                    key={item.id}
                    class='failure-item-wrapper'
                  >
                    {this.subPanels[item.key]?.status !== 'failed' && (
                      <i
                        class='icon-monitor icon-chakan1 slider-icon'
                        v-bk-tooltips={this.t('独立查看')}
                        onClick={() => {
                          this.toggleSlider(item.id);
                        }}
                      />
                    )}
                    {titleSlot(item)}
                    <div class='failure-item-content'>{contentSlot(item, mainShootingModule)}</div>
                  </div>
                );
              })}
          </div>
        </div>

        {/* 侧边栏 */}
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
                ? this.AI_CONFIG[0].name
                : this.showList.find(item => item.id === this.curSliderId).name,
            default: () => (
              <div class='trouble-shooting-main trouble-shooting-slider-main'>
                {this.curSliderId === 'panel-summary'
                  ? renderAICard()
                  : this.showList
                      .filter(item => item.id === this.curSliderId)
                      .map(item => (
                        <div
                          key={item.id}
                          class='failure-item-wrapper'
                        >
                          <div class='failure-item-content'>{contentSlot(item, sliderShootingModule)}</div>
                        </div>
                      ))}
              </div>
            ),
          }}
        </Sideslider>
      </>
    );
  },
});
