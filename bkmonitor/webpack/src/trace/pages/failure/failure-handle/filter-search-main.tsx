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
import { computed, defineComponent, inject, Ref, ref, watch, PropType } from 'vue';
import { TranslateResult, useI18n } from 'vue-i18n';

import { Select, Tag } from 'bkui-vue';

import { SPACE_TYPE_MAP } from '../../common/constant';
import { IIncident } from '../types';
import FilterSearchInput from './filter-search-input';
import { incidentValidateQueryString } from '../../../../monitor-api/modules/incident';

import './filter-search-main.scss';

export enum ETagsType {
  BCS = 'bcs' /** 容器项目 */,
  BKCC = 'bkcc' /** 业务 */,
  BKCI = 'bkci' /** 蓝盾项目 */,
  BKSAAS = 'bksaas' /** 蓝鲸应用 */,
  MONITOR = 'monitor' /** 监控空间 */,
}
export type AnlyzeField =
  | 'alert_name'
  | 'assignee'
  | 'bk_cloud_id'
  | 'bk_service_instance_id'
  | 'duration'
  | 'ip'
  | 'ipv6'
  | 'metric'
  | 'strategy_id';
export interface ICommonItem {
  id: string;
  name: TranslateResult | string;
}
interface TagInfoType {
  bk_biz_id: number;
  bk_biz_name: string;
  isCheck: boolean;
}

export default defineComponent({
  name: 'FilterSearchMain',
  props: {
    tagInfo: {
      type: Object as PropType<TagInfoType>,
      default: () => ({}),
    },
  },
  emits: ['search', 'changeSpace'],
  setup(props, { emit }) {
    const incidentDetail = inject<Ref<IIncident>>('incidentDetail');
    const { t } = useI18n();
    const spaceFilter = ref<number[]>([]);
    const searchType = ref('incident');
    const queryString = ref('');
    const spaceData = ref(null);
    const valueMap = ref<Record<Partial<AnlyzeField>, ICommonItem[]> | null>(null);
    const tagInfoData = computed(() => {
      return props.tagInfo || [];
    });
    const inputStatus = ref<string>('success');
    const handleBiz = (data: any) => {
      const list = JSON.parse(JSON.stringify(spaceFilter.value));
      spaceFilter.value.push(data.bk_biz_id);
      spaceFilter.value = [...new Set(spaceFilter.value)];
      if (!list.includes(data.bk_biz_id)) {
        emit('changeSpace', spaceFilter.value);
      }
    };
    watch(
      () => tagInfoData.value,
      () => {
        handleBiz(tagInfoData.value);
      }
    );
    const currentBizList = computed(() => {
      const { current_snapshot } = incidentDetail.value;
      return current_snapshot?.bk_biz_id || [];
    });
    const spaceDataList = computed(() => {
      const list = (window.space_list || []).filter(item => currentBizList.value.includes(item.bk_biz_id));
      return getSpaceList(list || []);
    });
    const changeSpace = (space: string) => {
      emit('changeSpace', space);
    };
    /* 整理space_list */
    const getSpaceList = spaceList => {
      const list = [];
      spaceList.forEach(item => {
        const tags = [{ id: item.space_type_id, name: item.type_name, type: item.space_type_id }];
        if (item.space_type_id === 'bkci' && item.space_code) {
          tags.push({ id: 'bcs', name: t('容器项目'), type: 'bcs' });
        }
        const newItem = {
          ...item,
          name: item.space_name.replace(/\[.*?\]/, ''),
          tags,
          isCheck: false,
          show: true,
        };
        list.push(newItem);
      });
      return list;
    };
    /**
     * @description: 查询条件变更时触发搜索
     * @param {string} v 查询语句
     * @return {*}
     */
    const handleQueryStringChange = async (v: string) => {
      const isChange = v !== queryString.value;
      if (isChange) {
        queryString.value = v;
        const validate = await handleValidateQueryString();
        emit('search', queryString.value, validate);
      }
    };
    const replaceSpecialCondition = (qs: string) => {
      // 由于验证 queryString 不允许使用单引号，为提升体验，这里单双引号的空串都会进行替换。
      const regExp = new RegExp(`${t('通知人')}\\s*:\\s*(""|'')`, 'gi');
      return qs.replace(regExp, `NOT ${t('通知人')} : *`);
    }
    const handleValidateQueryString = async () => {
      let validate = true;
      if (queryString.value?.length) {
        validate = await incidentValidateQueryString(
          { query_string: replaceSpecialCondition(queryString.value), search_type: searchType.value },
          { needMessage: false, needRes: true }
        )
          .then(res => res.result)
          .catch(() => false);
      }
      inputStatus.value = !validate ? 'error' : 'success';
      return validate;
    }
    return {
      t,
      handleQueryStringChange,
      spaceFilter,
      changeSpace,
      searchType,
      queryString,
      spaceData,
      valueMap,
      spaceDataList,
      inputStatus,
    };
  },
  render() {
    return (
      <div class='failure-search-main'>
        <div class='main-top'>
          <Select
            selected-style='checkbox'
            class='main-select'
            v-model={this.spaceFilter}
            inputSearch={false}
            prefix={this.t('空间筛选')}
            filterable
            multiple
            onChange={this.changeSpace}
          >
            {this.spaceDataList.map((item, ind) => (
              <Select.Option
                id={item.id}
                key={ind}
                class='main-select-item'
                name={item.name}
              >
                <span class='item-name'>
                  <span class={['name', { disabled: !!item.noAuth && !item.hasData }]}>{item.name}</span>
                </span>
                <div class='space-tags'>
                  {item.tags.map(tag =>
                    SPACE_TYPE_MAP[tag.id]?.name ? (
                      <Tag
                        style={{ ...SPACE_TYPE_MAP[tag.id]?.light }}
                        class='space-tags-item'
                      >
                        {SPACE_TYPE_MAP[tag.id]?.name}
                      </Tag>
                    ) : (
                      ''
                    )
                  )}
                </div>
              </Select.Option>
            ))}
          </Select>
        </div>
        <div class='main-bot'>
          <FilterSearchInput
            searchType={this.searchType}
            value={this.queryString}
            valueMap={this.valueMap}
            inputStatus={this.inputStatus}
            onChange={this.handleQueryStringChange}
            onClear={this.handleQueryStringChange}
          />
        </div>
      </div>
    );
  },
});
