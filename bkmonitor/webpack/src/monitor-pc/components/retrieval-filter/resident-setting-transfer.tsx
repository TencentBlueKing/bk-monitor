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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils';

import { type IFilterField, fieldTypeMap, getTitleAndSubtitle } from './utils';

import './resident-setting-transfer.scss';

interface IProps {
  fields: IFilterField[];
  show?: boolean;
  value?: string[];
  onCancel?: () => void;
  onConfirm?: (value: IFilterField[]) => void;
}

@Component
export default class ResidentSettingTransfer extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) fields: IFilterField[];
  @Prop({ type: Array, default: () => [] }) value: string[];
  @Prop({ type: Boolean, default: false }) show: boolean;

  @Ref('search') searchRef: HTMLDivElement;

  localFields: IFilterField[] = [];
  searchValue = '';
  selectedFields: IFilterField[] = [];
  dragOverIndex = -1;

  get searchLocalFields() {
    if (!this.searchValue) {
      return this.localFields;
    }
    return this.localFields.filter(item => {
      const searchValue = this.searchValue.toLocaleLowerCase();
      if (item.name.toLocaleLowerCase().includes(searchValue)) {
        return true;
      }
      if (item.alias.toLocaleLowerCase().includes(searchValue)) {
        return true;
      }
      return false;
    });
  }

  @Watch('show', { immediate: true })
  handleWatchShow() {
    if (this.show) {
      this.searchValue = '';
      this.dragOverIndex = -1;
      const tempSet = new Set(this.value);
      const selectedFields = [];
      const localFields = [];
      const selectedFieldsMap = new Map();
      for (const item of this.fields) {
        if (tempSet.has(item.name)) {
          selectedFields.push(item);
          selectedFieldsMap.set(item.name, item);
        } else {
          localFields.push(item);
        }
      }
      const selected = [];
      for (const v of this.value) {
        const item = selectedFieldsMap.get(v);
        if (item) {
          selected.push(item);
        }
      }
      this.localFields = localFields;
      this.selectedFields = selected;
      this.searchRef?.focus();
    }
  }

  @Watch('fields', { immediate: true })
  handleWatchFields() {
    this.handleSetLocalFields();
  }

  handleCheck(index: number) {
    const name = this.searchLocalFields[index].name;
    const delIndex = this.localFields.findIndex(item => item.name === name);
    const item = structuredClone(this.localFields[delIndex]);
    this.localFields.splice(delIndex, 1);
    this.selectedFields.push(item);
  }

  /**
   * @description 点击确定
   */
  handleConfirm() {
    this.$emit('confirm', this.selectedFields);
  }
  handleCancel() {
    this.$emit('cancel');
  }

  handleSetLocalFields() {
    const localFields = [];
    const selectedFields = new Set(this.selectedFields.map(item => item.name));
    for (const item of this.fields) {
      if (!selectedFields.has(item.name)) {
        localFields.push(item);
      }
    }
    this.localFields = localFields;
  }

  /**
   * @description 删除
   * @param event
   * @param index
   */
  handleDelete(event, index) {
    event.stopPropagation();
    this.selectedFields.splice(index, 1);
    this.handleSetLocalFields();
  }

  /**
   * @description 拖拽开始
   * @param event
   * @param index
   */
  handleDragStart(event, index) {
    event.dataTransfer.effectAllowed = 'move';
    // 设置自定义数据保存拖动项的索引
    event.dataTransfer.setData('drag-index', index);
  }
  /**
   * @description 拖拽悬停
   * @param event
   * @param _index
   */
  handleDragOver(event, _index) {
    // 阻止默认行为，允许 drop
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    this.dragOverIndex = _index;
  }
  /**
   * @description 拖拽结束
   * @param event
   * @param dropIndex
   * @returns
   */
  handleDrop(event, dropIndex) {
    event.preventDefault();
    this.dragOverIndex = -1;
    const dragIndex = event.dataTransfer.getData('drag-index');
    if (dragIndex === '') return;
    const fromIndex = Number.parseInt(dragIndex, 10);
    // 如果拖动位置和放置位置相同，则无需操作
    if (fromIndex === dropIndex) return;
    // 从数组中移除拖动项，并在目标位置插入
    const movedItem = this.selectedFields.splice(fromIndex, 1)[0];
    this.selectedFields.splice(dropIndex, 0, movedItem);
  }

  /**
   * @description 清空
   */
  handleClear() {
    this.selectedFields = [];
    this.localFields = this.fields.slice();
  }

  /**
   * @description 全部添加
   */
  handleAllAdd() {
    this.localFields = [];
    this.selectedFields = this.fields.slice();
  }

  @Debounce(300)
  handleSearchValueChange(value: string) {
    this.searchValue = value;
  }

  render() {
    const optionRender = (item: IFilterField) => {
      const { title, subtitle } = getTitleAndSubtitle(item.alias);
      return [
        <span
          key={'01'}
          style={{
            background: fieldTypeMap[item.type].bgColor,
            color: fieldTypeMap[item.type].color,
          }}
          class='option-icon'
        >
          {item.name === '*' ? (
            <span class='option-icon-xing'>*</span>
          ) : (
            <span class={[fieldTypeMap[item.type].icon, 'option-icon-icon']} />
          )}
        </span>,
        <span
          key={'02'}
          class='option-name-title'
        >
          {title}
        </span>,
        !!subtitle && <span class='option-name-subtitle'>（{subtitle}）</span>,
      ];
    };
    return (
      <div class='retrieval-filter__resident-setting-transfer-component'>
        <div class='component-top'>
          <div class='component-top-left'>
            <div class='top-header'>
              <span class='header-title'>{`${this.$t('待选列表')}（${this.localFields.length}）`}</span>
              <span
                class='header-btn'
                onClick={this.handleAllAdd}
              >
                {this.$t('全部添加')}
              </span>
            </div>
            <div class='content-wrap'>
              <div class='search-wrap'>
                <bk-input
                  ref='search'
                  behavior='simplicity'
                  left-icon='bk-icon icon-search'
                  placeholder={this.$t('请输入关键字')}
                  value={this.searchValue}
                  onChange={this.handleSearchValueChange}
                />
              </div>
              <div class='options-wrap'>
                {this.searchLocalFields.map((item, index) => (
                  <div
                    key={item.name}
                    class={'option check-type'}
                    onClick={() => this.handleCheck(index)}
                  >
                    {optionRender(item)}
                    <span class='icon-monitor icon-back-right' />
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div class='component-top-right'>
            <div class='top-header'>
              <span class='header-title'>{`${this.$t('常驻筛选')}（${this.selectedFields.length}）`}</span>
              <span
                class='header-btn'
                onClick={this.handleClear}
              >
                {this.$t('清空')}
              </span>
            </div>
            <div class='content-wrap'>
              {this.selectedFields.map((item, index) => (
                <div
                  key={item.name}
                  class={{
                    option: true,
                    'drag-type': true,
                    'drag-over': this.dragOverIndex === index,
                  }}
                  draggable={true}
                  onDragover={event => this.handleDragOver(event, index)}
                  onDragstart={event => this.handleDragStart(event, index)}
                  onDrop={event => this.handleDrop(event, index)}
                >
                  <span class='icon-monitor icon-mc-tuozhuai' />
                  {optionRender(item)}
                  <span
                    class='icon-monitor icon-mc-close-fill'
                    onClick={event => this.handleDelete(event, index)}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
        <div class='component-bottom'>
          <div class='button-wrap'>
            <bk-button
              class='mr-8'
              theme='primary'
              onClick={() => this.handleConfirm()}
            >
              {this.$t('确定')}
            </bk-button>
            <bk-button onClick={() => this.handleCancel()}>{this.$t('取消')}</bk-button>
          </div>
        </div>
      </div>
    );
  }
}
