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

import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { Button, Dialog, Input } from 'bk-magic-vue';

import { Debounce } from '../../../monitor-common/utils/utils';
import GuidePage from '../../../monitor-pc/components/guide-page/guide-page';
import AlarmTools from '../../../monitor-pc/pages/monitor-k8s/components/alarm-tools';
import { INavItem } from '../../../monitor-pc/pages/monitor-k8s/typings';
import introduceData from '../../../monitor-pc/router/space';
import { PanelModel } from '../../../monitor-ui/chart-plugins/typings';
import ListMenu, { IMenuItem } from '../../components/list-menu/list-menu';

import NavBar from './nav-bar';

import './app-list-new.scss';

@Component
export default class AppList extends tsc<{}> {
  routeList: INavItem[] = [
    {
      id: '',
      name: 'APM'
    }
  ];

  /** 显示引导页 */
  showGuidePage = false;

  // menu list
  menuList: IMenuItem[] = [
    {
      id: 'help-docs',
      name: window.i18n.tc('帮助文档')
    }
  ];

  /** 是否显示帮助文档弹窗 */
  showGuideDialog = false;
  /** 搜索关键词 */
  searchKeyword = '';
  /* 是否展开 */
  isExpan = false;

  get alarmToolsPanel() {
    const data = {
      title: this.$t('应用列表'),
      type: 'dict',
      targets: [
        {
          datasource: 'apm',
          dataType: 'dict',
          api: 'scene_view.getStrategyAndEventCount',
          data: {
            scene_id: 'apm'
          }
        }
      ]
    };
    return new PanelModel(data as any);
  }
  get apmIntroduceData() {
    const apmData = introduceData['apm-home'];
    apmData.is_no_source = false;
    apmData.data.buttons[0].url = window.__POWERED_BY_BK_WEWEB__ ? '#/apm/application/add' : '#/application/add';
    return apmData;
  }

  /** 展示添加弹窗 */
  handleAddApp() {
    // this.pluginId = opt.id;
    // this.showAddDialog = true;
    this.$router.push({
      name: 'application-add'
    });
  }

  /** 设置打开帮助文档 */
  handleSettingsMenuSelect(option) {
    if (option.id === 'help-docs') {
      this.showGuideDialog = true;
    }
  }

  /** 关闭弹窗 */
  handleCloseGuideDialog() {
    this.showGuideDialog = false;
  }

  /** 列表搜索 */
  @Debounce(300)
  handleSearch() {
    //
  }

  /**
   * @description 展开收起
   */
  handleExpanChange() {
    this.isExpan = !this.isExpan;
  }

  render() {
    return (
      <div class='app-list-wrap-page'>
        <NavBar routeList={this.routeList}>
          {!this.showGuidePage && (
            <div
              slot='handler'
              class='dashboard-tools-wrap'
            >
              <AlarmTools
                class='alarm-tools'
                panel={this.alarmToolsPanel}
              />
              <bk-button
                size='small'
                theme='primary'
                onClick={this.handleAddApp}
              >
                <span class='app-add-btn'>
                  <i class='icon-monitor icon-mc-add app-add-icon'></i>
                  <span>{this.$t('新建应用')}</span>
                </span>
              </bk-button>
              <ListMenu
                list={this.menuList}
                onMenuSelect={this.handleSettingsMenuSelect}
              >
                <i class='icon-monitor icon-mc-more-tool' />
              </ListMenu>
            </div>
          )}
        </NavBar>

        <div class='app-list-main'>
          {this.showGuidePage ? (
            <GuidePage
              guideId='apm-home'
              guideData={this.apmIntroduceData}
            />
          ) : (
            <div class='app-list-content'>
              <div class='app-list-content-top'>
                <Button onClick={this.handleExpanChange}>
                  {this.isExpan ? (
                    <span class='icon-monitor icon-mc-full-screen'></span>
                  ) : (
                    <span class='icon-monitor icon-mc-merge'></span>
                  )}
                  <span>{this.isExpan ? this.$t('全部展开') : this.$t('全部收起')}</span>
                </Button>
                <Input
                  class='app-list-search'
                  placeholder={this.$t('输入搜索或筛选')}
                  v-model={this.searchKeyword}
                  clearable
                  onInput={this.handleSearch}
                ></Input>
              </div>
            </div>
          )}
        </div>

        <Dialog
          value={this.showGuideDialog}
          mask-close={true}
          ext-cls='guide-create-dialog'
          width={1360}
          show-footer={false}
          on-cancel={this.handleCloseGuideDialog}
        >
          <GuidePage
            marginless
            guideId='apm-home'
            guideData={this.apmIntroduceData}
          />
        </Dialog>
      </div>
    );
  }
}
