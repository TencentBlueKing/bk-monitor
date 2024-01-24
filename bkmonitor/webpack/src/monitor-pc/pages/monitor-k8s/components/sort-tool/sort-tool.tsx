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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './sort-tool.scss';

interface ISortFieldItem {
  id: string;
  name: string;
}

interface IProps {
  defaultField?: string;
  sortFields: ISortFieldItem[];
}

interface IEvents {
  onChange: string;
}

@Component
export default class SortTool extends tsc<IProps, IEvents> {
  @Prop({ type: String, default: '' }) defaultField: string;
  @Prop({ required: true }) sortFields: ISortFieldItem[];

  isDropdownShow = false;
  activeField = '';
  order = 'ascending';
  // isActive = false;

  get sortFieldName() {
    return this.sortFields?.find(item => item.id === this.activeField)?.name || '';
  }

  created() {
    // 根据默认排序字段 初始化默认字段和排序类型
    if (this.defaultField) {
      if (/^(-)/.test(this.defaultField)) {
        this.activeField = this.defaultField.substring(1, this.defaultField.length);
        this.order = 'descending';
      } else {
        this.activeField = this.defaultField;
        this.order = 'ascending';
      }
    }
  }

  @Emit('change')
  handleOrderChange() {
    let sortKey = '';
    switch (this.order) {
      case 'ascending':
        sortKey = this.activeField;
        break;
      case 'descending':
        sortKey = `-${this.activeField}`;
        break;
      // default:
      //   sortKey = undefined;
    }
    return sortKey;
  }

  @Watch('sortFields', { immediate: true })
  handlesortFieldsChange() {
    if (!this.defaultField) {
      this.activeField = this.sortFields[0]?.id;
    }
  }

  handleDropdownShow(isShow) {
    this.isDropdownShow = isShow;
  }
  handleChangeSortField(id) {
    this.activeField = id;
    if (this.order) {
      this.handleOrderChange();
    }
  }
  handleChangeOrder(e) {
    e.stopPropagation();
    // this.isActive = true;
    switch (this.order) {
      case 'ascending':
        this.order = 'descending';
        break;
      case 'descending':
        this.order = 'ascending';
        break;
      // default:
      //   this.order = 'ascending';
    }

    this.handleOrderChange();
  }

  render() {
    return (
      <div class='sort-tool-wrap'>
        <bk-dropdown-menu
          class='sort-dropdown-menu'
          trigger='click'
          onShow={() => this.handleDropdownShow(true)}
          onHide={() => this.handleDropdownShow(false)}
        >
          <div
            class='sort-trigger'
            slot='dropdown-trigger'
          >
            <div
              class={['trigger-text', { 'is-active': this.isDropdownShow }]}
              v-bk-tooltips={{ content: this.$t('排序并置顶') }}
            >
              {this.sortFieldName}
            </div>
            <div
              class={['sort-btn', 'active']}
              v-bk-tooltips={{
                content: `${this.order === 'ascending' ? this.$t('升序') : this.$t('降序')}`,
                disabled: !this.order
              }}
              onClick={e => this.handleChangeOrder(e)}
            >
              <i
                class={`icon-monitor ${!this.order || this.order === 'ascending' ? 'icon-shengxu' : 'icon-jiangxu'}`}
              />
            </div>
          </div>
          <ul
            class='bk-dropdown-list'
            slot='dropdown-content'
          >
            {this.sortFields.map(option => (
              <li>
                <a
                  class={[{ active: option.id === this.activeField }]}
                  onClick={() => this.handleChangeSortField(option.id)}
                >
                  {option.name}
                </a>
              </li>
            ))}
          </ul>
        </bk-dropdown-menu>
      </div>
    );
  }
}
