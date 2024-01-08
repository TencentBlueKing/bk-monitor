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

import { Component, Provide } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { Button, Dialog, Input } from 'bk-magic-vue';

import { deleteApplication, listApplication } from '../../../monitor-api/modules/apm_meta';
import { Debounce } from '../../../monitor-common/utils/utils';
import GuidePage from '../../../monitor-pc/components/guide-page/guide-page';
import type { TimeRangeType } from '../../../monitor-pc/components/time-range/time-range';
import { handleTransformToTimestamp } from '../../../monitor-pc/components/time-range/utils';
import AlarmTools from '../../../monitor-pc/pages/monitor-k8s/components/alarm-tools';
import { IFilterDict, INavItem } from '../../../monitor-pc/pages/monitor-k8s/typings';
import OperateOptions, { IOperateOption } from '../../../monitor-pc/pages/uptime-check/components/operate-options';
import introduceData from '../../../monitor-pc/router/space';
import { PanelModel } from '../../../monitor-ui/chart-plugins/typings';
import ListMenu, { IMenuItem } from '../../components/list-menu/list-menu';
import authorityStore from '../../store/modules/authority';

import * as authorityMap from './authority-map';
import NavBar from './nav-bar';

import './app-list-new.scss';

interface IAppListItem {
  isExpan: boolean;
  app_alias: {
    value: string;
  };
  app_name: string;
  application_id: number;
  firstCode: string;
  permission: {
    [key: string]: boolean;
  };
}

@Component
export default class AppList extends tsc<{}> {
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;

  routeList: INavItem[] = [
    {
      id: '',
      name: 'APM'
    }
  ];
  /** 时间范围 */
  timeRange: TimeRangeType = ['now-1h', 'now'];
  /** 表格列数据项过滤 */
  filterDict: IFilterDict = {};
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
  /* 应用分类数据 */
  appList: IAppListItem[] = [];
  pagination = {
    current: 1,
    limit: 10,
    total: 100
  };

  opreateOptions: IOperateOption[] = [
    {
      id: 'storageState',
      name: window.i18n.t('存储状态'),
      authority: true
    },
    {
      id: 'dataStatus',
      name: window.i18n.t('数据状态'),
      authority: true
    },
    {
      id: 'accessService',
      name: window.i18n.t('接入服务'),
      authority: true
    },
    {
      id: 'noDataAlarm',
      name: window.i18n.t('新增无数据告警'),
      authority: true
    },
    {
      id: 'delete',
      name: window.i18n.t('删除'),
      authority: true
    }
  ];

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

  // eslint-disable-next-line @typescript-eslint/no-dupe-class-members
  handleShowAuthorityDetail(actionIds: string | string[]) {
    authorityStore.getAuthorityDetail(actionIds);
  }

  created() {
    this.getAppList();
  }

