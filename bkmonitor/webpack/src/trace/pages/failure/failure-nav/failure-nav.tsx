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
import { KeepAlive, type PropType, type Ref, defineComponent, inject, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import { incidentAlertAggregate } from 'monitor-api/modules/incident';

import FailureHandle from '../failure-handle/failure-handle';
import FailureMenu from '../failure-menu/failure-menu';
import FailureProcess from '../failure-process/failure-process';

import type { ITagInfoType, IAggregationRoot } from '../types';

import './failure-nav.scss';

export default defineComponent({
  name: 'FailureNav',
  props: {
    tagInfo: {
      type: Object as PropType<ITagInfoType>,
      default: () => ({}),
    },
    topoNodeId: {
      type: String,
      default: '',
    },
  },
  emits: ['nodeClick', 'filterSearch', 'nodeExpand', 'treeScroll', 'chooseOperation', 'changeSpace', 'changeTab'],
  setup(props, { emit }) {
    /** 左侧头部菜单 */
    const { t } = useI18n();
    const playLoading = inject<Ref<boolean>>('playLoading');
    const alertAggregateParams = ref({});
    const refNav = ref(null);
    const tabList = [
      {
        name: 'FailureHandle',
        label: t('故障处理'),
      },
      {
        name: 'FailureProcess',
        label: t('故障流转'),
      },
    ];
    const active = ref('FailureHandle');
    const handleChange = (name: string) => {
      if (active.value !== name) {
        active.value = name;
      }
    };
    const nodeClick = item => {
      emit('nodeClick', item);
    };
    const filterSearch = data => {
      alertAggregateParams.value = data;
      emit('filterSearch', data);
    };
    const nodeExpand = data => {
      emit('nodeExpand', data);
    };
    const treeScroll = scrollTop => {
      emit('treeScroll', scrollTop);
    };

    const chooseOperation = (id: string, data: any) => {
      emit('chooseOperation', id, data);
    };
    const handleIsRoot = data => {
      return data.map(item => {
        item.isOpen = item.is_root || item.is_feedback_root;
        if (item.children) {
          handleIsRoot(item.children);
        }
        return item;
      });
    };
    const handleRefNavRefresh = () => {
      if (active.value === 'FailureHandle') {
        refNav.value?.refreshTree();
      } else {
        incidentAlertAggregate(alertAggregateParams.value)
          .then(res => {
            const list: IAggregationRoot[] = Object.values(res);
            const data = list.filter(item => item.count !== 0);
            const isHasRoot = data.findIndex(item => item.is_root || item.is_feedback_root) !== -1;
            const isHasChildInd = data.findIndex(item => item.children?.length);
            if (data.length !== 0) {
              if (isHasRoot) {
                handleIsRoot(data);
              } else {
                data[isHasChildInd].isOpen = true;
              }
            }
            emit('nodeExpand', data);
          })
          .catch(err => {
            console.log(err);
          });
      }
    };

    const handleSpace = (value: string[]) => {
      emit('changeSpace', value);
    };
    const changeTab = () => {
      emit('changeTab');
    };
    return {
      active,
      tabList,
      handleChange,
      handleSpace,
      nodeClick,
      filterSearch,
      nodeExpand,
      treeScroll,
      playLoading,
      chooseOperation,
      refNav,
      handleRefNavRefresh,
      changeTab,
    };
  },
  render() {
    const Component = this.active === 'FailureHandle' ? FailureHandle : FailureProcess;
    return (
      <div class='failure-nav'>
        {this.playLoading && <div class='failure-nav-loading' />}
        <FailureMenu
          width={'500px'}
          active={this.active}
          tabList={this.tabList}
          top={-16}
          onChange={this.handleChange}
        />
        <div class='failure-nav-main'>
          <KeepAlive>
            <Component
              ref='refNav'
              tagInfo={this.$props.tagInfo}
              topoNodeId={this.$props.topoNodeId}
              onChangeSpace={this.handleSpace}
              onChangeTab={this.changeTab}
              onChooseOperation={this.chooseOperation}
              onFilterSearch={this.filterSearch}
              onNodeClick={this.nodeClick}
              onNodeExpand={this.nodeExpand}
              onTreeScroll={this.treeScroll}
            />
          </KeepAlive>
        </div>
      </div>
    );
  },
});
