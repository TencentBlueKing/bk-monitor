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

import { defineComponent, computed, shallowRef } from 'vue';
import { useI18n } from 'vue-i18n';

import { checkAllowed } from 'monitor-api/modules/iam';
import { random } from 'monitor-common/utils/utils';

import RetrievalFilter from '../../../../components/retrieval-filter/retrieval-filter';
import SpaceSelector from '../../../../components/space-select/space-selector';
import { useAppStore } from '../../../../store/modules/app';
import AlarmModuleSelector from './components/alarm-module-selector';
import SelectorTrigger from './components/selector-trigger';

import type { ITriggerSlotOptions } from '../../../../components/space-select/typing';

import './alarm-retrieval-filter.scss';

export default defineComponent({
  name: 'AlarmRetrievalFilter',
  props: {
    searchType: {
      type: String,
      default: 'alert',
    },
  },
  setup(props) {
    const { t } = useI18n();
    const appStore = useAppStore();
    const bizId = computed(() => {
      return appStore.bizId;
    });
    const isIncident = computed(() => {
      return props.searchType === 'incident';
    });
    const bizList = computed(() => {
      return appStore.bizList;
    });

    const bizIds = shallowRef([]);
    const allowedBizList = shallowRef([]);

    /**
     * @description: 通过业务id 获取无权限申请url
     * @param {string} bizIds 业务id
     * @return {*}
     */
    async function handleCheckAllowedByIds(bizIds?: (number | string)[]) {
      let bizList = bizIds;
      if (!bizIds?.length) {
        bizList = allowedBizList.value.filter(item => item.noAuth).map(item => item.id);
      }
      if (!bizList?.length) return;
      const applyObj = await checkAllowed({
        action_ids: [
          'view_business_v2',
          'manage_event_v2',
          'manage_downtime_v2',
          'view_event_v2',
          'view_host_v2',
          'view_rule_v2',
        ],
        resources: bizList.map(id => ({ id, type: 'space' })),
      });
      if (applyObj?.apply_url) {
        window.open(applyObj?.apply_url, random(10));
      }
    }

    function handleBizIdsChange(v: number[]) {
      bizIds.value = v;
    }

    return {
      bizId,
      isIncident,
      bizIds,
      bizList,
      t,
      handleCheckAllowedByIds,
      handleBizIdsChange,
    };
  },
  render() {
    return (
      <RetrievalFilter class='alarm-center__alarm-retrieval-filter-component'>
        {{
          default: () => (
            <>
              <SpaceSelector
                currentSpace={this.bizId}
                hasAuthApply={true}
                isCommonStyle={false}
                needIncidentOption={this.isIncident}
                spaceList={this.bizList}
                value={this.bizIds}
                onApplyAuth={this.handleCheckAllowedByIds}
                onChange={this.handleBizIdsChange}
              >
                {{
                  trigger: (options: ITriggerSlotOptions) => (
                    <SelectorTrigger
                      tips={options.valueStrList
                        .map(
                          (item, index) =>
                            `${index !== 0 ? `   , ${item.name}` : item.name}${item.id ? `(${item.id})` : ''}`
                        )
                        .join('')}
                      active={options.active}
                      hasRightSplit={true}
                      isError={options.error}
                    >
                      {{
                        top: () => <span>{this.t('空间')}</span>,
                        bottom: () => (
                          <span class='selected-text'>
                            {options.valueStrList.map((item, index) => (
                              <span
                                key={item.id}
                                class='selected-text-item'
                              >
                                {index !== 0 ? `   , ${item.name}` : item.name}
                                {!!item.id && <span class='selected-text-id'>({item.id})</span>}
                              </span>
                            ))}
                          </span>
                        ),
                      }}
                    </SelectorTrigger>
                  ),
                }}
              </SpaceSelector>
              <AlarmModuleSelector />
            </>
          ),
        }}
      </RetrievalFilter>
    );
  },
});
