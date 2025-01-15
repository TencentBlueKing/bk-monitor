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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { partialUpdateUserConfig } from 'monitor-api/modules/model';

import store from '../../store/store';

import { SPACE_TYPE_MAP } from '../../common/constant';
import PerformanceModule from '../../store/modules/performance';

import type { ThemeType } from './biz-select';

import './list.scss';

interface IProps {
  list: IListItem[];
  checked?: number;
  theme?: ThemeType;
}
interface IEvents {
  onSelected: number;
}
export interface IListItem {
  id: number | string;
  name: string;
  space_code?: string;
  space_type_id?: string;
  space_id?: string;
  tags?: ITagsItem[];
  children?: IListItem[];
  is_hidden_tag?: boolean;
}
interface ITagsItem {
  id: string;
  name: string;
  type: ETagsType;
}
interface IDialogData {
  id: number | string;
  type: boolean;
  targetName: string;
}
export enum ETagsType {
  BCS = 'bcs' /** 容器项目 */,
  BKCC = 'bkcc' /** 业务 */,
  BKCI = 'bkci' /** 蓝盾项目 */,
  BKSAAS = 'bksaas' /** 蓝鲸应用 */,
  MONITOR = 'monitor' /** 监控空间 */,
}
@Component
export default class List extends tsc<IProps, IEvents> {
  /** 选中的id */
  @Prop({ type: Number }) checked: number;
  /** 列表数据 */
  @Prop({ default: () => [], type: Array }) list: IListItem[];
  /** 主题 */
  @Prop({
    default: 'light',
    type: String,
    validator: (val: string) => ['dark', 'light'].includes(val),
  })
  theme: ThemeType;

  stickyId = -1;

  dialogShow = false;

  dialogData: IDialogData = {
    id: 0,
    type: false,
    targetName: '',
  }

  btnLoading = false;

  get defaultBizId() {
    return store.getters.defaultBizId;
  }

  @Emit('selected')
  handleSelected(id: number | string) {
    return id;
  }

  created() {
    this.getUserConfig();
  }

  // 获取当前用户的置顶配置id
  async getUserConfig() {
    const stickyList = await PerformanceModule.getUserConfigList({
      key: 'DEFAULT_BIZ_ID',
    });
    if (!stickyList.length) {
      // 如果用户配置不存在就创建配置
      PerformanceModule.createUserConfig({
        key: 'DEFAULT_BIZ_ID',
        value: JSON.stringify({}),
      })
        .then(data => {
          this.stickyId = data[0].id || -1;
        })
        .catch(e => console.log(e));
    } else {
      this.stickyId = stickyList[0].id;
    }
  }

  // 默认id处理
  async handleDefaultId() {
    this.btnLoading = true;
    const result = await partialUpdateUserConfig(this.stickyId, {
      key: 'default_biz_id',
      value: this.dialogData.type ? Number(this.dialogData.id) : 'undefined',
    }).finally(() => {
      this.btnLoading = false;
      this.dialogShow = false;
    });
    if (result) {
      store.commit('app/SET_APP_STATE', {
        defaultBizId: this.dialogData.type ? Number(this.dialogData.id) : '',
      })
    }
  }

  // 打开弹窗
  handleOpenDialog(data: IDialogData, e: MouseEvent) {
    e.stopPropagation();
    this.dialogData = data;
    this.dialogShow = true;
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
                    {this.defaultBizId && Number(this.defaultBizId) === child.id && (
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
                  <div class='set-default-button'>
                    {this.defaultBizId && Number(this.defaultBizId) === child.id ? (
                      <div
                        class={`btn-style-${this.theme} remove`}
                        onClick={e => this.handleOpenDialog({ id: child.id, type: false, targetName: child.name }, e)}
                      >
                        {this.$tc('取消默认')}
                      </div>
                    ) : (
                      <div
                        class={`btn-style-${this.theme}`}
                        onClick={e => this.handleOpenDialog({ id: child.id, type: true, targetName: child.name }, e)}
                      >
                        {this.$tc('设为默认')}
                      </div>
                    )}
                  </div>
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
          value={this.dialogShow}
          transfer
        >
          <div class='confirm-dialog__hd'>
            {this.dialogData.type ? this.$tc('是否将该业务设为默认业务？') : this.$tc('是否取消默认业务？')}
          </div>
          <div class='confirm-dialog__bd'>
            {this.$tc('业务名称')}：<span class='confirm-dialog__bd-name'>{this.dialogData.targetName}</span>
          </div>
          <div class='confirm-dialog__ft'>
            {this.dialogData.type
              ? this.$tc('设为默认后，每次进入监控平台将会默认选中该业务')
              : this.$tc('取消默认业务后，每次进入监控平台将会默认选中最近使用的业务而非当前默认业务')}
          </div>
          <div slot='footer'>
            <bk-button
              class='btn-confirm'
              loading={this.btnLoading}
              theme='primary'
              onClick={this.handleDefaultId}
            >
              {this.$tc('确认')}
            </bk-button>
            <bk-button
              class='btn-cancel' 
              onClick={() => {
                this.dialogShow = false;
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
