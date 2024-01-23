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
import { Component, Emit, Inject, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listStickySpaces } from '../../../../monitor-api/modules/commons';
import {
  createDashboardOrFolder,
  deleteDashboard,
  deleteFolder,
  getDashboardList,
  getDirectoryTree,
  renameFolder,
  starDashboard,
  unstarDashboard
} from '../../../../monitor-api/modules/grafana';
import bus from '../../../../monitor-common/utils/event-bus';
import { deepClone, random } from '../../../../monitor-common/utils/utils';
import BizSelect from '../../../components/biz-select/biz-select';
import Collapse from '../../../components/collapse/collapse';
import EmptyStatus from '../../../components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../../components/empty-status/types';
import { ISpaceItem } from '../../../types';
import { WATCH_SPACE_STICKY_LIST } from '../../app';

import FavList, { IFavListItem } from './fav-list';
import IconBtn, { IIconBtnOptions } from './icon-btn';
import { IMoreData } from './tree-list';
import TreeMenu from './tree-menu';
import { ITreeMenuItem, TreeMenuItem } from './utils';

import './dashboard-aside.scss';

export const GRAFANA_HOME_ID = 'home';
interface IProps {
  bizIdList: ISpaceItem[];
}
interface ILinkItem {
  icon: string;
  tips: string;
  router: string;
  usePath?: boolean;
}
interface IEvents {
  onSelectedFav: IFavListItem;
  onSelectedDashboard: TreeMenuItem;
  onBizChange: number;
  onOpenSpaceManager?: void;
}
interface IFormData {
  name: string;
  dir: number | string;
}

export enum MoreType {
  dashboard /** 仪表盘 */,
  dir /** 目录 */,
  import /** 导入 */,
  imports /** 批量导入 */,
  delete /** 删除 */,
  fav /** 收藏 */,
  unfav /** 取消收藏 */,
  export /** 导出 */,
  rename /** 重命名 */
}
type FormType = MoreType.dashboard | MoreType.dir;
@Component
export default class DashboardAside extends tsc<IProps, IEvents> {
  @Prop({ type: Array, default: () => [] }) bizIdList: ISpaceItem[];
  @Ref() dashboardForm: any;
  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('authorityMap') authorityMap;
  bizId = window.cc_biz_id;
  /** 搜索框激活状态 */
  searchActive = false;
  keywork = '';
  showAddForm = false;
  curFormType: FormType = MoreType.dir;
  /** 选中的仪表盘 */
  checked: string = null;
  /** 外链数据 */
  linkList: ILinkItem[] = [
    {
      icon: 'icon-mc-youjian',
      tips: window.i18n.tc('route-邮件订阅'),
      router: 'email-subscriptions'
    },
    {
      icon: 'icon-mc-history',
      tips: window.i18n.tc('route-发送历史'),
      router: 'email-subscriptions-history'
    },
    process.env.APP !== 'external'
      ? {
          icon: 'icon-menu-export',
          tips: window.i18n.tc('批量导入'),
          router: 'export-import'
        }
      : undefined,
    {
      icon: 'icon-shezhi',
      tips: window.i18n.tc('route-仪表盘设置'),
      router: 'grafana-datasource'
    }
  ].filter(Boolean);

  /** 我的收藏列表 */
  favList = [];
  /** 仪表盘列表 */
  grafanaList: ITreeMenuItem[] = [];
  /** 置顶的空间列表 */
  spacestickyList: string[] = [];

  /** 新增操作选项 */
  get addOptions(): IIconBtnOptions[] {
    return [
      {
        id: MoreType.dashboard,
        name: window.i18n.tc('仪表盘'),
        hasAuth: this.authority.NEW_DASHBOARD_AUTH,
        action_id: this.authorityMap.NEW_DASHBOARD_AUTH
      },
      {
        id: MoreType.dir,
        name: window.i18n.tc('目录'),
        hasAuth: this.authority.NEW_DASHBOARD_AUTH,
        action_id: this.authorityMap.NEW_DASHBOARD_AUTH
      },
      {
        id: MoreType.import,
        name: window.i18n.tc('导入'),
        hasAuth: this.authority.NEW_DASHBOARD_AUTH,
        action_id: this.authorityMap.NEW_DASHBOARD_AUTH
      },
      process.env.APP !== 'external'
        ? {
            id: MoreType.imports,
            name: window.i18n.tc('批量导入'),
            hasAuth: this.authority.NEW_DASHBOARD_AUTH,
            action_id: this.authorityMap.NEW_DASHBOARD_AUTH
          }
        : undefined
    ].filter(Boolean);
  }

