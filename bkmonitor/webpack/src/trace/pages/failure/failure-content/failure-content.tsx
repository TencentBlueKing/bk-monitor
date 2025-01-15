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
import { KeepAlive, type PropType, type Ref, computed, defineComponent, inject, ref, watch, nextTick, provide } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import { incidentValidateQueryString } from 'monitor-api/modules/incident';

import AlarmDetail from '../alarm-detail/alarm-detail';
import FilterSearchInput from '../failure-handle/filter-search-input';
import FailureMenu from '../failure-menu/failure-menu';
import FailureTiming from '../failure-timing/failure-timing';
import FailureTopo from '../failure-topo/failure-topo';
import FailureView from '../failure-view/failure-view';

import type { IAlert, IAlertObj, IFilterSearch, IIncident, IIncidentOperation } from '../types';

import './failure-content.scss';

/**
 * @enum {'FailureTiming' | 'FailureTopo' | 'FailureView'}
 * @description 一级 Tabs 常量，用于故障详情页面的不同视图切换
 *  */
enum FailureContentTabView {
  /**
   * @description 一级Tabs - 故障时序，展示故障发生的时间序列信息
   *  */
  FAILURE_TIMING = 'FailureTiming',
  /**
   *  @description 一级Tabs - 故障拓扑，展示故障相关的系统或网络拓扑信息
   * */
  FAILURE_TOPO = 'FailureTopo',
  /**
   *  @description 一级Tabs - 告警，展示与故障相关的告警信息
   * */
  FAILURE_VIEW = 'FailureView',
}

