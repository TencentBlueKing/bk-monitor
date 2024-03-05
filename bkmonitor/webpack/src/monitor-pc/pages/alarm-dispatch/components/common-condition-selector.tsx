/* eslint-disable no-param-reassign */
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

import SimpleSelectInput from '../../alarm-shield/components/simple-select-input';
import SelectMenu from '../../strategy-config/strategy-config-set-new/components/select-menu';
import { CONDITIONS, ICondtionItem, METHODS, TContionType, TMthodType } from '../typing';
import { TGroupKeys, TValueMap } from '../typing/condition';

import './common-condition-selector.scss';

const nullOptions = {
  // 下拉选项第一为空值
  id: '',
  name: `- ${window.i18n.tc('空')} -`
};

interface IListItem {
  id: string;
  name: string;
  isCheck?: boolean;
}

interface ICondition {
  field: string;
  value?: string[];
  method?: TMthodType;
  condition?: TContionType;
  name?: string;
}

interface IProps {
  value: ICondtionItem[];
  keyList?: IListItem[];
  valueList?: IListItem[];
  valueMap?: TValueMap;
  groupKeys?: TGroupKeys;
  groupKey?: string[];
  onChange?: (v: ICondtionItem[]) => void;
}

@Component
export default class CommonConditionSelector extends tsc<IProps> {
  /* 当前condition */
  @Prop({ default: () => [], type: Array }) value: ICondtionItem[];
  /* 可供选择的key选项 */
  @Prop({ default: () => [], type: Array }) keyList: IListItem[];
  /* key对应的value选项集合 */
  @Prop({ default: () => new Map(), type: Map }) valueMap: TValueMap;
  /* 组合项key 如 dimension.xxx  tags.xxxx*/
  @Prop({ default: () => new Map(), type: Map }) groupKeys: TGroupKeys;
  /* 组合项key前缀，如命中前缀可展开groupKeys内的选项以供选择 */
  @Prop({ default: () => [], type: Array }) groupKey: string[];

  conditions: ICondition[] = [];
  keyMaps = new Map();

  curSelectTarget = null;
  showSelectMenu = false;
  menuList = [];
  curConditionIndex = -1;
  curConditionProp = '';

  get showAdd() {
    if (!this.conditions.length) return false;
    const { field, value } = this.conditions[this.conditions.length - 1];
    return field && value?.length > 0;
  }

  created() {
    this.keyList.forEach(keyItem => {
      this.keyMaps.set(keyItem.id, keyItem);
    });
    const conditions = this.value
      .filter(item => !!item.field)
      .map(item => ({
        ...item,
        name: this.keyMaps.get(item.field)?.name || item.field
      }));
    if (conditions.length) {
      this.conditions = conditions;
    } else {
      this.conditions = [this.handleGetDefaultCondition(false) as any];
    }
  }

  @Emit('change')
  handleConditionChange() {
    return this.conditions;
  }

  /* 弹出条件选择 */
  handleToggleCondition(e, { index, prop }) {
    this.curSelectTarget = e.target;
    this.showSelectMenu = true;
    this.menuList = CONDITIONS;
    this.curConditionIndex = index;
    this.curConditionProp = prop;
  }

  /* 选中field */
  async handleKeyChange(item: ICondition, v: string) {
    this.$emit('key-loading', true);
    if (!v && this.conditions.length > 1) this.handleDeleteKey(this.value.length - 1);
    item.name = v;
    let id = v;
    this.keyList.forEach(item => {
      if (item.id === v || item.name === v) {
        id = item.id as string;
      }
    });
    if (item.field !== id) {
      item.value = [];
    }
    item.field = id;
    if (id && !this.keyMaps.get(id)) {
      await this.getVariableValueList(id);
    }
    this.conditions = this.conditions.slice();
    this.handleConditionChange();
    this.$emit('key-loading', false);
  }

  /* 删除条件 */
  handleDeleteKey(index: number) {
    const deleteList = this.conditions.splice(index, 1);
    if (!this.conditions.length) {
      this.conditions.push(this.handleGetDefaultCondition(false) as any);
    } else {
      if (this.conditions[index] && (this.conditions[index - 1]?.condition || index === 0)) {
        delete this.conditions[index].condition;
      }
    }
    !!deleteList?.[0]?.field && this.handleConditionChange();
  }

  /* 获取value列表 */
  getVariableValueList(field: string) {
    return this.valueMap.get(field) || [];
  }
  handleGetDefaultCondition(needCondition = true) {
    return Object.assign(
      {},
      {
        field: '',
        name: '',
        value: [],
        method: 'eq'
      },
      needCondition ? { condition: 'and' } : {}
    );
  }