  /**
   * 新增仪表盘、目录表单
   */
  formData: IFormData = {
    name: '',
    dir: null
  };
  /**
   * 表单校验规则
   */
  formRules = {
    name: [{ required: true, message: window.i18n.tc('必填项'), trigger: 'blur' }],
    dir: [{ required: true, message: window.i18n.tc('必填项'), trigger: 'blur' }]
  };
  loading = false;

  emptyStatusType: EmptyStatusType = 'empty';

  /** 搜索结果列表 */
  get searchResList(): TreeMenuItem[] {
    if (!this.keywork) return [];
    const res = this.grafanaList.reduce((total, item) => {
      // eslint-disable-next-line max-len
      const res = item.children.filter(
        child => child.title.toLocaleLowerCase().indexOf(this.keywork.toLocaleLowerCase()) > -1
      );
      total = [...total, ...res];
      return total;
    }, []);
    return deepClone(res);
  }

  get isDashboard() {
    return this.curFormType === MoreType.dashboard;
  }

  /** 目录列表 */
  get dirList() {
    return this.grafanaList.reduce((total, item) => {
      if (item.isFolder && item.title && item.uid !== GRAFANA_HOME_ID) {
        total.push({
          id: item.id,
          name: item.title
        });
      }
      return total;
    }, []);
  }
  @Watch('$route.name', { immediate: true })
  handleRouteChange() {
    this.handleResetChecked();
  }
  @Watch('$route.params.url', { immediate: true })
  handleRouteUrlChange() {
    this.handleResetChecked();
  }
  mounted() {
    window.addEventListener('message', this.handleMessage, false);
    this.handleResetChecked();
    this.handleFetchGrafanaTree();
    this.handleFetchFavGrafana();
    this.handleFetchStickyList();
    bus.$on(WATCH_SPACE_STICKY_LIST, this.handleWatchSpaceStickyList);
  }
  beforeDestroy() {
    window.removeEventListener('message', this.handleMessage, false);
    bus.$off(WATCH_SPACE_STICKY_LIST);
  }

  /**
   * 接收空间uid
   * @param list 空间uid
   */
  handleWatchSpaceStickyList(list: string[]) {
    this.spacestickyList = list;
  }
  /**
   * 获取置顶列表
   */
  async handleFetchStickyList() {
    const params = {
      username: this.$store.getters.userName
    };
    const res = await listStickySpaces(params).catch(() => []);
    this.spacestickyList = res;
  }

  handleMessage(e: any) {
    if (e?.data?.starredChange) {
      this.handleFetchGrafanaTree();
      this.handleFetchFavGrafana();
    }
  }
  handleResetChecked() {
    if (this.$store.getters.bizIdChangePedding) {
      const list = this.$store.getters.bizIdChangePedding?.split('/') || [];
      this.checked = list.length < 2 ? GRAFANA_HOME_ID : list[2] || GRAFANA_HOME_ID;
    } else if (this.$route.name === 'grafana-home') {
      this.checked = GRAFANA_HOME_ID;
    } else if (this.$route.name === 'favorite-dashboard') {
      this.checked = this.$route.params?.url || '';
    } else {
      this.checked = random(10);
    }
  }
  /**
   * 获取仪表盘数据
   */
  async handleFetchGrafanaTree() {
    const list = await getDirectoryTree().catch(() => {
      this.emptyStatusType = '500';
      return [];
    });
    this.grafanaList = this.handleGrafanaTreeData(list);
    this.grafanaList.unshift({
      id: 99999,
      title: 'Home',
      uid: GRAFANA_HOME_ID,
      icon: 'icon-mc-grafana-home',
      isFolder: false,
      isStarred: false,
      children: []
    });
  }

  /**
   * 处理仪表盘接口返回的数据
   * @param list
   * @returns
   */
  handleGrafanaTreeData(list: Array<any>): ITreeMenuItem[] {
    return list.map(item => {
      const { id, title, dashboards = [], uid = '', isStarred = false } = item;
      return {
        id,
        title,
        uid,
        isStarred,
        isFolder: Object.prototype.hasOwnProperty.call(item, 'dashboards'),
        editable: item.editable ?? true,
        children: this.handleGrafanaTreeData(dashboards)
      };
    });
  }

