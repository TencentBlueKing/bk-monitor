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
import { defineComponent, type PropType, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import { type ITagInfoType, type IUserName } from '../types';
import HandleSearch from './handle-search';
import HandlerList from './handler-list';

import './failure-handle.scss';

export default defineComponent({
  name: 'FailureHandle',
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
  emits: ['nodeClick', 'filterSearch', 'nodeExpand', 'treeScroll'],
  setup() {
    const { t } = useI18n();
    const handleSearchRef = ref(null);
    const username = ref<IUserName>({
      id: 'admin',
      name: t('我负责'),
    });

    const refreshTree = () => {
      handleSearchRef.value?.handleFilter();
    };

    return {
      handleSearchRef,
      username,
      refreshTree,
      getIUserName: (item: IUserName) => (username.value = item),
    };
  },
  render() {
    return (
      <div class='failure-handle'>
        <HandlerList onClick={this.getIUserName} />
        <HandleSearch
          ref='handleSearchRef'
          tagInfo={this.$props.tagInfo}
          topoNodeId={this.$props.topoNodeId}
          username={this.username}
          onFilterSearch={(data: any) => this.$emit('filterSearch', data)}
          onNodeClick={(item: any) => this.$emit('nodeClick', item)}
          onNodeExpand={(data: any) => this.$emit('nodeExpand', data)}
          onTreeScroll={(scrollTop: any) => this.$emit('treeScroll', scrollTop)}
        />
      </div>
    );
  },
});
