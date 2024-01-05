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
import { Component, Emit } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getUserDepartments, listDepartments } from '../../../../monitor-api/modules/commons';

import './organization-selector.scss';

interface IItem {
  id: number | string;
  full_name: string;
  name: string;
}

const typeIndexs = {
  bg: 0,
  dept: 1,
  center: 2
};
type IType = 'bg' | 'dept' | 'center';

interface ISelectItem {
  list: IItem[];
  value: number | string;
  type: IType;
  loading: boolean;
}

interface IProps {
  onChange?: (value: string[]) => void;
}

@Component
export default class OrganizationSelector extends tsc<IProps> {
  allSelectList: ISelectItem[] = [
    { list: [], value: '', type: 'bg', loading: false },
    { list: [], value: '', type: 'dept', loading: false },
    { list: [], value: '', type: 'center', loading: false }
  ];

  async created() {
    this.allSelectList.forEach(item => {
      item.loading = true;
    });
    const data = await getUserDepartments().catch(() => []);
    (data.length <= 3 ? data : data.slice(1)).forEach((item, index) => {
      this.allSelectList[index].list = [item];
      this.allSelectList[index].value = item.id;
    });
    this.handleChange();
    await this.getAllSelectList('bg', true);
    this.allSelectList.forEach(item => {
      item.loading = false;
    });
  }

  /* 获取单个列表 */
  async getSelectList(type: IType, id: string | number) {
    const index = typeIndexs[type];
    this.allSelectList[index].loading = true;
    const data = await listDepartments({
      type,
      id: type === 'bg' ? '' : id
    }).catch(() => []);
    this.allSelectList[index].list = data;
    if (this.allSelectList[index].value) {
      if (!this.allSelectList[index].list.map(l => l.id).includes(this.allSelectList[index].value)) {
        this.allSelectList[index].value = '';
      }
    }
    this.allSelectList[index].loading = false;
  }

  /* 获取指定或者全部联机列表 */
  async getAllSelectList(type: IType, isInit = false) {
    if (isInit) {
      const promiseList = [];
      let preId = '';
      this.allSelectList.forEach(item => {
        const promiseItem = new Promise(resolve => {
          this.getSelectList(item.type, preId).then(() => {
            resolve(true);
          });
        });
        promiseList.push(promiseItem);
        preId = item.value as any;
      });
      await Promise.all(promiseList);
      return;
    }
    const changeIndex = this.allSelectList.findIndex(item => item.type === type);
    if (changeIndex >= 0) {
      const targetId = this.allSelectList[changeIndex].value;
      const targetType = this.allSelectList[changeIndex + 1]?.type;
      if (targetType && targetId) {
        await this.getSelectList(targetType, targetId);
      }
    }
  }

  handleSelected(type: IType) {
    this.allSelectList.forEach((item, index) => {
      if (type === 'bg' && index > 0) {
        item.value = '';
        item.list = [];
      } else if (type === 'dept' && index > 1) {
        item.value = '';
        item.list = [];
      }
    });
    this.handleChange();
    this.getAllSelectList(type);
  }

  @Emit('change')
  handleChange() {
    return this.allSelectList.map(item => item.value);
  }

  render() {
    return (
      <div class='organization-selector-component'>
        {this.allSelectList.map(item => (
          <div
            class='item-wrap'
            key={item.type}
          >
            <bk-select
              v-model={item.value}
              loading={item.loading}
              searchable
              clearable={false}
              onSelected={() => this.handleSelected(item.type)}
            >
              {item.list.map(option => (
                <bk-option
                  key={option.id}
                  id={option.id}
                  name={option.name}
                ></bk-option>
              ))}
            </bk-select>
          </div>
        ))}
      </div>
    );
  }
}
