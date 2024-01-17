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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import AppStore from '../../store/modules/app';

import './app-select.scss';

interface IProps {
  placement?: string;
  list: IAppSelectOptItem[];
  tipsPlacement?: string;
}
interface IEvents {
  onSelected: IAppSelectOptItem;
}
export interface IAppSelectOptItem {
  id: string;
  name: string;
  icon: string;
  desc: string;
}
@Component
export default class AppSelect extends tsc<IProps, IEvents> {
  @Prop({ default: 'bottom-end', type: String }) placement: string;
  @Prop({ default: 'left', type: String }) tipsPlacement: string;
  @Prop({ default: () => [], type: Array }) list: IAppSelectOptItem[];
  @Ref() popoverInstance: any;

  /** DEMO业务 */
  get demoBiz() {
    return this.$store.getters.demoBiz;
  }

  @Emit('selected')
  handleSelect(opt: IAppSelectOptItem) {
    this.handleHide();
    return opt;
  }

  handleHide() {
    this.popoverInstance?.hideHandler?.();
  }

  /**
   * 切换demo业务
   */
  handleToDemo() {
    if (this.demoBiz?.id) {
      if (+this.$store.getters.bizId === +this.demoBiz.id) {
        location.reload();
      } else {
        /** 切换为demo业务 */
        AppStore.handleChangeBizId({
          bizId: this.demoBiz.id,
          ctx: this
        });
      }
    }
  }

  render() {
    return (
      <bk-popover
        ref='popoverInstance'
        theme='light common-monitor app-select'
        placement={this.placement}
        offset={-1}
        distance={16}
        animation='slide-toggle'
        tippy-options={{
          arrow: false,
          trigger: 'click'
        }}
      >
        {this.$slots.default ?? <bk-button theme='primary'>{this.$t('新建应用')}</bk-button>}
        <div
          slot='content'
          class='app-select-main'
        >
          <div class='app-select-title'>{this.$t('插件选择')}</div>
          <ul class='app-select-list'>
            {this.list.map(opt => (
              <li
                class='app-select-item'
                onClick={() => this.handleSelect(opt)}
              >
                <span class={['app-select-item-icon']}>
                  <img
                    src={opt.icon}
                    alt=''
                  ></img>
                </span>
                <span class='app-select-content'>
                  <span class='app-select-name'>{opt.name}</span>
                  <span
                    class='app-select-desc'
                    v-bk-overflow-tips={{ content: opt.desc, placement: this.tipsPlacement }}
                  >
                    {opt.desc}
                  </span>
                </span>
              </li>
            ))}
          </ul>
          {!!this.demoBiz && (
            <div
              class='app-select-demo'
              onClick={this.handleToDemo}
            >
              {this.$t('DEMO')}
            </div>
          )}
        </div>
      </bk-popover>
    );
  }
}
