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

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { SPACE_TYPE_MAP } from '../../../../common/constant';
import { ETagsType } from '../../../../components/biz-select/list';

import './checkbox-list.scss';

interface IProps {
  list: IListItem[];
  checked?: number;
}
interface IEvents {
  onSelected: number;
}
export interface IListItem {
  id: number;
  name: string;
  space_code?: string;
  space_type_id?: string;
  space_id?: string;
  tags?: ItagsItem[];
  children?: IListItem[];
  bk_biz_id?: number;
}
interface ItagsItem {
  id: string;
  name: string;
  type: ETagsType;
}
@Component
export default class List extends tsc<IProps, IEvents> {
  /** 选中的id */
  @Prop({ type: Number }) checked: number;
  /** 列表数据 */
  @Prop({ default: () => [], type: Array }) list: IListItem[];

  selectList = [];

  get isSelectAll() {
    return this.selectList.length === 1 && this.selectList[0] === '*';
  }

  handleCheckBoxChange(id: number) {
    const spliceIndex = this.selectList.findIndex(item => item === id);
    if (spliceIndex >= 0) {
      this.selectList.splice(spliceIndex, 1);
    } else {
      if (this.selectList[0] === '*') this.selectList = [];
      this.selectList.push(id);
    }
  }

  handleSelectAll(status: boolean) {
    this.selectList = status ? ['*'] : [];
  }

  clearSelectList() {
    this.selectList = [];
  }

  render() {
    return (
      <div>
        {!!this.list.length ? (
          this.list.map(item => (
            <div class={['list-group', { 'no-name': !item.name }]}>
              {
                <bk-checkbox
                  checked={this.isSelectAll}
                  ext-cls={'list-item-checkbox'}
                  onChange={(status: boolean) => this.handleSelectAll(status)}
                >
                  <div class={['checkbox-item', { checked: this.selectList.includes('*') }]}>
                    <span class='list-item-left'>{this.$t('全选')}</span>
                  </div>
                </bk-checkbox>
              }
              {item.children.map(child => (
                <bk-checkbox
                  checked={this.selectList.includes(child.bk_biz_id)}
                  ext-cls={'list-item-checkbox'}
                  onChange={() => this.handleCheckBoxChange(child.bk_biz_id)}
                >
                  <div
                    key={child.id}
                    class={['checkbox-item', { checked: this.selectList.includes(child.bk_biz_id) }]}
                  >
                    <span class='list-item-left'>
                      <span
                        class='list-item-name'
                        v-bk-overflow-tips
                      >
                        {child.name}
                      </span>
                      <span
                        class='list-item-id'
                        v-bk-overflow-tips
                      >
                        ({child.space_type_id === ETagsType.BKCC ? `#${child.id}` : child.space_id || child.space_code})
                      </span>
                    </span>
                    <span class='list-item-right'>
                      {child.tags?.map?.(tag => (
                        <span
                          class='list-item-tag'
                          style={{ ...SPACE_TYPE_MAP[tag.id]?.light }}
                        >
                          {tag.name}
                        </span>
                      ))}
                    </span>
                  </div>
                </bk-checkbox>
              ))}
            </div>
          ))
        ) : (
          <bk-exception
            class='no-data'
            type='search-empty'
            scene='part'
          />
        )}
      </div>
    );
  }
}
