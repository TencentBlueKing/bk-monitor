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

import VueJsonPretty from 'vue-json-pretty';
import { Component, Prop, Watch, Emit, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { updateFavorite } from 'monitor-api/modules/model';

import { mergeWhereList } from '../../../components/retrieval-filter/utils';
import { isEn } from '../../../i18n/lang';

import type { IFavList } from '../typings';

import './favorite-detail.scss';

interface IGroup {
  id: string;
  name: string;
}

interface IProps {
  value?: IFavList.favList;
  favoriteType?: string;
  groups?: IGroup[];
  onSuccess?: (data: IFavList.favList) => void;
  onClose?: () => void;
}

@Component
export default class FavoriteDetail extends tsc<IProps> {
  @Prop({ type: Object, default: () => null }) value: IFavList.favList;
  @Prop({ type: Array, default: () => [] }) groups: IGroup[];
  @Prop({ default: 'event' }) favoriteType: string;
  @Ref('nameInputWrap') nameInputWrapRef: HTMLInputElement;

  showNameInput = false;
  nameInput = '';
  nameLoading = false;
  showGroupInput = false;
  groupInput: number | object | string = '';
  groupLoading = false;

  @Emit('close')
  handleCloseDialog() {}

  @Watch('value')
  handleWatchValue() {
    this.showNameInput = false;
    this.showGroupInput = false;
    this.nameLoading = false;
    this.groupLoading = false;
  }

  /**
   * @description 收藏名称
   */
  handleEditName() {
    this.showNameInput = true;
    this.showGroupInput = false;
    this.nameInput = this.value.name;
    this.$nextTick(() => {
      this.nameInputWrapRef?.focus();
    });
  }

  /**
   * @description 所属组
   */
  handleEditGroup() {
    this.showGroupInput = true;
    this.showNameInput = false;
    this.groupInput = this.value.group_id;
  }

  async handleUpdateName() {
    this.showNameInput = false;
    if (this.nameInput && this.nameInput !== this.value.name) {
      this.nameLoading = true;
      const params = {
        ...this.value,
        name: this.nameInput,
      };
      const success = await this.handleUpdateFavorite(params);
      this.nameLoading = false;
      if (success) {
        this.$emit('success', params);
      }
    }
  }

  async handleUpdateGroup() {
    this.showGroupInput = false;
    if (this.groupInput && this.groupInput !== this.value.group_id) {
      this.groupLoading = true;
      const groupName = this.groups.find(item => String(item.id) === String(this.groupInput))?.name;
      const params = {
        ...this.value,
        group_id: this.groupInput === 'null' ? null : this.groupInput,
      };
      const success = await this.handleUpdateFavorite(params);
      this.groupLoading = false;
      if (success) {
        this.$emit('success', {
          ...params,
          groupName: groupName || this.value.groupName,
        });
      }
    }
  }
  async handleUpdateFavorite(data) {
    const success = await updateFavorite(data.id, {
      group_id: data.group_id,
      name: data.name,
      type: this.favoriteType,
      config: data.config,
    })
      .then(() => {
        return true;
      })
      .catch(() => {
        return false;
      });
    return success;
  }

  queryContent() {
    const queryConfig = this.value.config.queryConfig;
    if (this.favoriteType === 'event') {
      const filterMode = queryConfig.filterMode;
      if (filterMode === 'ui') {
        return (
          <div class='json-wrap'>
            <VueJsonPretty
              data={{
                data_source_label: queryConfig?.data_source_label || '',
                data_type_label: queryConfig?.data_type_label || '',
                table: queryConfig?.result_table_id || '',
                where: mergeWhereList(queryConfig.where, queryConfig.commonWhere || []),
              }}
              deep={5}
            />
          </div>
        );
      }
      return <div class='query-string-wrap'>{queryConfig.query_string}</div>;
    }
    if (this.value.config?.promqlData?.length) {
      const promqlData = this.value.config.promqlData
        .filter(pItem => pItem.code)
        .map(item => ({
          label: `${window.i18n.t('查询项')}${item.alias}:`,
          value: item.code,
        }));
      return (
        <div class='query-string-wrap'>
          {promqlData.map(item => (
            <div
              key={`${item.label}_${item.value}`}
              class='promql-box'
            >
              <div class='promql-label'>{item.label}</div>
              <div class='promql-val'>{item.value}</div>
            </div>
          ))}
        </div>
      );
    }
    return (
      <div class='json-wrap'>
        <VueJsonPretty
          data={this.value.config}
          deep={5}
        />
      </div>
    );
  }

  render() {
    function formItem(title, content) {
      return (
        <div class='form-item'>
          <div class='form-item-label'>{title}：</div>
          <div class='form-item-content'>{content}</div>
        </div>
      );
    }
    return (
      <div class='favorite-manage___favorite-detail-component'>
        <div class='header-title'>
          {this.$t('收藏详情')}
          <i
            class='icon-monitor icon-mc-close'
            onClick={this.handleCloseDialog}
          />
        </div>
        <div class={['detail-items-wrap', { 'is-en': isEn }]}>
          {formItem(
            this.$t('收藏名称'),
            !this.nameLoading ? (
              !this.showNameInput ? (
                <span class='edit-name-wrap'>
                  <div class='edit-name'>{this.value.name}</div>
                  <span
                    class='icon-monitor icon-bianji'
                    onClick={this.handleEditName}
                  />
                </span>
              ) : (
                <bk-input
                  ref='nameInputWrap'
                  class='edit-input-wrap'
                  v-model={this.nameInput}
                  onBlur={() => this.handleUpdateName()}
                  onEnter={() => this.handleUpdateName()}
                />
              )
            ) : (
              <div class='skeleton-element input-loading' />
            )
          )}
          {formItem(
            this.$t('所属组'),
            !this.groupLoading ? (
              !this.showGroupInput ? (
                <span class='edit-name-wrap'>
                  <div class='edit-name'>{this.value.groupName}</div>
                  <span
                    class='icon-monitor icon-bianji'
                    onClick={this.handleEditGroup}
                  />
                </span>
              ) : (
                <bk-select
                  class='edit-input-wrap'
                  v-model={this.groupInput}
                  clearable={false}
                  onChange={this.handleUpdateGroup}
                >
                  {this.groups.map(item => (
                    <bk-option
                      id={String(item.id)}
                      key={String(item.id)}
                      name={item.name}
                    />
                  ))}
                </bk-select>
              )
            ) : (
              <div class='skeleton-element input-loading' />
            )
          )}
          {this.favoriteType === 'event'
            ? formItem(this.$t('数据ID'), <div class='item-name'>{this.value.config.queryConfig.result_table_id}</div>)
            : undefined}
          {formItem(this.$t('查询语句'), <div class='query-content-wrap'>{this.queryContent()}</div>)}
        </div>
      </div>
    );
  }
}