  /**
   * 获取我的收藏列表
   */
  async handleFetchFavGrafana() {
    const list = await getDashboardList();
    const favList = [
      {
        id: 3,
        name: this.$tc('我的收藏'),
        children: []
      }
    ];
    favList[0].children = list.reduce((total, item) => {
      if (item.is_starred)
        total.push({
          id: item.id,
          name: item.name,
          uid: item.uid
        });
      return total;
    }, []);
    this.favList = favList;
    this.grafanaList = this.grafanaList || [];
  }

  /**
   * 选中收藏数据
   * @param item 收藏数据项
   */
  @Emit('selectedFav')
  handleSelectedFav(item: IFavListItem) {
    this.checked = item.uid;
    return item;
  }
  async handleUnstarred(id: number, name: string) {
    const res = await unstarDashboard({ dashboard_id: id })
      .then(() => true)
      .catch(() => false);
    if (res) {
      this.$bkMessage({ message: `${this.$t('取消收藏成功')}：${name}`, theme: 'success' });
      this.handleFetchGrafanaTree();
      this.handleFetchFavGrafana();
    }
  }

  @Emit('selectedDashboard')
  handleSelectedGrafana(item: TreeMenuItem) {
    this.checked = item.uid;
    return item;
  }

  handleSearchHit(item: TreeMenuItem): string {
    const keywork = this.keywork.toLocaleLowerCase();
    return item.title.replace(new RegExp(`(${keywork})`, 'i'), '<span class="highlight">$1</span>');
  }

  /**
   * 仪表盘的更多操作
   */
  handleTreeMore(data: IMoreData) {
    switch (data.option.id) {
      case MoreType.dashboard:
      case MoreType.dir:
        this.handleShowAddFrom(data);
        break;
      case MoreType.delete:
        this.handleDelete(data.item);
        break;
      case MoreType.fav:
        this.handleFavDashboard(data);
        break;
      case MoreType.unfav:
        this.handleUnFavDashboard(data);
        break;
      case MoreType.export:
        this.handleExportDashboard(data);
        break;
      default:
        break;
    }
  }

  /**
   * 删除仪表盘、目录
   * @param item
   */
  async handleDelete(item: IMoreData['item']) {
    if (item.isGroup) {
      /** 删除目录 */
      if (!!item.children.length) {
        this.$bkMessage({ message: this.$t('先删除该目录下的所有仪表盘'), theme: 'error' });
      } else if (!item.children.length) {
        this.$bkInfo({
          title: this.$t('确认删除目录？'),
          subTitle: item.title,
          confirmLoading: true,
          confirmFn: async () => {
            const res = await deleteFolder({ uid: item.uid })
              .then(() => true)
              .catch(() => false);
            if (res) {
              this.$bkMessage({ message: this.$t('目录删除成功'), theme: 'success' });
              this.handleFetchGrafanaTree();
            }
          }
        });
      }
    } else {
      /** 删除仪表盘 */
      this.$bkInfo({
        title: this.$t('确认删除仪表盘？'),
        subTitle: item.title,
        confirmLoading: true,
        confirmFn: async () => {
          const res = await deleteDashboard({ uid: item.uid })
            .then(() => true)
            .catch(() => false);
          if (res) {
            this.$bkMessage({ message: this.$t('仪表盘删除成功'), theme: 'success' });
            this.handleFetchGrafanaTree();
          }
        }
      });
    }
  }
  /**
   * 新增操作
   * @param item
   */
  handleAdd(item: IIconBtnOptions) {
    switch (item.id) {
      case MoreType.dashboard:
      case MoreType.dir:
        this.handleShowAddFrom(null, item);
        break;
      case MoreType.imports:
        this.handleImportsDashboard();
        break;
      case MoreType.import:
        this.handleImportDashboard();
        break;
      default:
        break;
    }
  }
  /**
   * 跳转批量导入
   */
  handleImportsDashboard() {
    this.$router.push({
      name: 'import-configuration-upload'
    });
  }

  /**
   * 挑战grafana导入
   */
  handleImportDashboard() {
    this.$router.push({
      path: '/grafana/import'
    });
  }

