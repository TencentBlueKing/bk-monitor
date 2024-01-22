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

import { DetectionRuleTypeEnum, IDetectionTypeItem } from '../typings/index';

import './rules-select.scss';

interface IRulesSelect {
  readonly?: boolean;
  typeList?: IDetectionTypeItem[];
  isFirst?: boolean;
}

interface IEvent {
  onTypeChange: IDetectionTypeItem;
}

@Component({ name: 'RulesSelect' })
export default class RulesSelect extends tsc<IRulesSelect, IEvent> {
  @Prop({ default: false, type: Boolean }) readonly: boolean;
  /** 当前算法是否是第一个 */
  @Prop({ default: false, type: Boolean }) isFirst: boolean;
  /** 算法列表 */
  @Prop({ default: () => [], type: Array }) typeList: IDetectionTypeItem[];

  @Ref('type-select') typeEl: HTMLElement;

  show = true;

  /** 按照智能算法和常规算法进行分类 */
  get induceTypeList() {
    return this.typeList.reduce(
      (pre, cur) => {
        if (cur.type === 'ai') pre.ai.push(cur);
        else if (cur.id !== DetectionRuleTypeEnum.PartialNodes || !cur.disabled) {
          // 部分节点数算法只有在可选时，才展示
          pre.convention.push(cur);
        }
        return pre;
      },
      {
        ai: [] as IDetectionTypeItem[],
        convention: [] as IDetectionTypeItem[]
      }
    );
  }

  @Watch('isFirst', { immediate: true })
  isFirstChange(val1) {
    this.show = val1;
  }

  handleTypeChange(item) {
    if (item.disabled) return;
    this.show = false;
    this.$emit('typeChange', item);
    return item;
  }

  showChange() {
    this.show = !this.show;
  }

  render() {
    return (
      <div class='rules-select-wrap'>
        {!this.show ? (
          <bk-button
            text
            on-click={this.showChange}
            size='small'
            disabled={this.readonly}
            ext-cls='rule-add-btn'
          >
            <div class='rule-add'>
              <span class='icon-monitor icon-mc-add'></span>
              {this.$t('检测规则')}
            </div>
          </bk-button>
        ) : (
          <div class='select-type-panel'>
            <div class='header'>
              <span class='title'>{this.$t('选择算法')}</span>
              {!this.isFirst && (
                <span
                  class='icon-monitor icon-mc-delete-line del-btn'
                  onClick={this.showChange}
                ></span>
              )}
            </div>
            <div class='rules-category-list'>
              <p class='category-label'>{this.$t('智能算法')}</p>
              <div class='type-list'>
                {this.induceTypeList.ai.map(item => (
                  <div
                    class={['type-list-item', item.disabled && 'disabled']}
                    onClick={() => this.handleTypeChange(item)}
                    v-bk-tooltips={{
                      content: item.disabled ? item.disabledTip : item.tip,
                      disabled: !item.disabled,
                      allowHTML: false
                    }}
                  >
                    <img
                      src={item.icon}
                      alt=''
                      class='type-icon'
                    />
                    <span>{item.name}</span>
                  </div>
                ))}
              </div>
            </div>
            <div class='rules-category-list'>
              <p class='category-label'>{this.$t('常规算法')}</p>
              <div class='type-list'>
                {this.induceTypeList.convention.map(item => (
                  <div
                    class={['type-list-item', item.disabled && 'disabled']}
                    onClick={() => this.handleTypeChange(item)}
                    v-bk-tooltips={{
                      content: item.disabled ? item.disabledTip : item.tip,
                      disabled: !item.disabled,
                      allowHTML: false
                    }}
                  >
                    <img
                      src={item.icon}
                      alt=''
                      class='type-icon'
                    />
                    <span>{item.name}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }
}
