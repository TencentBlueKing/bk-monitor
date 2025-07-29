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

import Viewer from 'monitor-ui/markdown-editor/viewer';

interface IConfigurationViewEvent {
  onShrink: MouseEvent; // 关闭侧栏
}

interface IConfigurationViewProps {
  data: string; // 富文本内容
}

@Component
export default class ConfigurationView extends tsc<IConfigurationViewProps, IConfigurationViewEvent> {
  @Prop({ type: String, default: '' }) data: string;

  @Emit('shrink')
  handleClickShrink(e: MouseEvent) {
    return e;
  }

  render() {
    return (
      <div class='configuration-view'>
        <div class='view-header'>
          <span>{this.$t('使用说明')}</span>
          <i
            class='bk-icon icon-minus detail-shrink'
            onClick={this.handleClickShrink}
          />
        </div>
        <div class='view-content'>
          <Viewer value={this.data} />
        </div>
      </div>
    );
  }
}
