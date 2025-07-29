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

import CommonNavBar from 'monitor-pc/pages/monitor-k8s/components/common-nav-bar';

import type { INavItem, IRouteBackItem } from 'monitor-pc/pages/monitor-k8s/typings';

import './nav-bar.scss';

type handlerPosition = 'center' | 'left' | 'right';
interface IProps {
  backGotoItem?: IRouteBackItem;
  handlerPosition?: handlerPosition;
  needBack?: boolean;
  routeList: INavItem[];
}

@Component
export default class NavBar extends tsc<IProps> {
  /** 面包屑数据 */
  @Prop({ type: Array }) routeList: INavItem[];
  /** 右侧区域内容对齐方式 */
  @Prop({ default: 'right', type: String }) handlerPosition: handlerPosition;
  /** 是否需要返回键 */
  @Prop({ default: false, type: Boolean }) needBack: boolean;
  /** 返回按键传值具体跳转 */
  @Prop({ default: () => {}, type: Object }) backGotoItem: IRouteBackItem;

  get position() {
    const positionMap = {
      left: 'flex-start',
      center: 'center',
      right: 'flex-end',
    };
    return positionMap[this.handlerPosition] ?? 'flex-start';
  }
  render() {
    return (
      <div class='app-nav-bar-wrap'>
        <CommonNavBar
          class='nav-route'
          backGotoItem={this.backGotoItem}
          needBack={this.needBack}
          needShadow={true}
          routeList={this.routeList}
        />
        <div
          style={{
            'justify-content': this.position,
          }}
          class='app-nav-bar-handler'
        >
          {this.$slots.handler}
        </div>
      </div>
    );
  }
}
