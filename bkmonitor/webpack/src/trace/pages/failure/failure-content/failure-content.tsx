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
import { computed, defineComponent, inject, KeepAlive, Ref, ref, PropType, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import { incidentValidateQueryString } from '../../../../monitor-api/modules/incident';
import AlarmDetail from '../alarm-detail/alarm-detail';
import FilterSearchInput from '../failure-handle/filter-search-input';
import FailureMenu from '../failure-menu/failure-menu';
import FailureTiming from '../failure-timing/failure-timing';
import FailureTopo from '../failure-topo/failure-topo';
import FailureView from '../failure-view/failure-view';
import { IIncident, IAlert, IFilterSearch, IIncidentOperation, IAlertObj } from '../types';
import { useIncidentInject } from '../utils';

import './failure-content.scss';

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
    const active = ref<string>('FailureView');
    const alertIdsObject = ref<IAlertObj>({});
    const playLoading = inject<Ref<boolean>>('playLoading');
    const activeTab = ref<string>('FailureView');
    const incidentId = useIncidentInject();
    const searchValidate = ref<boolean>(true);
    const tabList = [
      {
        name: 'FailureTopo',
        label: t('故障拓扑'),
      },
      {
        name: 'FailureTiming',
        label: t('故障时序'),
      },
      {
        name: 'FailureView',
        label: t('告警'),
      },
    ];
    /** 告警Tab中二级tab列表 */
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
    const chooseOperation = ref<IIncidentOperation>({});
    const currentNodeData = computed(() => {
      return props.currentNode;
    });
    const route = useRoute();
    const router = useRouter();
    const inputStatus = ref<string>('success');

    const handleChangeActive = (activeName: string) => {
      active.value = activeName;
      router.push({ name: 'incident-detail', params: { id: incidentId.value }, query: {} });
    };
    const playingHandle = status => {
      playLoading.value = status;
    };
    /** 跳转到告警明细 */
    const goAlertDetail = (alertObj: IAlertObj) => {
      handleChangeActive('AlarmDetail');
      alertIdsObject.value = alertObj;
    };
    const refresh = () => {
      emit('refresh');
    };
    const goFailureTiming = (id, data) => {
      handleChangeActive('FailureTiming');
      chooseOperation.value = data;
    };
    watch(
      () => route.query,
      val => {
        val.tab && handleChangeActive(val.tab as string);
      },
      { immediate: true }
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
      if (alertIdsObject.value.ids?.length) {
        validate = await incidentValidateQueryString(
          { query_string: replaceSpecialCondition(alertIdsObject.value.ids), search_type: 'incident' },
          { needMessage: false, needRes: true }
        )
          .then(res => res.result)
          .catch(() => false);
      }
      inputStatus.value = !validate ? 'error' : 'success';
      return validate;
    };
    const handleQueryStringChange = async (v: string) => {
      const isChange = v !== alertIdsObject.value.ids;
      if (isChange) {
        alertIdsObject.value.ids = v;
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
        ></FailureMenu>
        <KeepAlive>
          {this.active === 'FailureTopo' && (
            <FailureTopo
              selectNode={this.currentNodeData || []}
              onChangeSelectNode={this.handleChangeSelectNode}
              onPlaying={this.playingHandle}
              onToDetailTab={this.goAlertDetail}
            ></FailureTopo>
          )}
          {this.active === 'FailureTiming' && (
            <FailureTiming
              alertAggregateData={this.$props.alertAggregateData}
              chooseOperation={this.chooseOperation}
              scrollTop={this.$props.scrollTop}
              onGoAlertDetail={this.goAlertDetail}
              onRefresh={this.refresh}
            />
          )}
          {this.active === 'FailureView' && (
            <div class='failure-view-content'>
              <div class='content-head'>
                <div class='head-tab'>
                  {this.tabViewList.map(item => (
                    <span
                      class={['head-tab-item', { active: item.name === this.activeTab }]}
                      onClick={() => {
                        this.activeTab = item.name;
                      }}
                    >
                      <i class={`icon-monitor ${item.icon} item-icon`}></i>
                      {item.label}
                    </span>
                  ))}
                </div>
                <FilterSearchInput
                  // valueMap={this.valueMap}
                  inputStatus={this.inputStatus}
                  searchType='incident'
                  value={this.alertIdsObject.ids}
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
                  ></AlarmDetail>
                )}
              </div>
            </div>
          )}
        </KeepAlive>
      </div>
    );
  },
});
