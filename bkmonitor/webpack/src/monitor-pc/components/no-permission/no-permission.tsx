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
import authorityStore from '../../store/modules/authority';

// 20231205 代码还原，先保留原有部分
// import { showAccessRequest } from '../access-request-dialog';
import './no-permission.scss';

interface AuthorityIDProps {
  actionIds: string | string[];
}

@Component
export default class NoPermission extends tsc<AuthorityIDProps> {
  @Prop({ type: String }) readonly actionIds: string | string;

  getAccess = { url: '', businessName: '', operator: [] };

  @Watch('actionIds')
  async handleGetAuthDetail() {
    if (this.actionIds?.length) {
      const data = await authorityStore.handleGetAuthDetail(this.actionIds).catch(() => ({}));
      this.getAccess.url = data.apply_url || '';
    }
  }
  async created() {
    if (this.actionIds?.length) {
      await this.handleGetAuthDetail();
    }
    if (this.getAccess.url) return;
    const data = await fetchBusinessInfo().catch(() => false);
    this.getAccess = {
      url: data.get_access_url || '',
      operator: data.operator || [],
      businessName: data.bk_biz_name || ''
    };
  }
  handleApply() {
    // 20231205 代码还原，先保留原有部分
    // showAccessRequest(this.getAccess.url);
    window.open(this.getAccess.url);
  }

  render() {
    return (
      <div class='no-permission-component'>
        <div class='lock-icon'></div>
        <div class='title'>{this.$t('无权限访问')}</div>
        <div class='msg'>{this.$t('您没有该资源的权限，请先申请!')}</div>
        <bk-button
          theme='primary'
          class='submit'
          on-click={this.handleApply}
        >
          {this.$t('去申请')}
        </bk-button>
      </div>
    );
  }
}
