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

import { listStickySpaces } from 'monitor-api/modules/commons';
import {
  copyDashboardToFolder,
  createDashboardOrFolder,
  deleteDashboard,
  deleteFolder,
  getDashboardList,
  getDirectoryTree,
  migrateDashboard,
  renameFolder,
  starDashboard,
  unstarDashboard,
} from 'monitor-api/modules/grafana';
import bus from 'monitor-common/utils/event-bus';
import { Debounce, deepClone, random } from 'monitor-common/utils/utils';

import BizSelect from '../../../components/biz-select/biz-select';
import Collapse from '../../../components/collapse/collapse';
import EmptyStatus from '../../../components/empty-status/empty-status';
import { WATCH_SPACE_STICKY_LIST } from '../../app';
import FavList, { type IFavListItem } from './fav-list';
import IconBtn, { type IIconBtnOptions } from './icon-btn';
import TreeMenu from './tree-menu';

import type { EmptyStatusOperationType, EmptyStatusType } from '../../../components/empty-status/types';
import type { ISpaceItem } from '../../../types';
import type { IMoreData } from './tree-list';
import type { ITreeMenuItem, TreeMenuItem } from './utils';

import './dashboard-aside.scss';

export const GRAFANA_HOME_ID = 'home';
export enum MoreType {
  copy = 9 /** 复制到 */,
  dashboard = 0 /** 仪表盘 */,
  delete = 4 /** 删除 */,
  dir = 1 /** 目录 */,
  export = 7 /** 导出 */,
  fav = 5 /** 收藏 */,
  import = 2 /** 导入 */,
  imports = 3 /** 批量导入 */,
  migrate = 10 /** 迁移 */,
  rename = 8 /** 重命名 */,
  unfav = 6 /** 取消收藏 */,
}
type FormType = MoreType.copy | MoreType.dashboard | MoreType.dir;
interface IEvents {
  onBizChange: number;
  onSelectedDashboard: TreeMenuItem;
  onSelectedFav: IFavListItem;
  onOpenSpaceManager?: () => void;
}
interface IFormData {
  dir: number | string;
  name: string;
}

