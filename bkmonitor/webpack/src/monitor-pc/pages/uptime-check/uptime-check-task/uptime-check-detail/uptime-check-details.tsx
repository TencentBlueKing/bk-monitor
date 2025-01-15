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
import { Component, InjectReactive, Prop, Provide } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import introduce from '../../../../common/introduce';
import GuidePage from '../../../../components/guide-page/guide-page';
import { destroyTimezone } from '../../../../i18n/dayjs';
import CommonNavBar from '../../../monitor-k8s/components/common-nav-bar';
import CommonPage from '../../../monitor-k8s/components/common-page';
import * as authorityMap from '../../authority-map';

import type { IMenuItem, INavItem, IViewOptions } from '../../../monitor-k8s/typings';

import './uptime-check-detail.scss';

Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);

@Component
export default class UptimeCheckDetail extends tsc<object> {
  @Prop({ type: String, default: '' }) taskId: string;
  @Prop({ type: String, default: '' }) groupId: string;

  @Provide('authority') authority = authorityMap;
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @InjectReactive('readonly') readonly: boolean;
  // 是否显示引导页
  get showGuidePage() {
    return introduce.getShowGuidePageByRoute(this.$route.meta?.navId);
  }
  viewOptions: IViewOptions = {};
  // 导航条设置
  routeList: INavItem[] = [];

  menuList: IMenuItem[] = [
    {
      id: 'task-edit',
      name: window.i18n.tc('数据源管理'),
      show: true,
    },
  ];

  // route navbar title change
  headerTitleChange(v: string) {
    this.routeList[this.routeList.length - 1].name = v;
  }
  beforeRouteEnter(to, from, next) {
    next((vm: UptimeCheckDetail) => {
      if (vm.showGuidePage) return;
      const list = vm.taskId.split('-');
      const groupId = !vm.groupId || vm.groupId === '0' ? undefined : vm.groupId;
      vm.routeList = [
        // {
        //   id: 'uptime-check',
        //   name: window.i18n.tc('服务拨测')
        // },
        // {
        //   id: 'uptime-check',
        //   name: window.i18n.tc('拨测任务'),
        //   query: {
        //     dashboardMode: 'list',
        //     dashboardId: 'uptime-check-task',
        //     key: random(10)
        //   }
        // },
        {
          id: '',
          name: list[0],
        },
      ];
      vm.viewOptions = {
        filters: {
          task_id: vm.taskId,
          group_id: groupId,
        },
      };
    });
  }
  beforeRouteLeave(to, from, next) {
    destroyTimezone();
    next();
  }
  /**
   * 基于当前的配置信息进行拨测任务的新建
   */
  handleToCreateDialTest() {
    this.$router.push({
      name: 'uptime-check-task-add',
      query: {
        taskId: this.$route.query['filter-task_id'],
      },
    });
  }

  handleMenuSelect({ id, param }) {
    if (id === 'task-edit') {
      this.$router.push({
        name: 'uptime-check-task-edit',
        params: {
          id: param.taskId,
        },
      });
    }
  }

  render() {
    if (this.showGuidePage) return <GuidePage guideData={introduce.data['uptime-check'].introduce} />;
    return (
      <div class='uptime-check-detail'>
        <CommonPage
          defaultViewOptions={this.viewOptions}
          menuList={this.menuList}
          sceneId={'uptime_check'}
          sceneType={'detail'}
          onMenuSelect={this.handleMenuSelect}
          onTitleChange={this.headerTitleChange}
        >
          <CommonNavBar
            slot='nav'
            needBack={true}
            needShadow={true}
            routeList={this.routeList}
            needCopyLink
          />
          {!this.readonly && (
            <span slot='dashboardTools'>
              <bk-button
                class='ml15'
                v-authority={{ active: !this.authority.MANAGE_AUTH }}
                icon='plus'
                size='small'
                theme='primary'
                onClick={() =>
                  this.authority.MANAGE_AUTH
                    ? this.handleToCreateDialTest()
                    : this.handleShowAuthorityDetail(authorityMap.MANAGE_AUTH)
                }
              >
                {this.$t('新建拨测')}
              </bk-button>
            </span>
          )}
        </CommonPage>
      </div>
    );
  }
}
