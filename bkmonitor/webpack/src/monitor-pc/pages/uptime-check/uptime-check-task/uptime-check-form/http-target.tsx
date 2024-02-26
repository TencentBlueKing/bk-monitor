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
import { MethodType } from 'fta-solutions/pages/setting/set-meal/set-meal-add/components/http-editor/http-editor';
import { isHttpUrl, isIpv6Url } from 'monitor-common/regex/url';

import AddBtn from './add-btn';
import CommonAddDialog from './common-add-dialog';
import HttpUrlInput from './http-url-input';

import './http-target.scss';

export type ProtocolType = 'http' | 'tcp' | 'udp' | 'icmp';
const methodList: MethodType[] = ['GET', 'POST', 'DELETE', 'PUT', 'PATCH'];
interface IHttpTargetProps {
  urls: string[];
  method: MethodType;
}
interface IHttpTargetEvents {
  onUrlChange: string[];
  onMethodChange: MethodType;
}
@Component
export default class HttpTarget extends tsc<IHttpTargetProps, IHttpTargetEvents> {
  @Prop({ default: () => [], type: Array }) urls: string[];
  @Prop({ default: 'GET', type: String }) method: MethodType;
  show = false;
  defaultUrl = '';
  showValidateTips = false;
  methodChange(v: MethodType) {
    this.$emit('methodChange', v);
  }
  addHttpUrl() {
    this.defaultUrl = this.urls.join('\n');
    this.show = true;
  }
  handleConfirm(v: string) {
    const list = v.split('\n').filter(Boolean);
    if (list?.every(url => isHttpUrl(url) || isIpv6Url(url))) {
      this.showValidateTips = false;
      this.$emit('urlChange', list);
      this.show = false;
    } else {
      this.show = true;
      this.showValidateTips = true;
    }
  }
  httpUrlChange(v: string, i: number) {
    const list = this.urls.slice();
    list.splice(i, 1, v);
    this.$emit('urlChange', list);
  }
  httpUrlDelete(i: number) {
    const list = this.urls.slice();
    list.splice(i, 1);
    this.$emit('urlChange', list);
  }
  handleShowChange(v: boolean) {
    this.show = v;
    if (!v) {
      this.showValidateTips = false;
    }
  }
  render() {
    return (
      <div class='http-target'>
        <div class='http-create'>
          <bk-select
            class='http-create-method'
            value={this.method}
            clearable={false}
            popover-width={100}
            onChange={this.methodChange}
          >
            {methodList.map(option => (
              <bk-option
                key={option}
                id={option}
                name={option}
              ></bk-option>
            ))}
          </bk-select>
          <AddBtn
            text={this.$t('添加URL').toString()}
            onClick={this.addHttpUrl}
          />
        </div>
        <div class='http-detail'>
          {this.urls.map((url, i) => (
            <HttpUrlInput
              key={i}
              value={url}
              onDelete={() => this.httpUrlDelete(i)}
              onChange={v => this.httpUrlChange(v, i)}
            />
          ))}
        </div>
        <CommonAddDialog
          defaultValue={this.defaultUrl}
          show={this.show}
          title={this.$t('添加/编辑URL')}
          placeholder={this.$t('输入URL，可通过回车区隔多个URL')}
          showValidateTips={this.showValidateTips}
          validateTips={this.$t('输入正确的url')}
          onShowChange={this.handleShowChange}
          onConfirm={this.handleConfirm}
          onFocus={() => (this.showValidateTips = false)}
        />
      </div>
    );
  }
}
