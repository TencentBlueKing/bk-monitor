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
import { Component, Provide, ProvideReactive } from 'vue-property-decorator';

import { collectingTargetStatus } from 'monitor-api/modules/datalink';
// import { collectingTargetStatus } from 'monitor-api/modules/datalink';
import { random } from 'monitor-common/utils/index';

import authorityMixinCreate from '../../../mixins/authorityMixin';
import * as collectAuth from '../authority-map';
import CollectorStatusDetails from '../collector-detail/collector-status-details';
import { STATUS_LIST } from './utils';

import './collector-operate-detail.scss';

@Component
export default class CollectorOperateDetail extends authorityMixinCreate(collectAuth) {
  @ProvideReactive('authority') authority: { [propsName: string]: boolean } = {};
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Provide('authorityMap') authorityMap = collectAuth;

  id = '';

  data = null;
  updateKey = random(8);

  loading = false;
  needPolling = true;
  pollingCount = 1;
  timer = null;

  created() {
    this.id = this.$route.params.id;
    this.getHosts(this.pollingCount);
  }
  beforeDestroy() {
    window.clearTimeout(this.timer);
  }
  getHosts(count) {
    return collectingTargetStatus({ collect_config_id: this.id })
      .then(data => {
        if (count !== this.pollingCount) return;
        this.data = data;
        this.needPolling = data.contents.some(item => item.child.some(set => STATUS_LIST.includes(set.status)));
        if (!this.needPolling) {
          window.clearTimeout(this.timer);
        } else if (count === 1) {
          this.handlePolling();
        }
        this.updateKey = random(8);
      })
      .catch(() => {});
  }
  handlePolling(v = true) {
    if (v) {
      this.timer = setTimeout(() => {
        clearTimeout(this.timer);
        this.pollingCount += 1;
        this.getHosts(this.pollingCount).finally(() => {
          if (!this.needPolling) return;
          this.handlePolling();
        });
      }, 10000);
    } else {
      window.clearTimeout(this.timer);
    }
  }

  handleRefreshData() {
    return collectingTargetStatus({ collect_config_id: this.id })
      .then(data => {
        this.data = data;
        this.updateKey = random(8);
      })
      .catch(() => {});
  }

  render() {
    return (
      <div class='collector-operate-detail-page'>
        <CollectorStatusDetails
          data={this.data}
          updateKey={this.updateKey}
          onCanPolling={this.handlePolling}
          onRefresh={this.handleRefreshData}
        />
      </div>
    );
  }
}
