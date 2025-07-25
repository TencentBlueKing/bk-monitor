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

import Collapse from '../../../components/collapse/collapse';

import './fav-list.scss';

export interface IFavListItem {
  children?: IFavListItem[];
  expend?: boolean;
  id: number | string;
  name: string;
  uid?: string;
  url?: string;
}
interface IEvents {
  onSelected: IFavListItem;
  onUnstarred: (id: number, name: string) => void;
}
interface IProps {
  checked?: string;
  list: IFavListItem[];
}
@Component
export default class FavList extends tsc<IProps, IEvents> {
  @Prop({ type: Array, default: () => [] }) list: IFavListItem[];
  @Prop({ type: String }) checked: string;
  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('authorityMap') authorityMap;
  localList: IFavListItem[] = [];

  localChecked: string = null;

  @Watch('checked', { immediate: true })
  checkedChange(val: string) {
    this.localChecked = val;
  }

  @Watch('list', { immediate: true })
  listChange(list: IFavListItem[]) {
    this.localList =
      list?.map?.(item => {
        this.$set(item, 'expend', true);
        return item;
      }) || [];
  }

  handleExpend(item: IFavListItem) {
    item.expend = !item.expend;
  }

  @Emit('selected')
  handleSelectItem(item: IFavListItem) {
    this.localChecked = item.uid;
    return item;
  }
  handleUnstarred(item: IFavListItem) {
    this.$emit('unstarred', item.id, item.name);
  }
  render() {
    return (
      <div class='fav-list'>
        {this.list.map((item, index) => (
          <div
            key={index}
            class='fav-list-group'
          >
            <div
              class='fav-list-header'
              onClick={() => this.handleExpend(item)}
            >
              <i class={['icon-monitor icon-mc-triangle-down', { expend: item.expend }]} />
              <span>{item.name}</span>
            </div>
            <Collapse
              expand={item.expend}
              maxHeight={300}
              needCloseButton={false}
            >
              <div class='fav-list-main'>
                {item.children.map(child => (
                  <div
                    key={child.id}
                    class={['fav-item', { checked: this.localChecked === child.uid }]}
                  >
                    <i
                      class='icon-monitor icon-mc-collect'
                      v-bk-tooltips={{
                        content: this.$t('取消收藏'),
                        extCls: 'garfana-link-tips',
                      }}
                      onClick={() => this.handleUnstarred(child)}
                    />
                    <span
                      class='fav-item-name'
                      v-bk-overflow-tips
                      onClick={() => this.handleSelectItem(child)}
                    >
                      {child.name}
                    </span>
                  </div>
                ))}
              </div>
            </Collapse>
          </div>
        ))}
      </div>
    );
  }
}
