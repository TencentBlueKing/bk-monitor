/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { logServiceRelationBkLogIndexSet } from 'monitor-api/modules/apm_service';
import { random } from 'monitor-common/utils';

import './log_relation-list.scss';

export interface ILogRelation {
  related_bk_biz_id: number | string;
  value_list: string[];
}

interface ILogRelationList extends ILogRelation {
  indexSetList: { id: string; name: string }[];
  key: string;
}

interface IProp {
  bizSelectList?: { id: string; name: string }[];
  indexSetListMap: Map<number | string, { id: string; name: string }[]>;
  value?: ILogRelation[];
  onChange?: (v: ILogRelation[]) => void;
  onSetIndexSetListMap: (obj: {
    indexSetList: { id: string; name: string }[];
    related_bk_biz_id: number | string;
  }) => void;
}

@Component
export default class LogRelationList extends tsc<IProp> {
  @Prop({ default: () => [], type: Array }) value: ILogRelation[];
  @Prop({ default: () => [], type: Array }) bizSelectList: { id: string; name: string }[];
  @Prop({ default: () => new Map(), type: Map }) indexSetListMap: Map<number | string, { id: string; name: string }[]>;

  logRelationList: ILogRelationList[] = [];

  @Watch('value', { immediate: true })
  async handleWatchValue() {
    if (this.value.length) {
      const logRelationList = [];
      await this.getIndexSetList(this.value.map(item => item.related_bk_biz_id).filter(v => !!v));
      for (const v of this.value) {
        const logRelationListItem = this.logRelationList.find(
          item =>
            item.related_bk_biz_id === v.related_bk_biz_id &&
            JSON.stringify(v.value_list) === JSON.stringify(item.value_list)
        );
        if (logRelationListItem) {
          logRelationList.push(logRelationListItem);
        } else {
          logRelationList.push({
            ...v,
            indexSetList: this.indexSetListMap.get(v.related_bk_biz_id),
            key: random(8),
          });
        }
      }
      this.logRelationList = logRelationList;
    } else {
      this.logRelationList = [
        {
          value_list: [],
          related_bk_biz_id: '',
          indexSetList: [],
          key: random(8),
        },
      ];
    }
  }

  /**
   * @description 关联日志biz选择器改变
   * @param index
   * @param v
   * @param valueList
   * @returns
   */
  async handleLogBizChange(index: number, v: number | string, valueList: string[] = []) {
    this.logRelationList[index].value_list = valueList;
    this.logRelationList[index].indexSetList = [];
    (this.$refs[`${this.logRelationList[index].key}-indexSet`] as any).clearError();
    if (v) {
      await this.getIndexSetList([v]);
      this.logRelationList[index].indexSetList = this.indexSetListMap.get(v);
    }
    this.handleChange();
  }

  /**
   * @description 关联日志添加
   * @param index
   */
  handleAdd(index: number) {
    this.logRelationList.splice(index + 1, 0, {
      value_list: [],
      related_bk_biz_id: '',
      indexSetList: [],
      key: random(8),
    });
    this.handleChange();
  }
  /**
   * @description 关联日志删除
   * @param index
   */
  handleDel(index: number) {
    this.logRelationList.splice(index, 1);
    this.handleChange();
  }

  /**
   * @description 关联日志校验
   * @returns
   */
  validate() {
    return new Promise((resolve, reject) => {
      let isError = false;
      for (const item of this.logRelationList) {
        if (item.related_bk_biz_id && !item.value_list.length) {
          (this.$refs[`${item.key}-indexSet`] as any).setValidator({
            state: 'error',
            content: window.i18n.t('选择索引集'),
          });
          isError = true;
        } else {
          (this.$refs[`${item.key}-indexSet`] as any).clearError();
        }
      }
      if (isError) {
        reject();
      } else {
        resolve(true);
      }
    });
  }

  /**
   * @description 关联日志校验清除
   */
  clearValidator() {
    for (const item of this.logRelationList) {
      (this.$refs[`${item.key}-indexSet`] as any).clearError();
    }
  }

  /**
   * @description 关联日志索引集获取
   * @param bkBizIds
   */
  async getIndexSetList(bkBizIds: (number | string)[]) {
    const promiseList = [];
    for (const id of bkBizIds) {
      if (this.indexSetListMap.has(id)) {
        continue;
      }
      promiseList.push(
        logServiceRelationBkLogIndexSet({
          bk_biz_id: id,
        }).then(data => {
          this.handleSetIndexSetListMap(id, data);
        })
      );
    }
    await Promise.all(promiseList);
  }

  /**
   * @description 关联日志索引集改变
   */
  handleChange() {
    this.$emit(
      'change',
      this.logRelationList.map(item => ({
        related_bk_biz_id: item.related_bk_biz_id,
        value_list: item.value_list,
      }))
    );
  }

  /**
   * @description 关联日志索引集列表缓存
   * @param related_bk_biz_id
   * @param indexSetList
   */
  handleSetIndexSetListMap(related_bk_biz_id, indexSetList) {
    this.$emit('setIndexSetListMap', {
      related_bk_biz_id,
      indexSetList,
    });
  }

  render() {
    return (
      <div class='service-config-log-relation-list-edit'>
        {this.logRelationList.map((item, index) => (
          <div
            key={item.key}
            class={['list-edit-item', { 'mt-8': index !== 0 }]}
          >
            <bk-form-item>
              <bk-select
                vModel={item.related_bk_biz_id}
                display-key='name'
                id-Key='id'
                list={this.bizSelectList}
                enable-virtual-scroll
                searchable
                onChange={v => this.handleLogBizChange(index, v)}
              />
            </bk-form-item>
            <bk-form-item ref={`${item.key}-indexSet`}>
              <bk-select
                style='width:290px'
                vModel={item.value_list}
                auto-height={false}
                multiple={true}
                display-tag
                searchable
                onChange={() => this.handleChange()}
              >
                {item.indexSetList.map(option => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  />
                ))}
              </bk-select>
            </bk-form-item>
            <span
              class='icon-monitor icon-mc-plus-fill'
              onClick={() => this.handleAdd(index)}
            />
            {this.logRelationList.length > 1 && (
              <span
                class='icon-monitor icon-mc-minus-plus'
                onClick={() => this.handleDel(index)}
              />
            )}
          </div>
        ))}
      </div>
    );
  }
}
