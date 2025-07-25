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
import { Component, Emit, Mixins, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { SPACE_TYPE_MAP } from '../../common/constant';
import UserConfigMixin from '../../mixins/userStoreConfig';
import store from '../../store/store';

import type { ThemeType } from './biz-select';

import './list.scss';

export enum ETagsType {
  BCS = 'bcs' /** 容器项目 */,
  BKCC = 'bkcc' /** 业务 */,
  BKCI = 'bkci' /** 蓝盾项目 */,
  BKSAAS = 'bksaas' /** 蓝鲸应用 */,
  MONITOR = 'monitor' /** 监控空间 */,
}
export interface IListItem {
  children?: IListItem[];
  id: number | string;
  is_hidden_tag?: boolean;
  name: string;
  space_code?: string;
  space_id?: string;
  space_type_id?: string;
  tags?: ITagsItem[];
}
interface IEvents {
  onSelected: number;
  onHide: () => void;
}
interface IProps {
  canSetDefaultSpace?: boolean;
  checked?: number;
  list: IListItem[];
  theme?: ThemeType;
}

interface ITagsItem {
  id: string;
  name: string;
  type: ETagsType;
}

const DEFAULT_BIZ_ID = 'DEFAULT_BIZ_ID';
@Component
export default class List extends Mixins(UserConfigMixin, tsc<IProps, IEvents>) {
  /** 选中的id */
  @Prop({ type: Number }) checked: number;
  /** 可设置默认空间 */
  @Prop({ default: true, type: Boolean }) canSetDefaultSpace: boolean;
  /** 列表数据 */
  @Prop({ default: () => [], type: Array }) list: IListItem[];
  /** 主题 */
  @Prop({
    default: 'light',
    type: String,
    validator: (val: string) => ['dark', 'light'].includes(val),
  })
  theme: ThemeType;

  defaultSpace: IListItem = null;
  setDefaultBizIdLoading = false;
  isSetBizIdDefault = true;

  get defaultBizId() {
    return store.getters.defaultBizId;
  }

  @Emit('selected')
  handleSelected(id: number | string) {
    return id;
  }
  @Emit('hide')
  handleHide() {}

  created() {
    !store.getters.defaultBizIdApiId && this.getUserConfigId();
  }

  // 获取当前用户的配置id
  getUserConfigId() {
    this.handleGetUserConfig(DEFAULT_BIZ_ID)
      .then((res: number) => {
        if (res) {
          store.commit('app/SET_APP_STATE', {
            defaultBizIdApiId: this.storeId,
          });
        }
      })
      .catch(e => {
        console.log(e);
      });
  }

  // 默认id处理
  async handleDefaultId() {
    this.setDefaultBizIdLoading = true;
    const defaultBizId = this.isSetBizIdDefault ? Number(this.defaultSpace.id) : 'undefined';
    this.handleSetUserConfig(DEFAULT_BIZ_ID, `${defaultBizId}`, store.getters.defaultBizIdApiId || 0)
      .then(result => {
        if (result) {
          store.commit('app/SET_APP_STATE', {
            defaultBizId,
          });
        }
      })
      .catch(e => {
        console.log(e);
      })
      .finally(() => {
        this.setDefaultBizIdLoading = false;
        this.defaultSpace = null;
      });
  }

  // 打开弹窗
  handleDefaultBizIdDialog(e: MouseEvent, data: IListItem, isSetDefault: boolean) {
    e.stopPropagation();
    this.handleHide();
    this.defaultSpace = data;
    this.isSetBizIdDefault = isSetDefault;
  }

  render() {
    return (
      <div class={['biz-list-wrap', this.theme]}>
        {this.list.length ? (
          this.list.map(item => (
            <div
              key={item.name}
              class={['list-group', this.theme, { 'no-name': !item.name }]}
            >
              {item.name && <div class='list-group-name'>{item.name}</div>}
              {item.children.map((child, i) => (
                <div
                  key={child.id || i}
                  class={['list-item', this.theme, { checked: child.id === this.checked }]}
                  onClick={() => this.handleSelected(child.id)}
                >
                  <span class='list-item-left'>
                    <span
                      class='list-item-name'
                      v-bk-overflow-tips
                    >
                      {child.name}
                    </span>
                    <span
                      class={['list-item-id', this.theme]}
                      v-bk-overflow-tips
                    >
                      ({child.space_type_id === ETagsType.BKCC ? `#${child.id}` : child.space_id || child.space_code})
                    </span>
                    {this.canSetDefaultSpace && this.defaultBizId && Number(this.defaultBizId) === child.id && (
                      <span class='item-default-icon'>
                        <span class='item-default-text'>{this.$tc('默认')}</span>
                      </span>
                    )}
                  </span>
                  {!child.is_hidden_tag && (
                    <span class='list-item-right'>
                      {child.tags?.map?.(tag => (
                        <span
                          key={tag.id}
                          style={{ ...SPACE_TYPE_MAP[tag.id]?.[this.theme] }}
                          class='list-item-tag'
                        >
                          {SPACE_TYPE_MAP[tag.id]?.name}
                        </span>
                      ))}
                    </span>
                  )}
                  {this.canSetDefaultSpace && (
                    <div class='set-default-button'>
                      {this.defaultBizId && Number(this.defaultBizId) === child.id ? (
                        <div
                          class={`btn-style-${this.theme} remove`}
                          onClick={e => this.handleDefaultBizIdDialog(e, child, false)}
                        >
                          {this.$tc('取消默认')}
                        </div>
                      ) : (
                        <div
                          class={`btn-style-${this.theme}`}
                          onClick={e => this.handleDefaultBizIdDialog(e, child, true)}
                        >
                          {this.$tc('设为默认')}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))
        ) : (
          <bk-exception
            class='no-data'
            scene='part'
            type='search-empty'
          />
        )}
        <bk-dialog
          width={480}
          ext-cls='confirm-dialog__set-default'
          footer-position='center'
          mask-close={false}
          value={!!this.defaultSpace}
          transfer
          on-value-change={val => {
            if (!val) {
              this.defaultSpace = null;
            }
          }}
        >
          <div class='confirm-dialog__hd'>
            {this.isSetBizIdDefault ? this.$tc('是否将该业务设为默认业务？') : this.$tc('是否取消默认业务？')}
          </div>
          <div class='confirm-dialog__bd'>
            {this.$tc('业务名称')}：<span class='confirm-dialog__bd-name'>{this.defaultSpace?.name || ''}</span>
          </div>
          <div class='confirm-dialog__ft'>
            {this.isSetBizIdDefault
              ? this.$tc('设为默认后，每次进入监控平台将会默认选中该业务')
              : this.$tc('取消默认业务后，每次进入监控平台将会默认选中最近使用的业务而非当前默认业务')}
          </div>
          <div slot='footer'>
            <bk-button
              class='btn-confirm'
              loading={this.setDefaultBizIdLoading}
              theme='primary'
              onClick={this.handleDefaultId}
            >
              {this.$tc('确认')}
            </bk-button>
            <bk-button
              class='btn-cancel'
              onClick={() => {
                this.defaultSpace = null;
              }}
            >
              {this.$tc('取消')}
            </bk-button>
          </div>
        </bk-dialog>
      </div>
    );
  }
}
