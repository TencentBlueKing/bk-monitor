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
import { Component, Mixins, Prop, Ref, Watch } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';

import UserConfigMixin from '../../mixins/userStoreConfig';
import ResidentSettingTransfer from './resident-setting-transfer';
import SettingKvSelector from './setting-kv-selector';
import {
  type IFilterField,
  type IGetValueFnParams,
  type IWhereItem,
  type IWhereValueOptionsItem,
  defaultWhereItem,
  ECondition,
  EFieldType,
} from './utils';

import type { IFieldItem, TGetValueFn } from './value-selector-typing';

import './resident-setting.scss';

export interface IResidentSetting {
  field: IFilterField;
  value: IWhereItem;
}
interface IProps {
  fields: IFilterField[];
  /** 是否根据onlyKey请求默认配置， 否则根据value生成配置 */
  isDefaultSetting?: boolean;
  residentSettingOnlyId?: string;
  value?: IWhereItem[];
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  onChange?: (v: IWhereItem[]) => void;
}

@Component
class ResidentSetting extends Mixins(UserConfigMixin) {
  @Prop({ type: Array, default: () => [] }) fields: IFilterField[];
  @Prop({
    type: Function,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  })
  getValueFn: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  @Prop({ default: () => [], type: Array }) value: IWhereItem[];
  @Prop({ default: '', type: String }) residentSettingOnlyId: string;
  /** 是否根据onlyKey请求默认配置， 否则根据value生成配置 */
  @Prop({ default: true, type: Boolean }) isDefaultSetting: boolean;

  @Ref('selector') selectorRef: HTMLDivElement;

  popoverInstance = null;

  localValue: IResidentSetting[] = [];

  userConfigLoading = false;

  isValueChange = false;

  showTransfer = false;

  get fieldNameMap(): Record<string, IFilterField> {
    return this.fields.reduce((pre, cur) => {
      pre[cur.name] = cur;
      return pre;
    }, {});
  }

  get valueNameMap(): Record<string, IWhereItem> {
    return this.value.reduce((pre, cur) => {
      pre[cur.key] = cur;
      return pre;
    }, {});
  }

  @Watch('residentSettingOnlyId', { immediate: true })
  async handleWatchOnlyKey() {
    const fields: IResidentSetting[] = [];
    this.userConfigLoading = true;
    const defaultConfig = (await this.handleGetUserConfig<string[]>(this.residentSettingOnlyId)) || [];
    this.userConfigLoading = false;
    if (!this.isDefaultSetting) {
      for (const where of this.value) {
        if (this.fieldNameMap[where.key]) {
          fields.push({
            field: this.fieldNameMap[where.key],
            value: where,
          });
        }
      }
    } else {
      for (const key of defaultConfig) {
        if (this.fieldNameMap[key]) {
          fields.push({
            field: this.fieldNameMap[key],
            value: defaultWhereItem(
              this.valueNameMap[key] || {
                key: this.fieldNameMap[key].name,
                value: this.valueNameMap[key]?.value || [],
              }
            ),
          });
        }
      }
    }
    this.localValue = fields;
  }

  async handleShowSelect(event: MouseEvent) {
    if (this.popoverInstance) {
      this.destroyPopoverInstance();
      return;
    }
    this.popoverInstance = this.$bkPopover(event.target, {
      content: this.selectorRef,
      trigger: 'click',
      placement: 'bottom-start',
      theme: 'light common-monitor',
      arrow: false,
      interactive: true,
      boundary: 'window',
      distance: 15,
      zIndex: 998,
      animation: 'slide-toggle',
      followCursor: false,
      onHidden: () => {
        this.destroyPopoverInstance();
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show();
    this.showTransfer = true;
  }

  destroyPopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
    this.showTransfer = false;
  }

  handleShowSettingTransfer(event: MouseEvent) {
    event.stopPropagation();
    this.handleShowSelect({
      target: this.$el,
    } as any);
  }

  /**
   * @description 点击弹层取消
   */
  handleCancel() {
    this.destroyPopoverInstance();
  }

  /**
   * @description 点击弹层确认
   */
  handleConfirm(fields: IFilterField[]) {
    this.localValue = fields.map(item => ({
      field: item,
      value: defaultWhereItem(
        this.valueNameMap[item.name] || {
          key: item.name,
          value: [],
        }
      ),
    }));
    this.handleChange();
    this.destroyPopoverInstance();
    this.handleSetUserConfig(this.residentSettingOnlyId, JSON.stringify(fields.map(item => item.name)));
  }

  /**
   * @description 选择值改变
   * @param value
   * @param index
   */
  handleValueChange(value: IWhereItem, index: number) {
    this.localValue[index].value = value;
    this.handleChange();
  }

  // 处理change事件
  handleChange() {
    this.$emit(
      'change',
      this.localValue.map(item => item.value)
    );
  }

  getFieldInfo(item: IFilterField): IFieldItem {
    return {
      field: item.name,
      alias: item.alias,
      isEnableOptions: !!item?.is_option_enabled,
      methods:
        item?.supported_operations.map(o => ({
          id: o.value,
          name: o.alias,
        })) || [],
      type: item.type,
    };
  }

  getValueFnProxy(params: { field: string; limit: number; search: string }): any | TGetValueFn {
    return new Promise((resolve, _reject) => {
      const fieldType = this.fieldNameMap?.[params.field]?.type;
      this.getValueFn({
        where: params.search
          ? [
              {
                key: params.field,
                method: fieldType === EFieldType.integer ? 'eq' : 'include',
                value: [params.search],
                condition: ECondition.and,
                options: {
                  is_wildcard: true,
                },
              },
            ]
          : [],
        fields: [params.field],
        limit: params.limit,
        isInit__: params?.isInit__ || false,
      })
        .then(data => {
          resolve(data);
        })
        .catch(() => {
          resolve({
            count: 0,
            list: [],
          });
        });
    });
  }

  render() {
    return (
      <div class={['retrieval-filter__resident-setting-component', { 'no-data': !this.localValue.length }]}>
        <span
          class='left-btn'
          onClick={this.handleShowSettingTransfer}
        >
          <span class='icon-monitor icon-shezhi1' />
          <span class='setting-text'>{this.$t('设置筛选')}</span>
        </span>
        <div class='right-content'>
          {this.localValue.length ? (
            this.localValue.map((item, index) => (
              <SettingKvSelector
                key={index}
                class='mb-4 mr-4'
                fieldInfo={this.getFieldInfo(item.field)}
                getValueFn={this.getValueFnProxy}
                value={item.value}
                onChange={v => this.handleValueChange(v, index)}
              />
            ))
          ) : (
            <span class='placeholder-text'>{`（${this.$t('暂未设置常驻筛选，请点击左侧设置按钮')}）`}</span>
          )}
        </div>
        <div style='display: none;'>
          <div ref='selector'>
            <ResidentSettingTransfer
              fields={this.fields}
              show={this.showTransfer}
              value={this.localValue.map(item => item.field.name)}
              onCancel={this.handleCancel}
              onConfirm={this.handleConfirm}
            />
          </div>
        </div>
      </div>
    );
  }
}

export default tsx.ofType<IProps>().convert(ResidentSetting);
