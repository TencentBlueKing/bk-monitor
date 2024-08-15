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

import { getHostInfo } from 'monitor-api/modules/scene_view';

import introduce from '../../../common/introduce';
import GuidePage from '../../../components/guide-page/guide-page';
import { destroyTimezone } from '../../../i18n/dayjs';
import CommonNavBar from '../../monitor-k8s/components/common-nav-bar';
import CommonPage from '../../monitor-k8s/components/common-page';

import type { INavItem, IViewOptions } from '../../monitor-k8s/typings';

import './performance-detail.scss';

Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);
@Component
export default class PerformanceDetail extends tsc<object> {
  @Prop({ type: [String, Number], default: '' }) id: string;
  @Prop({ type: [String, Number], default: '' }) process: string;
  @Prop({ type: String, default: '' }) title: string;

  viewOptions: IViewOptions = {};
  // 导航条设置
  routeList: INavItem[] = [];
  loading = true;
  get showGuidePage() {
    return introduce.getShowGuidePageByRoute(this.$route.meta?.navId);
  }
  // route navbar title change
  headerTitleChange(v: string, data?: any) {
    if (data?.ip && typeof data.bk_cloud_id !== 'undefined') {
      this.viewOptions = {
        filters: {
          bk_target_cloud_id: data.bk_cloud_id,
          bk_target_ip: data.ip,
          bk_host_id: data.bk_host_id,
        },
      };
    }
    if (this.id.toString() === v.toString()) return;
    this.routeList[this.routeList.length - 1].name = v;
  }
  beforeRouteEnter(to, from, next) {
    next(async (vm: PerformanceDetail) => {
      if (vm.showGuidePage) return;
      const isOldIpv4 = vm.id.toString().includes('-');
      let params = {};
      if (isOldIpv4) {
        const list = vm.id.split('-');
        params = { ip: list[0], bk_cloud_id: list[1] };
      } else {
        params = { bk_host_id: vm.id };
      }
      vm.loading = true;
      const { bk_os_type, bk_cloud_id, ip, bk_host_id, display_name } = await getHostInfo(params)
        .then(data => ({ ...data }))
        .catch(() => ({
          bk_os_type: '',
        }));
      vm.routeList = [
        {
          id: '',
          name: display_name || ip,
        },
      ];
      vm.viewOptions = {
        filters: {
          bk_target_cloud_id: bk_cloud_id,
          bk_target_ip: ip,
          bk_host_id,
        },
        variables: vm.process
          ? {
              display_name: vm.process,
            }
          : {},
        matchFields: !vm.process
          ? {
              os_type: bk_os_type,
            }
          : {},
      };
      vm.loading = false;
    });
  }
  beforeRouteLeave(to, from, next) {
    destroyTimezone();
    next();
  }

  handleBack() {
    if (window.history.length <= 1) {
      this.$router.push({
        name: 'performance',
      });
    } else {
      this.$router.back();
    }
  }

  render() {
    if (this.showGuidePage) return <GuidePage guideData={introduce.data.performance.introduce} />;
    return (
      <div
        class='performance-detail'
        v-monitor-loading={{ isLoading: this.loading }}
      >
        {!this.loading && (
          <CommonPage
            defalutMethod={'MAX'}
            defaultViewOptions={this.viewOptions}
            sceneId={this.viewOptions.variables?.display_name ? 'process' : 'host'}
            sceneType={'detail'}
            onTitleChange={this.headerTitleChange}
          >
            <CommonNavBar
              slot='nav'
              callbackRouterBack={this.handleBack}
              navMode={'share'}
              needBack={true}
              needShadow={true}
              routeList={this.routeList}
              needCopyLink
            />
          </CommonPage>
        )}
      </div>
    );
  }
}
