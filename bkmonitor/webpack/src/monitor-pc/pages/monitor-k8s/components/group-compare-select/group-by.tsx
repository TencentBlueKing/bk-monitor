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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils';

import type { IGroupOption, IListItem } from './utils';

import './group-by.scss';

interface IProps {
  groupBy?: string[];
  groupOptions?: IGroupOption[];
  limit?: number;
  limitType?: string;
  limitTypes?: IListItem[];
  method?: string;
  methods?: IListItem[];
  onChange?: (v: string[]) => void;
  onGroupByLimitEnabledChange?: (v: boolean) => void;
  onLimitChange?: (v: number) => void;
  onLimitType?: (v: string) => void;
  onMethodChange?: (v: string) => void;
}

@Component
export default class GroupBy extends tsc<IProps> {
  @Prop({ required: true, type: Array, default: () => [] }) groupOptions: IGroupOption[];
  @Prop({ type: Array, default: () => [] }) limitTypes: IListItem[];
  @Prop({ type: Array, default: () => [] }) methods: IListItem[];
  @Prop({ type: Array, default: () => [] }) groupBy: string[];
  @Prop({ type: String, default: '' }) method: string;
  @Prop({ type: Number, default: 1 }) limit: number;
  @Prop({ type: String, default: '' }) limitType: string;

  @Ref('dimension-select') dimensionSelectRef: any;

  /* groupBy已选项tag */
  groupBySelectedTags: IGroupOption[] = [];
  /* groupBy已选项key */
  groupBySelectedKey = [];
  oldGroupBySelectedKey = [];
  /* groupBy可选项  */
  groupByList: IGroupOption[] = [];
  /* 是否显示选择器 */
  isShowPicker = false;
  localLimit = 1;
  localMethod = '';
  localLimitType = '';

  groupBySearch = '';

  everyTopLimitEnable = false;

  get groupByListFilter() {
    return this.groupByList.filter(item => {
      if (this.groupBySearch) {
        return item.name.toLowerCase().includes(this.groupBySearch.toLowerCase());
      }
      return true;
    });
  }

  @Watch('groupBy', { immediate: true })
  handleWatchGroupBy() {
    if (JSON.stringify(this.groupBySelectedKey) !== JSON.stringify(this.groupBy)) {
      this.groupBySelectedKey = [...this.groupBy];
      const groupByTags = [];
      const groupBySet = new Set(this.groupBy);
      this.groupByList = this.groupOptions.map(item => {
        const checked = groupBySet.has(item.id);
        if (checked) {
          groupByTags.push(item);
        }
        return {
          ...item,
          checked: checked,
        };
      });
      this.groupBySelectedTags = groupByTags;
      this.everyTopLimitEnable = this.handleGroupByLimitEnabledChange();
      this.$emit('groupByLimitEnabledChange', this.everyTopLimitEnable);
    }
  }

  @Watch('groupOptions', { immediate: true })
  handleWatchSearchList() {
    const groupBySet = new Set(this.groupBy);
    const groupByTags = [];
    this.groupByList = this.groupOptions.map(item => {
      const checked = groupBySet.has(item.id);
      if (checked) {
        groupByTags.push(item);
      }
      return {
        ...item,
        checked,
      };
    });
    this.groupBySelectedTags = groupByTags;
    this.everyTopLimitEnable = this.handleGroupByLimitEnabledChange();
    this.$emit('groupByLimitEnabledChange', this.everyTopLimitEnable);
  }

  @Watch('limit', { immediate: true })
  handleWatchLimit(val) {
    if (this.localLimit !== val) {
      this.localLimit = val;
    }
  }
  @Watch('method', { immediate: true })
  handleWatchMethod(val) {
    if (this.localMethod !== val) {
      this.localMethod = val;
    }
  }
  @Watch('limitType', { immediate: true })
  handleWatchLimitType(val) {
    if (this.localLimitType !== val) {
      this.localLimitType = val;
    }
  }

  emitChange() {
    this.everyTopLimitEnable = this.handleGroupByLimitEnabledChange();
    if (this.everyTopLimitEnable) {
      if (this.limitTypes.length && !this.localLimitType) {
        this.handleChangeLimitType(this.limitTypes[0].id);
      }
      if (this.methods.length && !this.localMethod) {
        this.handleChangeMethod(this.methods[0].value);
      }
    } else {
      this.handleChangeLimitType('');
      this.handleChangeMethod('');
    }
    this.$emit('change', this.groupBySelectedKey);
    this.$emit('groupByLimitEnabledChange', this.everyTopLimitEnable);
  }

  @Emit('limitType')
  handleChangeLimitType(val) {
    this.localLimitType = val;
    return val;
  }
  @Emit('methodChange')
  handleChangeMethod(val) {
    this.localMethod = val;
    return val;
  }

  handleGroupByLimitEnabledChange() {
    let everyTopLimitEnable = false;
    for (const item of this.groupByList) {
      if (item.checked) {
        if (item?.top_limit_enable) {
          everyTopLimitEnable = true;
        } else {
          everyTopLimitEnable = false;
          break;
        }
      }
    }
    return everyTopLimitEnable;
  }

  @Debounce(300)
  handleChangeLimit(val) {
    if (val && val >= 1 && val <= 30) {
      this.localLimit = +val;
      this.$emit('limitChange', +val);
    }
  }