  /* 弹出判断方式 */
  handleToggleMethod(e, { index, prop }) {
    this.curSelectTarget = e.target;
    this.showSelectMenu = true;
    this.menuList = METHODS;
    this.curConditionIndex = index;
    this.curConditionProp = prop;
  }

  handleGetMethodNameById(id: string) {
    return METHODS.find(item => item.id === id)?.name || '';
  }

  // 粘贴条件时触发(tag-input)
  handlePaste(v, item) {
    const SYMBOL = ';';
    /** 支持 空格 | 换行 | 逗号 | 分号 分割的字符串 */
    const valList = `${v}`.replace(/(\s+)|([,;])/g, SYMBOL)?.split(SYMBOL);
    const ret = [];
    valList.forEach(val => {
      !item.value.some(v => v === val) && val !== '' && item.value.push(val);
      if (!this.valueMap.get(item.field)?.some(item => item.id === val)) {
        ret.push({
          id: val,
          name: val,
          show: true
        });
      }
    });
    this.handleConditionChange();
    return ret;
  }

  // value变化时触发
  async handleValueChange(item: ICondition, v: string[]) {
    await this.$nextTick();
    if (item.value.includes(nullOptions.id)) {
      if (v.length > 1) {
        item.value = v.filter(str => str !== nullOptions.id);
      } else {
        item.value = v;
      }
    } else {
      if (v.includes(nullOptions.id)) {
        item.value = [nullOptions.id];
      } else {
        item.value = v;
      }
    }
    this.conditions = this.conditions.slice();
    this.handleConditionChange();
  }

  async handleAddCondition() {
    this.conditions.push(this.handleGetDefaultCondition() as any);
    setTimeout(() => {
      (this.$refs[`selectInput${this.conditions.length - 1}`] as SimpleSelectInput).inputWrapRef.click();
      (this.$refs[`selectInput${this.conditions.length - 1}`] as SimpleSelectInput).inputRef.focus();
    }, 100);
  }

  handelMenuSelect(item) {
    const condition = this.conditions[this.curConditionIndex];
    if (!condition) return;
    condition[this.curConditionProp] = item?.id;
    this.handleConditionChange();
  }

  handleMenuHidden() {
    this.curSelectTarget = null;
    this.menuList = [];
    this.showSelectMenu = false;
  }

  render() {
    return (
      <div class='common-condition-selector-component'>
        {this.conditions.map((item, index) => [
          item.condition && item.field && index > 0 ? (
            <input
              style={{ display: item.condition ? 'block' : 'none' }}
              key={`condition-${index}-${item.field}`}
              class='condition-item condition-item-condition'
              readonly
              value={item.condition.toLocaleUpperCase()}
              on-click={e => this.handleToggleCondition(e, { index, prop: 'condition' })}
            />
          ) : undefined,
          <SimpleSelectInput
            ref={`selectInput${index}`}
            value={item.name}
            list={this.keyList as any}
            placeholder={window.i18n.t('选择') as string}
            v-bk-tooltips={{
              content: item.field,
              trigger: 'mouseenter',
              zIndex: 9999,
              disabled: !item.field,
              boundary: document.body,
              allowHTML: false
            }}
            nodataMsg={window.i18n.t('无选项') as string}
            onChange={v => this.handleKeyChange(item, v)}
          ></SimpleSelectInput>,
          item.name
            ? [
                <span
                  class='condition-item condition-item-method'
                  key={`method-${index}-${item.field}`}
                  on-click={e => this.handleToggleMethod(e, { index, prop: 'method' })}
                >
                  {this.handleGetMethodNameById(item.method)}
                </span>,
                <bk-tag-input
                  key={`value-${index}-${item.field}-${JSON.stringify(this.valueMap.get(item.field) || [])}`}
                  class='condition-item condition-item-value'
                  list={
                    this.valueMap.get(item.field) ? [nullOptions].concat(this.valueMap.get(item.field)) : [nullOptions]
                  }
                  trigger='focus'
                  has-delete-icon
                  allow-create
                  allow-auto-match
                  value={item.value}
                  paste-fn={v => this.handlePaste(v, item)}
                  on-change={(v: string[]) => this.handleValueChange(item, v)}
                ></bk-tag-input>
              ]
            : undefined
        ])}
        <span
          class='condition-item condition-add'
          style={{ display: this.showAdd ? 'flex' : 'none' }}
          on-click={() => this.handleAddCondition()}
        >
          <i class='bk-icon icon-plus'></i>
        </span>
        <SelectMenu
          show={this.showSelectMenu}
          target={this.curSelectTarget}
          list={this.menuList}
          min-width={60}
          on-on-select={item => this.handelMenuSelect(item)}
          on-on-hidden={() => this.handleMenuHidden()}
        ></SelectMenu>
      </div>
    );
  }
}
