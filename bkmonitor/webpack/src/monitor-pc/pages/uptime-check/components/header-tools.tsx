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
import { Component, Emit, Inject, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from '../../../../monitor-common/utils/utils';

import './header-tools.scss';

interface IHeaderToolsProps {
  option?: {
    showTask?: boolean;
    showGroup?: boolean;
    showImport?: boolean;
    showNode?: boolean;
  };
  search?: string;
}
interface IHeaderToolsEvents {
  onCreate?: IClickType;
  onSearch?: string;
}

export type IClickType = 'createNode' | 'createTask' | 'createGroup' | 'import';

@Component({
  name: 'HeaderTools'
})
export default class HeaderTools extends tsc<IHeaderToolsProps, IHeaderToolsEvents> {
  @Prop({
    default: () => ({ showTask: true, showGroup: true, showImport: true, showNode: false }),
    type: Object
  })
  option: IHeaderToolsProps['option'];
  @Prop({ default: '', type: String }) search: string;
  // 权限
  @Inject('authority') authority;
  @Inject('authorityMap') authorityMap;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;

  searchValue = '';

  @Watch('search')
  handleSearchWatch(v: string) {
    this.searchValue = v;
  }

  @Emit('create')
  handleCreate(v: IClickType) {
    return v;
  }

  @Debounce(300)
  @Emit('search')
  handleSearch(v: string) {
    return v;
  }

  render() {
    return (
      <div class='uptime-check-header-tools'>
        <div class='left'>
          {this.option.showNode && (
            <bk-button
              class='left-btn'
              theme='primary'
              v-authority={{ active: !this.authority.MANAGE_AUTH }}
              on-click={() =>
                this.authority.MANAGE_AUTH
                  ? this.handleCreate('createNode')
                  : this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH)
              }
            >
              <span class='icon-monitor icon-plus-line mr-6'></span>
              {this.$t('新建节点')}
            </bk-button>
          )}
          {this.option.showTask && (
            <bk-button
              class='left-btn'
              theme='primary'
              v-authority={{ active: !this.authority.MANAGE_AUTH }}
              on-click={() =>
                this.authority.MANAGE_AUTH ? this.handleCreate('createTask') : this.handleShowAuthorityDetail()
              }
            >
              <span class='icon-monitor icon-plus-line mr-6'></span>
              {this.$t('新建拨测')}
            </bk-button>
          )}
          {this.option.showGroup && (
            <bk-button
              class='left-btn'
              v-authority={{ active: !this.authority.MANAGE_AUTH }}
              on-click={() =>
                this.authority.MANAGE_AUTH ? this.handleCreate('createGroup') : this.handleShowAuthorityDetail()
              }
            >
              <span class='icon-monitor icon-plus-line mr-6'></span>
              {this.$t('新建任务组')}
            </bk-button>
          )}
          {this.option.showImport && (
            <bk-button
              class='left-btn'
              v-authority={{ active: !this.authority.MANAGE_AUTH }}
              on-click={() =>
                this.authority.MANAGE_AUTH ? this.handleCreate('import') : this.handleShowAuthorityDetail()
              }
            >
              {this.$t('导入拨测任务')}
            </bk-button>
          )}
        </div>
        <div class='right'>
          <bk-input
            class='search-input'
            placeholder={this.$t('输入')}
            right-icon='bk-icon icon-search'
            v-model={this.searchValue}
            clearable
            on-change={(v: string) => this.handleSearch(v)}
          ></bk-input>
        </div>
      </div>
    );
  }
}
