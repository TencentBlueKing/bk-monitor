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

import Viewer from 'monitor-ui/markdown-editor/viewer';

import './custom-view.scss';

const MAX_HEIGHT = 100;

interface IProps {
  value?: string;
}

@Component
export default class CustomView extends tsc<IProps> {
  @Prop({ type: String, default: '' }) value: string;

  isExceed = false; // 是否显示收起与展开全部
  isExpan = false; // 是否展开
  height = 'auto';
  viewHeight = 0;

  mounted() {
    setTimeout(() => {
      const height = this.$el.querySelector('.viewer-wrap').clientHeight;
      if (height > MAX_HEIGHT) {
        this.viewHeight = height;
        this.height = `${MAX_HEIGHT}px`;
        this.isExceed = true;
      }
    }, 50);
  }

  handleExpan() {
    this.isExpan = !this.isExpan;
    if (this.isExpan) {
      this.height = `${this.viewHeight}px`;
    } else {
      this.height = `${MAX_HEIGHT}px`;
    }
  }

  render() {
    return (
      <div class='event-detail-custom-view'>
        <div
          style={{
            height: this.height,
          }}
          class='view-content-wrap'
        >
          <div class='viewer-wrap'>
            <Viewer value={this.value} />
          </div>
        </div>
        {this.isExceed && (
          <div
            class='expan-btn'
            onClick={this.handleExpan}
          >
            {this.isExpan ? this.$t('收起') : this.$t('展开全部')}
          </div>
        )}
      </div>
    );
  }
}