  handleChange() {
    const groupByKey = [];
    const groupByTags = [];
    for (const item of this.groupByList) {
      if (item.checked) {
        groupByKey.push(item.id);
        groupByTags.push(item);
      }
    }
    this.groupBySelectedKey = groupByKey;
    this.groupBySelectedTags = groupByTags;
  }

  /**
   * @description 展示选择器
   */
  handleAdd() {
    this.isShowPicker = true;
    this.$nextTick(() => {
      this.dimensionSelectRef?.showHandler?.();
    });
  }
  /**
   * @description 选中
   * @param item
   */
  chooseSelect(item) {
    item.checked = !item.checked;
    this.handleChange();
  }
  /* 收起groupBy选择 */
  handleHide() {
    this.isShowPicker = false;
    const isDiff =
      JSON.stringify(JSON.parse(JSON.stringify(this.groupBySelectedKey)).sort()) !==
      JSON.stringify(this.oldGroupBySelectedKey);
    if (isDiff) {
      this.emitChange();
    }
  }
  handleShow() {
    this.oldGroupBySelectedKey = JSON.parse(JSON.stringify(this.groupBySelectedKey)).sort();
  }

  @Debounce(300)
  handleGroupBySearch(val: string) {
    this.groupBySearch = val;
  }
  /** 删除标签 */
  closeGroupBy(val) {
    for (const item of this.groupByList) {
      if (item.id === val.id) {
        item.checked = false;
      }
    }
    this.handleChange();
    this.emitChange();
  }

  renderTagView() {
    const len = this.groupBySelectedTags.length;
    if (len > 2) {
      const list = this.groupBySelectedTags.slice(0, 2);
      return (
        <div>
          {list.map(item => (
            <bk-tag
              key={item.id}
              closable
              on-close={() => this.closeGroupBy(item)}
            >
              {item.name}
            </bk-tag>
          ))}
          <bk-tag
            v-bk-tooltips={this.groupBySelectedTags
              .slice(2)
              .map(item => item.name)
              .join('、')}
          >
            {' '}
            +{len - 2}
          </bk-tag>
        </div>
      );
    }
    return this.groupBySelectedTags.map(item => (
      <bk-tag
        key={item.id}
        closable
        on-close={() => this.closeGroupBy(item)}
      >
        {item.name}
      </bk-tag>
    ));
  }
  render() {
    return (
      <div class='group-compare-select___group-by'>
        <div class='group-by-tag-view'>
          {!this.isShowPicker && this.groupBySelectedKey.length > 0 && this.renderTagView()}
        </div>
        {this.isShowPicker ? (
          <bk-popover
            ref='dimension-select'
            ext-cls='group-compare-select___group-by-selector'
            arrow={false}
            placement='bottom'
            theme='light'
            transfer={true}
            trigger='click'
            onHide={this.handleHide}
            onShow={this.handleShow}
          >
            <div
              class='group-by-select'
              title={this.groupBySelectedTags.map(item => item.name).join(',')}
            >
              {this.groupBySelectedTags.length ? (
                this.groupBySelectedTags.map(item => item.name).join(',')
              ) : (
                <span class='placeholder'>{this.$t('请选择维度')}</span>
              )}

              <i class='icon-monitor icon-arrow-down' />
            </div>
            <div
              class='group-by-select-list-wrap'
              slot='content'
            >
              <div class='search-header'>
                <bk-input
                  behavior='simplicity'
                  placeholder={this.$t('请输入关键字搜索')}
                  value={this.groupBySearch}
                  onChange={this.handleGroupBySearch}
                />
              </div>
              <div class='group-by-select-list'>
                {this.groupByListFilter.length ? (
                  this.groupByListFilter.map(option => {
                    return (
                      <div
                        key={option.id}
                        class={['group-by-select-item', { active: option.checked }]}
                        title={option.id}
                        onClick={() => this.chooseSelect(option)}
                      >
                        {option.name}
                        {option.checked && <i class='icon-monitor icon-mc-check-small' />}
                      </div>
                    );
                  })
                ) : (
                  <div class='no-data'>{this.$t('暂无数据')}</div>
                )}
              </div>
            </div>
          </bk-popover>
        ) : (
          <span
            class='group-by-add'
            onClick={this.handleAdd}
          >
            <i class='icon-monitor icon-plus-line' />
          </span>
        )}
        {this.groupBySelectedKey.length > 0 && !this.isShowPicker && this.everyTopLimitEnable && (
          <div class='limit-selector'>
            <span>limit</span>
            <bk-select
              style='width: 150px;'
              ext-cls='ml-8'
              v-model={this.localLimitType}
              behavior='simplicity'
              clearable={false}
              onChange={this.handleChangeLimitType}
            >
              {this.limitTypes.map(option => (
                <bk-option
                  id={option.id}
                  key={option.id}
                  name={option.name}
                />
              ))}
            </bk-select>
            <bk-select
              style='width: 90px;'
              ext-cls='ml-8'
              v-model={this.localMethod}
              behavior='simplicity'
              clearable={false}
              onChange={this.handleChangeMethod}
            >
              {this.methods.map(option => (
                <bk-option
                  id={option.value}
                  key={option.value}
                  name={option.text}
                />
              ))}
            </bk-select>
            <bk-input
              style='width: 150px;'
              class='ml-8'
              v-model={this.localLimit}
              behavior='simplicity'
              max={30}
              min={1}
              placeholder={this.$t('请输入1~30的数字')}
              type='number'
              onChange={this.handleChangeLimit}
            />
          </div>
        )}
      </div>
    );
  }
}
