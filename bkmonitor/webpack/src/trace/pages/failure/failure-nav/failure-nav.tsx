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
import { defineComponent, inject, KeepAlive, Ref, ref, PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import FailureHandle from '../failure-handle/failure-handle';
import FailureMenu from '../failure-menu/failure-menu';
import FailureProcess from '../failure-process/failure-process';
import { ITagInfoType } from '../types';
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
  emits: ['nodeClick', 'filterSearch', 'nodeExpand', 'treeScroll', 'chooseOperation'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const playLoading = inject<Ref<boolean>>('playLoading');
    const refNav = ref<HTMLDivElement>();
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

    const handleRefNavRefresh = () => {
      active.value === 'FailureHandle' && refNav.value?.refreshTree();
    };

    return {
      active,
      tabList,
      handleChange,
      nodeClick,
      filterSearch,
      nodeExpand,
      treeScroll,
      playLoading,
      chooseOperation,
      refNav,
      handleRefNavRefresh,
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
        ></FailureMenu>
        <div class='failure-nav-main'>
          <KeepAlive>
            <Component
              ref='refNav'
              tagInfo={this.$props.tagInfo}
              topoNodeId={this.$props.topoNodeId}
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