export default defineComponent({
  name: 'FailureContent',
  props: {
    incidentDetail: {
      type: Object as () => IIncident,
      default: () => ({}),
    },
    currentNode: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    filterSearch: {
      type: Object as () => IFilterSearch,
      default: () => ({}),
    },
    alertAggregateData: {
      type: Array as PropType<IAlert[]>,
      default: () => [],
    },
    scrollTop: {
      type: Number,
      default: 0,
    },
  },
  emits: ['refresh', 'changeSelectNode'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const active = ref<string>(FailureContentTabView.FAILURE_TOPO);
    const alertIdsObject = ref<IAlertObj | string>();
    const playLoading = inject<Ref<boolean>>('playLoading');
    const activeTab = ref<string>('FailureView');
    provide('activeName', active);
    const searchValidate = ref<boolean>(true);
    const tabList = [
      {
        name: FailureContentTabView.FAILURE_TOPO,
        label: t('故障拓扑'),
      },
      {
        name: FailureContentTabView.FAILURE_TIMING,
        label: t('故障时序'),
      },
      {
        name: FailureContentTabView.FAILURE_VIEW,
        label: t('告警'),
      },
    ];
    /** 告警Tab中二级tab列表  */
    const tabViewList = [
      {
        name: 'FailureView',
        label: t('视图'),
        icon: 'icon-mc-two-column',
      },
      {
        name: 'AlarmDetail',
        label: t('明细'),
        icon: 'icon-mc-list',
      },
    ];
    const chooseOperation = ref<IIncidentOperation | any>();
    const currentNodeData = computed(() => {
      return props.currentNode;
    });
    const inputStatus = ref<string>('success');

    const handleChangeActive = (activeName: string) => {
      active.value = activeName;
      alertIdsObject.value = {};
    };
    const playingHandle = status => {
      playLoading.value = status;
    };

    /** 跳转到告警明细 */
    const goAlertDetail = (alertObj: IAlertObj) => {
      handleChangeActive(FailureContentTabView.FAILURE_VIEW);
      activeTab.value = 'AlarmDetail';
      alertIdsObject.value = alertObj;
    };
    const refresh = () => {
      emit('refresh');
    };
    const goFailureTiming = (id, data) => {
      chooseOperation.value = {};
      handleChangeActive(FailureContentTabView.FAILURE_TIMING);
      nextTick(() => {
        chooseOperation.value = data;
      });
    };

    watch(
      () => currentNodeData.value,
      () => {
        handleChangeActive(FailureContentTabView.FAILURE_TOPO);
      }
    );
    const handleChangeSelectNode = (nodeId: string) => {
      emit('changeSelectNode', nodeId);
    };
    const replaceSpecialCondition = (qs: string) => {
      // 由于验证 queryString 不允许使用单引号，为提升体验，这里单双引号的空串都会进行替换。
      const regExp = new RegExp(`${t('通知人')}\\s*:\\s*(""|'')`, 'gi');
      return qs.replace(regExp, `NOT ${t('通知人')} : *`);
    };
    const handleValidateQueryString = async () => {
      let validate = true;
      if (alertIdsObject.value?.ids?.length) {
        validate = await incidentValidateQueryString(
          { query_string: replaceSpecialCondition(alertIdsObject.value?.ids), search_type: 'incident' },
          { needMessage: false, needRes: true }
        )
          .then(res => res.result)
          .catch(() => false);
      }
      inputStatus.value = !validate ? 'error' : 'success';
      return validate;
    };
    const handleQueryStringChange = async (v: string) => {
      const isChange = alertIdsObject.value?.ids ? v !== alertIdsObject.value.ids : true;
      if (isChange) {
        alertIdsObject.value = v;
        searchValidate.value = await handleValidateQueryString();
      }
    };
    return {
      tabList,
      active,
      handleChangeActive,
      currentNodeData,
      playingHandle,
      goAlertDetail,
      alertIdsObject,
      refresh,
      goFailureTiming,
      chooseOperation,
      activeTab,
      tabViewList,
      handleChangeSelectNode,
      handleQueryStringChange,
      inputStatus,
      searchValidate,
    };
  },
  render() {
    return (
      <div class='failure-content'>
        <FailureMenu
          width={'calc(100vw - 500px)'}
          active={this.active}
          tabList={this.tabList}
          onChange={this.handleChangeActive}
        />
        <KeepAlive>
          {this.active === FailureContentTabView.FAILURE_TOPO && (
            <FailureTopo
              selectNode={this.currentNodeData || []}
              onChangeSelectNode={this.handleChangeSelectNode}
              onPlaying={this.playingHandle}
              onRefresh={this.refresh}
              onToDetailTab={this.goAlertDetail}
            />
          )}
          {this.active === FailureContentTabView.FAILURE_TIMING && (
            <FailureTiming
              alertAggregateData={this.$props.alertAggregateData}
              chooseOperation={this.chooseOperation}
              scrollTop={this.$props.scrollTop}
              onGoAlertDetail={this.goAlertDetail}
              onRefresh={this.refresh}
              onChangeTab={this.goAlertDetail}
            />
          )}
          {this.active === FailureContentTabView.FAILURE_VIEW && (
            <div class='failure-view-content'>
              <div class='content-head'>
                <div class='head-tab'>
                  {this.tabViewList.map(item => (
                    <span
                      key={item.name}
                      class={['head-tab-item', { active: item.name === this.activeTab }]}
                      onClick={() => {
                        this.activeTab = item.name;
                      }}
                    >
                      <i class={`icon-monitor ${item.icon} item-icon`} />
                      {item.label}
                    </span>
                  ))}
                </div>

                <FilterSearchInput
                  inputStatus={this.inputStatus}
                  searchType='incident'
                  value={this.alertIdsObject?.ids}
                  onChange={this.handleQueryStringChange}
                  onClear={this.handleQueryStringChange}
                />
              </div>
              <div class='content-main'>
                {this.activeTab === 'FailureView' ? (
                  <FailureView
                    alertIdsObject={this.alertIdsObject}
                    searchValidate={this.searchValidate}
                    onRefresh={this.refresh}
                  />
                ) : (
                  <AlarmDetail
                    alertIdsObject={this.alertIdsObject}
                    filterSearch={this.$props.filterSearch}
                    searchValidate={this.searchValidate}
                    onRefresh={this.refresh}
                  />
                )}
              </div>
            </div>
          )}
        </KeepAlive>
      </div>
    );
  },
});
