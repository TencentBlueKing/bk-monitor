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

import Component from 'vue-class-component';
import { TranslateResult } from 'vue-i18n';
import { Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import ViewParam from './view-param.vue';

import './history-dialog.scss';

interface IHistoryDialogProps {
  title?: string;
  list?: { label: string | TranslateResult; value: (string | number)[] | (string | number) }[];
  showCallback?: () => Promise<void> | void;
}

@Component({
  components: {
    ViewParam
  }
})
export default class HistoryDialog extends tsc<IHistoryDialogProps> {
  @Prop({ type: Function }) showCallback: () => Promise<void> | void;
  @Prop({ type: Array }) list: IHistoryDialogProps['list'];
  @Prop({ type: String, default: window.i18n.t('变更记录') }) title: string;

  visible = false;

  handleHistoryClick() {
    if (this.showCallback) {
      const res = this.showCallback();
      if (res instanceof Promise && res.then) {
        res.then(() => {
          this.visible = true;
        });
      } else {
        this.visible = true;
      }
    } else {
      this.visible = true;
    }
  }

  render() {
    return (
      <div
        class='history-container'
        onClick={this.handleHistoryClick}
        v-bk-tooltips={{ content: this.title, allowHTML: false }}
      >
        <span class='icon-monitor icon-lishijilu icon'></span>
        <ViewParam
          title={this.title}
          visible={this.visible}
          list={this.list}
          on={{ 'update:visible': val => (this.visible = val) }}
        >
          {this.$slots.default && <template slot='default'>{this.$slots.default}</template>}
        </ViewParam>
      </div>
    );
  }
}
