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

import { getAuthorityDetail } from 'monitor-api/modules/iam';

import './auth-component.scss';
export interface IAuthComponentProps {
  actionId: string;
}
@Component
export default class AuthComponent extends tsc<IAuthComponentProps> {
  @Prop() actionId!: string;
  type = '401';
  applyActions = [];
  applyUrl = '';
  isQuery = false;
  @Watch('actionId')
  async onQueryUidChange() {
    if (this.isQuery) return;
    this.applyActions = [];
    if (this.actionId) {
      this.isQuery = true;
      const data = await getAuthorityDetail(
        {
          action_ids: Array.isArray(this.actionId) ? this.actionId : [this.actionId],
          space_uid: window.space_uid || undefined,
          bk_biz_id: !window.space_uid ? window.bk_biz_id || window.cc_biz_id : undefined,
        },
        { needMessage: false }
      ).catch(e => {
        console.error(e);
        return false;
      });
      if (data) {
        this.applyActions = data.authority_list?.actions;
        this.applyUrl = data.apply_url;
      }
      this.isQuery = false;
    }
  }
  mounted() {
    this.onQueryUidChange();
  }
  handleGotoApply() {
    if (!this.applyUrl) return;
    try {
      if (self === top) {
        window.open(this.applyUrl, '_blank');
      } else {
        top.BLUEKING.api.open_app_by_other('bk_iam', this.applyUrl);
      }
    } catch {
      window.open(this.applyUrl, '_blank');
    }
  }
  getResource(resources) {
    if (resources.length === 0) {
      return ['--'];
    }
    const data = [];
    for (const resource of resources) {
      if (resource.instances.length > 0) {
        const instances = resource.instances
          .map(instanceItem => instanceItem.map(item => `[${item.id}]${item.name}`).join('，'))
          .join('，');
        const resourceItemData = `${resource.type_name}：${instances}`;
        data.push(resourceItemData);
      }
    }
    return data;
  }
  render() {
    return (
      <div class='exception-page'>
        <bk-exception
          class='exception-page-img'
          type='403'
        >
          <div class='exception-title'>
            {this.$t('您没有该资源的权限，请先申请或联系管理员!')}
            <bk-button
              class='exception-btn'
              theme='primary'
              onClick={this.handleGotoApply}
            >
              {this.$t('去申请')}
            </bk-button>
          </div>
          <table class='permission-table table-header'>
            <thead>
              <tr>
                <th width='30%'>{this.$t('需要申请的权限')}</th>
                <th width='50%'>{this.$t('关联的资源实例')}</th>
              </tr>
            </thead>
          </table>
          <div class='table-content'>
            <table class='permission-table'>
              <tbody>
                {this.applyActions?.map((action, index) => (
                  <tr key={`${index}__1`}>
                    <td width='30%'>{action.name}</td>
                    <td
                      key={`${index}__2`}
                      width='50%'
                    >
                      {this.getResource(action.related_resource_types)?.map((reItem, reIndex) => (
                        <p
                          key={reIndex}
                          class='resource-type-item'
                        >
                          {reItem}
                        </p>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </bk-exception>
      </div>
    );
  }
}