  /**
   * 收藏仪表盘
   * @param data
   */
  async handleFavDashboard(data: IMoreData) {
    if (data.item.isDashboard) {
      const res = await starDashboard({
        dashboard_id: data.item.id
      })
        .then(() => true)
        .catch(() => false);
      if (res) {
        this.$bkMessage({ message: `${this.$t('收藏成功')}：${data.item.title}`, theme: 'success' });
        this.handleFetchGrafanaTree();
        this.handleFetchFavGrafana();
      }
    }
  }
  /**
   * 取消收藏仪表盘
   * @param data
   */
  async handleUnFavDashboard(data: IMoreData) {
    if (data.item.isDashboard) {
      this.handleUnstarred(data.item.id, data.item.title);
    }
  }
  handleShowAddFrom(data: IMoreData, opt?: IIconBtnOptions) {
    const { option = opt, item } = data || {};
    this.formData.dir = item?.isGroup && !!item?.isFolder ? item?.id : '';
    this.showAddForm = true;
    this.curFormType = option.id as FormType;
  }

  /** 表单校验 */
  handleValidate(): Promise<boolean> {
    return this.dashboardForm
      .validate()
      .then(() => true)
      .catch(() => false);
  }

  /**
   * 新增他提交
   */
  async handleConfirm() {
    this.loading = true;
    const isPass = await this.handleValidate();
    if (isPass) {
      const api = this.isDashboard ? this.handleAddDashboard : this.handleAddFolder;
      const isSuccess = await api().catch(() => false);
      if (isSuccess) {
        this.showAddForm = false;
        this.handleFetchGrafanaTree();
      }
    }
    this.loading = false;
  }
  /**
   * 新增仪表盘
   */
  handleAddDashboard() {
    const params = {
      title: this.formData.name,
      folderId: this.formData.dir,
      type: 'dashboard'
    };
    return createDashboardOrFolder(params)
      .then(() => true)
      .catch(() => false);
  }
  /**
   * 新增目录
   */
  handleAddFolder() {
    const params = {
      title: this.formData.name,
      type: 'folder'
    };
    return createDashboardOrFolder(params)
      .then(() => true)
      .catch(() => false);
  }
  /** 取消新增 */
  handleCancel() {
    this.showAddForm = false;
    this.dashboardForm.clearError();
  }

  handleLinkTo(item: ILinkItem) {
    this.$router.push(item.usePath ? { path: item.router } : { name: item.router });
  }

  /**
   * 目录重命名
   * @param item
   */
  async handleRename(item: TreeMenuItem) {
    const res = await renameFolder({
      uid: item.uid,
      title: item.editValue
    })
      .then(() => true)
      .catch(() => false);
    if (res) {
      item.edit = false;
      item.title = item.editValue;
    }
  }

  handleExportDashboard(data: IMoreData) {
    const { item } = data;
    const checkList = item.isGroup ? item.children.map(child => child.uid) : [item.uid];
    this.$router.push({
      name: 'export-configuration',
      params: {
        dashboardChecked: checkList as any
      }
    });
  }

  handleShowSearch() {
    this.keywork = '';
    this.searchActive = !this.searchActive;
  }

  @Emit('bizChange')
  handleBizChange(bizId: number) {
    return bizId;
  }

  handleOpenSpace() {
    this.$emit('openSpaceManager');
  }

  handleSearchInput(val) {
    this.emptyStatusType = val ? 'search-empty' : 'empty';
  }

  handleEmptyStatusOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.keywork = '';
      return;
    }
    if (type === 'refresh') {
      this.handleFetchGrafanaTree();
      return;
    }
  }

  render() {
    return (
      <div class='grafana-aside'>
        <div class='grafana-aside-main'>
          <div class='grafana-biz'>
            <BizSelect
              value={+this.bizId}
              bizList={this.bizIdList}
              minWidth={380}
              theme={'dark'}
              stickyList={this.spacestickyList}
              onOpenSpaceManager={this.handleOpenSpace}
              onChange={this.handleBizChange}
            />
          </div>
          {!!this.favList.length && (
            <div class='grafana-fav'>
              <FavList
                checked={this.checked}
                list={this.favList}
                onUnstarred={this.handleUnstarred}
                onSelected={this.handleSelectedFav}
              ></FavList>
            </div>
          )}
          <div class='grafana-handle'>
            <div class='grafana-handle-bar'>
              <span
                class='title no-wrap'
                onClick={this.handleShowSearch}
              >
                {this.$t('全部')}
              </span>
              <IconBtn
                iconOnly
                checked={this.searchActive}
                class='search-icon'
                onClick={this.handleShowSearch}
              >
                <bk-icon
                  slot='icon'
                  type='search'
                />
              </IconBtn>
              {process.env.APP !== 'external' && (
                <IconBtn
                  class='no-wrap'
                  title={this.$tc('新增')}
                  options={this.addOptions}
                  onSelected={this.handleAdd}
                >
                  <bk-icon
                    slot='icon'
                    class='add-icon'
                    type='plus'
                  />
                </IconBtn>
              )}
            </div>
            <Collapse
              expand={this.searchActive}
              needCloseButton={false}
            >
              <div class='grafana-handle-main'>
                <bk-input
                  right-icon='bk-icon icon-search'
                  v-model={this.keywork}
                  onInput={this.handleSearchInput}
                ></bk-input>
              </div>
            </Collapse>
          </div>
          {!!this.keywork ? (
            <div class='search-list'>
              {this.searchResList.length ? (
                this.searchResList.map(item => (
                  <div
                    class={`search-item ${this.checked === item.uid ? 'is-active' : ''}`}
                    onClick={() => this.handleSelectedGrafana(item)}
                  >
                    <span class='search-icon'></span>
                    <span
                      class='search-content'
                      domPropsInnerHTML={this.handleSearchHit(item)}
                    ></span>
                  </div>
                ))
              ) : (
                <EmptyStatus
                  type={this.emptyStatusType}
                  onOperation={this.handleEmptyStatusOperation}
                />
              )}
            </div>
          ) : (
            <div class='grafana-list'>
              <TreeMenu
                checked={this.checked}
                data={this.grafanaList}
                defaultExpend={false}
                onMore={this.handleTreeMore}
                onSelected={this.handleSelectedGrafana}
                onRename={this.handleRename}
              ></TreeMenu>
            </div>
          )}
          {
            // #if APP !== 'external'
            <div class='garfana-link'>
              {this.linkList.map(item => (
                <span
                  v-bk-tooltips={{
                    content: item.tips,
                    extCls: 'garfana-link-tips',
                    allowHTML: false
                  }}
                  class={`link-item ${this.$route.meta?.navId === item.router ? 'is-active' : ''}`}
                  onClick={() => this.handleLinkTo(item)}
                >
                  <i class={['icon-monitor', item.icon]}></i>
                </span>
              ))}
            </div>
            // #endif
          }
        </div>
        <bk-dialog
          title={this.$t(this.isDashboard ? '新建仪表盘' : '新增目录')}
          header-position='left'
          width={480}
          zIndex={1}
          ext-cls='dashboard-add-dialog'
          v-model={this.showAddForm}
          show-footer
          onCancel={this.handleCancel}
        >
          <bk-form
            {...{
              props: {
                model: this.formData,
                rules: this.formRules
              }
            }}
            ref='dashboardForm'
            formType='vertical'
          >
            <bk-form-item
              required
              property='name'
              label={this.$t(this.isDashboard ? '仪表盘名称' : '目录名称')}
            >
              <bk-input v-model={this.formData.name}></bk-input>
            </bk-form-item>
            {this.isDashboard && (
              <bk-form-item
                required
                property='dir'
                label={this.$t('所属目录')}
              >
                <bk-select v-model={this.formData.dir}>
                  {this.dirList.map(item => (
                    <bk-option
                      id={item.id}
                      name={item.name}
                    ></bk-option>
                  ))}
                </bk-select>
              </bk-form-item>
            )}
          </bk-form>
          <div
            slot='footer'
            class='dashboard-add-dialog-footer'
          >
            <bk-button
              disabled={this.loading}
              loading={this.loading}
              theme='primary'
              onClick={this.handleConfirm}
            >
              {this.$t('确认')}
            </bk-button>
            <bk-button
              theme='default'
              onClick={this.handleCancel}
            >
              {this.$t('取消')}
            </bk-button>
          </div>
        </bk-dialog>
      </div>
    );
  }
}
