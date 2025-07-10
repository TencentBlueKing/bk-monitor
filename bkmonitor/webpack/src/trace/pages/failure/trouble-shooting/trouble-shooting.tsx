/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
import { computed, defineComponent, shallowRef, watch, reactive, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import { Collapse, Exception, Loading, Dropdown } from 'bkui-vue';
import { incidentDiagnosis } from 'monitor-api/modules/incident';

import MarkdownViewer from '../../../components/markdown-editor/viewer';

import type { IContentList, IListItem, IAlertData, IAnomalyAnalysis } from '../types';

import './trouble-shooting.scss';

export default defineComponent({
  name: 'TroubleShooting',
  props: {
    panelConfig: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['alertList'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const route = useRoute();
    const isAllCollapsed = shallowRef(true);
    const contentList: IContentList = reactive({});
    const loadingList = reactive({
      summary: false,
    });
    const activeIndex = shallowRef([]);
    const childActiveIndex = shallowRef([0]);
    const subPanels = computed(() => {
      return props.panelConfig.sub_panels || {};
    });
    const aiLoading = computed(() => {
      return subPanels.value?.summary?.status;
    });

    const showList = computed(() => {
      return list.filter(item => subPanels.value?.[item.key]?.enabled);
    });

    const dimensionalTitleSlot = (item: IAnomalyAnalysis) => (
      <span class='dimensional-title'>
        {item.name || `异常维度（组合）${item.$index + 1}`}
        <span class='red-font'>
          {t('可疑程度')} {(item?.score || 0).toFixed(2) * 100}%
        </span>
      </span>
    );
    /** 侧滑展开告警详情 */
    const goDetail = (data: IAlertData) => {
      window.__BK_WEWEB_DATA__?.showDetailSlider?.(data);
    };
    /** 跳转到告警tab */
    const goAlertList = (list: IAlertData[]) => {
      emit('alertList', list);
    };
    const dimensionalContentSlot = (item: IAnomalyAnalysis) => {
      return (
        <span class='dimensional-content'>
          {Object.keys(item.dimension_values || {}).map(key => (
            <span
              key={key}
              class='dimensional-content-item'
            >
              <span
                class='item-label'
                title={key}
              >
                {key}：
              </span>
              <span
                class='item-value'
                title={(item.dimension_values[key] || []).join('、')}
              >
                {(item.dimension_values[key] || []).join('、')}
              </span>
            </span>
          ))}
          <span class='content-title'>
            {t('包含')}
            <b
              class='blue-txt'
              onClick={() => goAlertList(item.alerts)}
            >
              {item.alert_count}
            </b>
            {t('个告警')}
          </span>
          {(item.alerts || []).map((ele: IAlertData) => (
            <span
              key={ele.id}
              class='dimensional-content-link'
              onClick={() => goDetail(ele)}
            >
              <span class='blue-txt'>{ele.alert_name}</span>
            </span>
          ))}
        </span>
      );
    };

    const renderDisposal = () => {
      return <MarkdownViewer value={contentList?.suggestion} />;
    };

    const renderDimensional = () => {
      const len = contentList?.anomaly_analysis?.length;
      return (
        <div>
          <span>{t('故障关联的告警，统计出最异常的维度（组合）：')}</span>
          {len > 0 && (
            <Collapse
              class='dimensional-collapse'
              v-model={childActiveIndex.value}
              v-slots={{
                default: item => dimensionalTitleSlot(item),
                content: item => dimensionalContentSlot(item),
              }}
              list={contentList?.anomaly_analysis || []}
            />
          )}
        </div>
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
        key: 'anomaly_analysis',
        icon: 'icon-dimension-line',
        render: renderDimensional,
        id: 'panel-anomaly_analysis',
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
        id: route.params.id,
        sub_panel: key,
      }).then(res => {
        contentList[key] = res.contents;
        const { sub_panels } = props.panelConfig;
        loadingList[key] = sub_panels[key].status === 'running';
      });
    };
    watch(
      () => props.panelConfig,
      val => {
        const { status, sub_panels } = val;
        let keys = Object.keys(sub_panels);
        if (status === 'running') {
          keys = Object.keys(sub_panels || {}).filter(
            key => sub_panels[key].enabled && sub_panels[key].status === 'running'
          );
        }
        keys.map(key => {
          getIncidentDiagnosis(key);
        });
      },
      { deep: true, immediate: true }
    );
    const handleToPanel = (key: string) => {
      const id = `panel-${key}`;
      if (key !== 'summary') {
        const idx = list.findIndex(item => item.key === key);
        if (idx > -1 && !activeIndex.value.includes(idx)) {
          activeIndex.value = [...activeIndex.value, idx];
        }
      }
      setTimeout(() => {
        const el = document.getElementById(id);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    };
    onMounted(() => {
      activeIndex.value = list.map((_, idx) => idx);
    });

    return {
      t,
      activeIndex,
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
    };
  },
  render() {
    const titleSlot = (item: IListItem) => (
      <span
        id={`panel-${item.key}`}
        class='collapse-item-title'
      >
        <i class={`icon-monitor ${item.icon} title-icon-circle`} />
        <span class='field-name'>{item.name}</span>
      </span>
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
          <Collapse
            class='failure-collapse'
            v-model={this.activeIndex}
            v-slots={{
              default: item => titleSlot(item),
              content: item => contentSlot(item),
            }}
            header-icon='right-shape'
            list={this.showList}
          />
        </div>
      </div>
    );
  },
});