  async getAppList() {
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const params = {
      start_time: startTime,
      end_time: endTime,
      keyword: this.searchKeyword,
      sort: '',
      filter_dict: this.filterDict,
      page: this.pagination.current,
      page_size: this.pagination.limit
    };
    const listData = await listApplication(params).catch(() => {
      return {
        data: []
      };
    });
    this.appList = listData.data.map(item => ({
      ...item,
      isExpan: false,
      firstCode: item.app_alias?.value?.slice(0, 1) || ''
    }));
    // 路由同步查询关键字
    const routerParams = {
      name: this.$route.name,
      query: {
        ...this.$route.query,
        queryString: this.searchKeyword
      }
    };
    this.$router.replace(routerParams).catch(() => {});
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
  handleAllExpanChange() {
    this.isExpan = !this.isExpan;
  }

  /** 跳转服务概览 */
  linkToOverview(row) {
    const routeData = this.$router.resolve({
      name: 'application',
      query: {
        'filter-app_name': row.app_name
      }
    });
    window.open(routeData.href);
  }
  /**
   * @description 跳转到配置页
   * @param row
   */
  handleToConfig(row) {
    const routeData = this.$router.resolve({
      name: 'application-config',
      params: {
        id: row.application_id
      }
    });
    window.open(routeData.href);
  }

  /**
   * @description 展开
   * @param row
   */
  handleExpanChange(row: IAppListItem) {
    row.isExpan = !row.isExpan;
  }

  /**
   * @description 更多选项
   * @param id
   * @param row
   */
  handleConfig(id, row) {
    // 存储状态、数据状态、指标维度、新增无数据告警 分别跳到配置页 query: active
    const toConfigKeys = ['storageState', 'dataStatus', 'indicatorDimension', 'noDataAlarm'];
    // 接入服务 /service-add/opentelemetry/apm_test_have_data
    const toAccessService = ['accessService'];
    if (toConfigKeys.includes(id)) {
      const routeData = this.$router.resolve({
        name: 'application-config',
        params: {
          id: row.application_id
        },
        query: {
          active: id === 'noDataAlarm' ? 'dataStatus' : id
        }
      });
      window.open(routeData.href);
    } else if (toAccessService.includes(id)) {
      const routeData = this.$router.resolve({
        name: 'service-add',
        params: {
          appName: row.app_name
        }
      });
      window.open(routeData.href);
    } else if (id === 'delete') {
      this.$bkInfo({
        type: 'warning',
        title: this.$t('确认删除该应用？'),
        maskClose: true,
        escClose: true,
        confirmFn: () => {
          deleteApplication({ app_name: row.app_name }).then(() => {
            this.$bkMessage({ theme: 'success', message: this.$t('删除成功') });
            this.getAppList();
          });
        }
      });
    }
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
                <Button onClick={this.handleAllExpanChange}>
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
              <div class='app-list-content-data'>
                {this.appList.map(item => (
                  <div
                    key={item.application_id}
                    class='item-expan-wrap'
                  >
                    <div
                      class='expan-header'
                      onClick={() => this.handleExpanChange(item)}
                    >
                      <div class='header-left'>
                        <span class={['icon-monitor icon-mc-triangle-down', { expan: item.isExpan }]}></span>
                        <div class='first-code'>
                          <span>{item.firstCode}</span>
                        </div>
                        <div class='biz-name-01'>{item.app_alias?.value}</div>
                        <div class='biz-name-02'>（{item.app_name}）</div>
                        <div class='item-label'>服务数量:</div>
                        <div class='item-content'>
                          <span>58</span>
                        </div>
                        <div class='item-label'>Tracing:</div>
                        <div class='item-content'>
                          <div class='trace-status'>无数据</div>
                        </div>
                        <div class='item-label'>Profiling:</div>
                        <div class='item-content'>
                          <span>正常</span>
                        </div>
                      </div>
                      <div class='header-right'>
                        <Button
                          class='mr-8'
                          size='small'
                          theme='primary'
                          outline
                          onClick={(event: Event) => {
                            event.stopPropagation();
                            this.linkToOverview(item);
                          }}
                        >
                          {this.$t('查看详情')}
                        </Button>
                        <Button
                          class='mr-8'
                          size='small'
                          onClick={(event: Event) => {
                            event.stopPropagation();
                            this.handleToConfig(item);
                          }}
                        >
                          {this.$t('配置')}
                        </Button>
                        <OperateOptions
                          options={{
                            outside: [],
                            popover: this.opreateOptions.map(o => ({
                              ...o,
                              authority: item?.permission[authorityMap.VIEW_AUTH] ?? true,
                              authorityDetail: authorityMap.VIEW_AUTH
                            }))
                          }}
                          onOptionClick={id => this.handleConfig(id, item)}
                        >
                          <div
                            class='more-btn'
                            slot='trigger'
                          >
                            <span class='icon-monitor icon-mc-more'></span>
                          </div>
                        </OperateOptions>
                      </div>
                    </div>
                    {item.isExpan && <div class='expan-content'></div>}
                  </div>
                ))}
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
