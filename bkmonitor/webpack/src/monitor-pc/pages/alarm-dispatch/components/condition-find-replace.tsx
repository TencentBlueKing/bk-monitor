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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

// import CommonConditionSelector from './common-condition-selector';
import CommonCondition from './common-condition-new';

import type { TGroupKeys, TValueMap } from '../typing/condition';

import './condition-find-replace.scss';

export interface IListItem {
  id: string;
  isCheck?: boolean;
  name: string;
}

interface IProps {
  groupKey: string[];
  groupKeys: TGroupKeys;
  keyList?: IListItem[];
  valueMap: TValueMap;
}

@Component
export default class ConditionFindReplace extends tsc<IProps> {
  /* 可供选择的key选项 */
  @Prop({ default: () => [], type: Array }) keyList: IListItem[];
  /* key对应的value选项集合 */
  @Prop({ default: () => new Map(), type: Map }) valueMap: TValueMap;
  /* 组合项key 如 dimension.xxx  tags.xxxx*/
  @Prop({ default: () => new Map(), type: Map }) groupKeys: TGroupKeys;
  /* 组合项key前缀，如命中前缀可展开groupKeys内的选项以供选择 */
  @Prop({ default: () => [], type: Array }) groupKey: string[];

  /* 查找数据 */
  findData = [];
  /* 替换数据 */
  replaceData = [];

  render() {
    return (
      <div class='condition-find-replace-component'>
        <div class='find-wrap'>
          <div class='header-title'>{this.$t('查找规则')}</div>
          <div class='select-content'>
            <CommonCondition
              groupKey={this.groupKey}
              groupKeys={this.groupKeys}
              isFormMode={false}
              keyList={this.keyList}
              needValidate={false}
              value={this.findData}
              valueMap={this.valueMap}
              onChange={v => (this.findData = v)}
            />
          </div>
        </div>
        <div class='repace-wrap'>
          <div class='header-title'>{this.$t('批量替换成')}</div>
          <div class='select-content'>
            <CommonCondition
              groupKey={this.groupKey}
              groupKeys={this.groupKeys}
              isFormMode={false}
              keyList={this.keyList}
              needValidate={false}
              value={this.findData}
              valueMap={this.valueMap}
              onChange={v => (this.replaceData = v)}
            />
          </div>
        </div>
      </div>
    );
  }
}
