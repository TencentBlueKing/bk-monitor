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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { fetchBusinessInfo } from '../../../monitor-api/modules/commons';
import { handleGotoLink } from '../../common/constant';
import { ETagsType } from '../biz-select/list';

import './access-request-dialog.scss';

interface IBusinessInfo {
  bk_biz_id: number;
  bk_biz_name: string;
  space_type_id: string;
  space_code: string;
  operator: string[];
  get_access_url: string;
  new_biz_apply: string;
}

@Component
export default class AccessRequestDialog extends tsc<{}> {
  // 原先跳转到 权限申请 的链接
  @Prop({ type: String, default: '' })
  originAccessURL: string;
  bizId = '';
  // 控制弹窗开启
  visible = false;

  bizName = '';
  spaceType = '';
  getAccessUrl = '';
  spaceCode = '';

  // 管理员列表
  administrators: string[] = [];

  get administratorList(): string {
    return this.administrators.reduce((accumulator, currentValue) => {
      if (accumulator) return `${accumulator}、${currentValue}`;
      return currentValue;
    }, '');
  }
  @Watch('originAccessURL')
  handleOriginAccessURLChange() {
    fetchBusinessInfo({
      bk_biz_id: this.bizId || window.cc_biz_id
    })
      .then((response: IBusinessInfo) => {
        this.administrators = response.operator;
        this.bizName = response.bk_biz_name;
        this.spaceType = response.space_type_id;
        this.getAccessUrl = response.get_access_url;
        this.spaceCode = response.space_code;
      })
      .catch(error => error);
  }

  goToJoinInUserGroup() {
    const url = new URL(this.originAccessURL);
    let name = this.bizName;
    // 蓝盾项目时 直接申请权限
    if (this.spaceType === ETagsType.BKCI && !this.spaceCode) {
      window.open(this.getAccessUrl, '_blank');
      return;
    }
    // 蓝鲸应用时 用户组名加上 开发者中心-
    if (this.spaceType === ETagsType.BKSAAS) {
      name = `开发者中心-${this.bizName}`;
    }
    const replacedURL = `${url.protocol}//${url.host}/apply-join-user-group?limit=10&current=1&name=${name}`;
    window.open(replacedURL, '_blank');
  }
  render() {
    return (
      <bk-dialog
        v-model={this.visible}
        width={480}
        show-footer={false}
        draggable={false}
        ext-cls='access-requst-dialog'
        mask-close={false}
      >
        <bk-exception
          type={403}
          scene={'part'}
        >
          <div class='access-request-title'>{window.i18n.t('你当前暂无 {0} 业务权限', [this.bizName])}</div>
          <div class='access-request-container'>
            <div>
              <div class='access-request-sub-title'>{window.i18n.t('可以按照以下方式进行申请')}</div>
              <div class='single-line'>
                <span style='margin-right: 10px;'>1. {window.i18n.t('推荐加入该业务的用户组，查询')}</span>
                <bk-link
                  disabled={!this.bizName}
                  theme='primary'
                  onClick={() => this.goToJoinInUserGroup()}
                >
                  {window.i18n.t('{0} 用户组', [this.bizName])}
                </bk-link>
              </div>
              <div class='single-line'>
                2. {window.i18n.t('找不到相应用户组时，请联系管理员：')}
                {this.administratorList}
              </div>
              <div class='single-line'>
                <span style='margin-right: 10px;'>3. {window.i18n.t('查看')}</span>
                <bk-link
                  theme='primary'
                  onClick={() => handleGotoLink('accessRequest')}
                >
                  {window.i18n.t('权限申请文档')}
                </bk-link>
              </div>
            </div>
          </div>
        </bk-exception>
      </bk-dialog>
    );
  }
}