interface ILinkItem {
  icon: string;
  router: string;
  tips: string;
  usePath?: boolean;
}
interface IProps {
  bizIdList: ISpaceItem[];
}
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
  /** 复制的仪表盘 */
  copiedUid: string = null;
  /** 外链数据 */
  linkList: ILinkItem[] = [
    {
      icon: 'icon-mc-youjian',
      tips: window.i18n.tc('route-邮件订阅'),
      router: 'email-subscriptions',
    },
    {
      icon: 'icon-mc-history',
      tips: window.i18n.tc('route-发送历史'),
      router: 'email-subscriptions-history',
    },
    process.env.APP !== 'external'
      ? {
          icon: 'icon-menu-export',
          tips: window.i18n.tc('批量导入'),
          router: 'export-import',
        }
      : undefined,
    {
      icon: 'icon-shezhi',
      tips: window.i18n.tc('route-仪表盘设置'),
      router: 'grafana-admin',
    },
  ].filter(Boolean);

  /** 我的收藏列表 */
  favList: IFavListItem[] = [];
  /** 仪表盘列表 */
  grafanaList: ITreeMenuItem[] = [];
  /** 置顶的空间列表 */
  spaceStickyList: string[] = [];

  /** 新增操作选项 */
  get addOptions(): IIconBtnOptions[] {
    return [
      {
        id: MoreType.dashboard,
        name: window.i18n.tc('仪表盘'),
        hasAuth: this.authority.NEW_DASHBOARD_AUTH,
        action_id: this.authorityMap.NEW_DASHBOARD_AUTH,
      },
      {
        id: MoreType.dir,
        name: window.i18n.tc('目录'),
        hasAuth: this.authority.NEW_DASHBOARD_AUTH,
        action_id: this.authorityMap.NEW_DASHBOARD_AUTH,
      },
      {
        id: MoreType.import,
        name: window.i18n.tc('导入'),
        hasAuth: this.authority.NEW_DASHBOARD_AUTH,
        action_id: this.authorityMap.NEW_DASHBOARD_AUTH,
      },
      process.env.APP !== 'external'
        ? {
            id: MoreType.imports,
            name: window.i18n.tc('批量导入'),
            hasAuth: this.authority.NEW_DASHBOARD_AUTH,
            action_id: this.authorityMap.NEW_DASHBOARD_AUTH,
          }
        : undefined,
    ].filter(Boolean);
  }

  /**
   * 新增仪表盘、目录表单
   */
  formData: IFormData = {
    name: '',
    dir: null,
  };
  /**
   * 表单校验规则
   */
  formRules = {
    name: [{ required: true, message: window.i18n.tc('必填项'), trigger: 'blur' }],
    dir: [{ required: true, message: window.i18n.tc('必填项'), trigger: 'blur' }],
  };
  loading = false;

  emptyStatusType: EmptyStatusType = 'empty';

  /** 搜索结果列表 */
  get searchResList(): TreeMenuItem[] {
    if (!this.keywork) return [];
    const res = this.grafanaList.reduce((total, item) => {
      const res = item.children.filter(
        child => child.title.toLocaleLowerCase().indexOf(this.keywork.toLocaleLowerCase()) > -1
      );
      total.push(...res);
      return total;
    }, []);
    return deepClone(res);
  }

  get isDashboard() {
    return this.curFormType === MoreType.dashboard;
  }

  get isCopyDashboard() {
    return this.curFormType === MoreType.copy;
  }

  /** 目录列表 */
  get dirList() {
    return this.grafanaList.reduce((total, item) => {
      if (item.isFolder && item.title && item.uid !== GRAFANA_HOME_ID) {
        total.push({
          id: item.id,
          name: item.title,
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
    this.spaceStickyList = list;
  }
  /**
   * 获取置顶列表
   */
  async handleFetchStickyList() {
    const params = {
      username: this.$store.getters.userName,
    };
    const res = await listStickySpaces(params).catch(() => []);
    this.spaceStickyList = res;
  }

  handleMessage(e: any) {
    if (e.origin !== location.origin) {
      return;
    }
    if (e?.data?.starredChange) {
      this.handleFetchGrafanaTree();
      this.handleFetchFavGrafana();
    }
  }
  handleResetChecked() {
    if (this.$store.getters.bizIdChangePending) {
      const list = this.$store.getters.bizIdChangePending?.split('/') || [];
      this.checked = list.length < 2 ? GRAFANA_HOME_ID : list[2] || GRAFANA_HOME_ID;
    } else if (this.$route.name === 'grafana-home') {
      this.checked = GRAFANA_HOME_ID;
    } else if (this.$route.name === 'favorite-dashboard') {
      const list = (this.$route.params?.url || '').split('/') || [];
      this.checked = list[0] || '';
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
      hasPermission: true,
      icon: 'icon-mc-grafana-home',
      isFolder: false,
      isStarred: false,
      children: [],
    });
  }

  /**
   * 处理仪表盘接口返回的数据
   * @param list
   * @returns
   */
  handleGrafanaTreeData(list: Array<any>): ITreeMenuItem[] {
    return list.map(item => {
      const {
        id,
        title,
        dashboards = [],
        uid = '',
        isStarred = false,
        url,
        has_permission: hasPermission = true,
      } = item;
      return {
        id,
        title,
        uid,
        hasPermission,
        isStarred,
        url,
        isFolder: Object.hasOwn(item, 'dashboards'),
        editable: item.editable ?? true,
        children: this.handleGrafanaTreeData(dashboards),
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
        children: [],
      },
    ];
    favList[0].children = list.reduce((total, item) => {
      if (item.is_starred)
        total.push({
          id: item.id,
          name: item.name,
          uid: item.uid,
          url: item.url,
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

  @Debounce(300)
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
      case MoreType.copy:
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
      case MoreType.migrate:
        this.handleMigrateDashboard(data.item);
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
      if (item.children.length) {
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
          },
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
        },
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
      name: 'import-configuration-upload',
    });
  }

  /**
   * 挑战grafana导入
   */
  handleImportDashboard() {
    this.$router.push({
      path: '/grafana/import',
    });
  }

  /**
   * 收藏仪表盘
   * @param data
   */
  async handleFavDashboard(data: IMoreData) {
    if (data.item.isDashboard) {
      const res = await starDashboard({
        dashboard_id: data.item.id,
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
    this.copiedUid = item.uid;
    this.formData.name = (this.isCopyDashboard && item?.title) || '';
  }

  /** 表单校验 */
  handleValidate(): Promise<boolean> {
    return this.dashboardForm
      .validate()
      .then(() => true)
      .catch(() => false);
  }

  /**
   * 新增提交
   */
  async handleConfirm() {
    this.loading = true;
    const isPass = await this.handleValidate();
    if (isPass) {
      const api = this.isDashboard
        ? this.handleAddDashboard
        : this.isCopyDashboard
          ? this.handleCopyDashboard
          : this.handleAddFolder;
      const isSuccess = await api().catch(() => false);
      if (isSuccess) {
        this.showAddForm = false;
        this.handleFetchGrafanaTree();
      }
    }
    this.loading = false;
  }

  /**
   * 迁移仪表盘
   * res.data为空：仪表盘内没有要迁移的旧面板情况
   * res.data.failed_total > 0： 有部分面板迁移失败
   * res.data.success_total：迁移成功的面板数量
   */
  async handleMigrateDashboard(item: IMoreData['item']) {
    this.$bkInfo({
      title: this.$t('确认更新？'),
      subTitle: this.$t('解决grafana升级后组件兼容性问题，不影响数据'),
      confirmLoading: true,
      confirmFn: async () => {
        try {
          const res = await migrateDashboard({ dashboard_uid: item.uid, bk_biz_id: this.bizId });
          const failedTotal = res.failed_total === 0;
          this.$bkMessage({
            message: Object.keys(res).length
              ? this.$t(`更新成功${!failedTotal ? ',部分旧面板更新失败' : ''}`)
              : this.$t('仪表盘内没有要更新的旧面板'),
            theme: failedTotal ? 'success' : 'warning',
          });
          this.handleFetchGrafanaTree();
        } catch (error) {
          this.$bkMessage({ message: error, theme: 'error' });
        }
      },
    });
  }

  /**
   * 新增仪表盘
   */
  handleAddDashboard() {
    const params = {
      title: this.formData.name,
      folderId: this.formData.dir,
      type: 'dashboard',
    };
    return createDashboardOrFolder(params)
      .then(res => {
        this.$bkMessage({ message: `${this.$t('创建成功')}：${res?.title}`, theme: 'success' });
        return true;
      })
      .catch(() => false);
  }
  /**
   * 复制仪表盘
   */
  handleCopyDashboard() {
    const params = {
      dashboard_uid: this.copiedUid,
      folder_id: this.formData.dir,
    };
    return copyDashboardToFolder(params)
      .then(res => {
        const url = res?.imported_url
          ? `${location.origin}${location.pathname}?bizId=${this.$store.getters.bizId}#${res.imported_url}`
          : '';
        url && window.open(url, '_blank');
        return true;
      })
      .catch(rs => {
        rs?.message && this.$bkMessage({ message: `${rs?.message}`, theme: 'error' });
        return false;
      });
  }
  /**
   * 新增目录
   */
  handleAddFolder() {
    const params = {
      title: this.formData.name,
      type: 'folder',
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
      title: item.editValue,
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
        dashboardChecked: checkList as any,
      },
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
              bizList={this.bizIdList}
              minWidth={380}
              stickyList={this.spaceStickyList}
              theme={'dark'}
              value={+this.bizId}
              onChange={this.handleBizChange}
              onOpenSpaceManager={this.handleOpenSpace}
            />
          </div>
          {/* 如果没有收藏仪表盘，就不显示空列表。 */}
          {!!this.favList?.[0]?.children?.length && (
            <div class='grafana-fav'>
              <FavList
                checked={this.checked}
                list={this.favList}
                onSelected={this.handleSelectedFav}
                onUnstarred={this.handleUnstarred}
              />
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
                class='search-icon'
                checked={this.searchActive}
                iconOnly
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
                  options={this.addOptions}
                  title={this.$tc('新增')}
                  onSelected={this.handleAdd}
                >
                  <bk-icon
                    class='add-icon'
                    slot='icon'
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
                  v-model={this.keywork}
                  right-icon='bk-icon icon-search'
                  onInput={this.handleSearchInput}
                />
              </div>
            </Collapse>
          </div>
          {this.keywork ? (
            <div class='search-list'>
              {this.searchResList.length ? (
                this.searchResList.map(item => (
                  <div
                    key={item.uid}
                    class={`search-item ${this.checked === item.uid ? 'is-active' : ''}`}
                    onClick={() => this.handleSelectedGrafana(item)}
                  >
                    <span class='search-icon' />
                    <span
                      class='search-content'
                      domPropsInnerHTML={this.handleSearchHit(item)}
                    />
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
                onRename={this.handleRename}
                onSelected={this.handleSelectedGrafana}
              />
            </div>
          )}
          {
            // #if APP !== 'external'
            <div class='garfana-link'>
              {this.linkList.map((item, index) => (
                <span
                  key={index}
                  class={`link-item ${this.$route.meta?.navId === item.router ? 'is-active' : ''}`}
                  v-bk-tooltips={{
                    content: item.tips,
                    extCls: 'garfana-link-tips',
                    allowHTML: false,
                  }}
                  onClick={() => this.handleLinkTo(item)}
                >
                  <i class={['icon-monitor', item.icon]} />
                </span>
              ))}
            </div>
            // #endif
          }
        </div>
        <bk-dialog
          width={480}
          ext-cls='dashboard-add-dialog'
          v-model={this.showAddForm}
          header-position='left'
          title={this.$t(this.isDashboard ? '新建仪表盘' : this.isCopyDashboard ? '复制仪表盘' : '新增目录')}
          show-footer
          onCancel={this.handleCancel}
        >
          <bk-form
            {...{
              props: {
                model: this.formData,
                rules: this.formRules,
              },
            }}
            ref='dashboardForm'
            formType='vertical'
          >
            {
              <bk-form-item
                label={this.$t(this.isDashboard || this.isCopyDashboard ? '仪表盘名称' : '目录名称')}
                property='name'
                required
              >
                <bk-input
                  v-model={this.formData.name}
                  readonly={this.isCopyDashboard}
                />
              </bk-form-item>
            }
            {(this.isDashboard || this.isCopyDashboard) && (
              <bk-form-item
                label={this.$t(this.isCopyDashboard ? '目标目录' : '所属目录')}
                property='dir'
                required
              >
                <bk-select
                  v-model={this.formData.dir}
                  placeholder={this.$t(`请选择${this.isCopyDashboard ? '目标目录' : '所属目录'}`)}
                  searchable
                >
                  {this.dirList.map(item => (
                    <bk-option
                      id={item.id}
                      key={item.id}
                      name={item.name}
                    />
                  ))}
                </bk-select>
              </bk-form-item>
            )}
          </bk-form>
          <div
            class='dashboard-add-dialog-footer'
            slot='footer'
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
