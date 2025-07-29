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

import './navigation-head.scss';

interface IEvents {
  onRightClick?: boolean;
}
interface IProps {
  rightActive?: boolean;
  title?: string;
}

@Component
export default class Navigation extends tsc<IProps, IEvents> {
  @Prop({ type: String, default: '' }) title: string;
  @Prop({ type: Boolean, default: true }) rightActive: boolean;

  active = true;

  created() {
    this.active = this.rightActive;
  }

  @Emit('rightClick')
  handleRightClick() {
    this.active = !this.active;
    return this.active;
  }

  render() {
    return (
      <div class='strategy-page-navigation-head'>
        <span
          class='icon-monitor icon-back-left'
          onClick={() => this.$router.back()}
        />
        <span class='title'>{this.title || this.$t('加载中...')}</span>
        <span
          class={['right-btn', { active: this.active }]}
          onClick={() => this.handleRightClick()}
        >
          <span class='icon-monitor icon-audit' />
        </span>
      </div>
    );
  }
}
