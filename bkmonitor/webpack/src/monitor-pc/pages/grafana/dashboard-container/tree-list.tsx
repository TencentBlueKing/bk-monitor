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
import { Component, Emit, Inject, Prop } from 'vue-property-decorator';
import { modifiers, Component as tsc } from 'vue-tsx-support';

import Collapse from '../../../components/collapse/collapse';
import { GRAFANA_HOME_ID, MoreType } from './dashboard-aside';
import IconBtn, { type IIconBtnOptions } from './icon-btn';

import type { TreeMenuItem } from './utils';

import './tree-list.scss';

interface IProps {
  list: TreeMenuItem[];
  indent?: number;
  checked?: string;
  needAdd?: boolean;
}
interface IEvents {
  onSelected: TreeMenuItem;
  onMore: IMoreData;
  onRename: TreeMenuItem;
}
export interface IMoreData {
  option: IIconBtnOptions;
  item: TreeMenuItem;
}
@Component({
  name: 'TreeList',
})
export default class TreeList extends tsc<IProps, IEvents> {
  @Prop({ type: Array, default: () => [] }) list: TreeMenuItem[];
  /** 层级缩进量 */
  @Prop({ type: Number, default: 16 }) indent: number;
  /** 选中的id */
  @Prop({ type: String }) checked: string;
  /** 是否需要增加功能 */
  @Prop({ type: Boolean, default: true }) needAdd: boolean;
  /** 是否需要更多功能 */
  @Prop({ type: Boolean, default: true }) needMore: boolean;
  @Inject('authority') authority;
  @Inject('authorityMap') authorityMap;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  /** 当前聚焦的数据项id */
  focusId = null;

  actionId = 'view_single_dashboard';

  get moreOptions() {
    return [
      {
        id: MoreType.rename,
        name: window.i18n.tc('重命名'),
        icon: 'icon-bianji',
        style: {
          'font-size': '20px',
        },
        hasAuth: this.authority.NEW_DASHBOARD_AUTH,
        action_id: this.authorityMap.NEW_DASHBOARD_AUTH,
      },
      {
        id: MoreType.export,
        name: window.i18n.tc('导出'),
        icon: 'icon-xiazai1',
        hasAuth: true,
      },
      {
        id: MoreType.delete,
        name: window.i18n.tc('删除'),
        icon: 'icon-mc-delete-line',
        hasAuth: this.authority.NEW_DASHBOARD_AUTH,
        action_id: this.authorityMap.NEW_DASHBOARD_AUTH,
      },
    ];
  }
  get addOptions(): IIconBtnOptions[] {
    return [
      {
        id: MoreType.dashboard,
        name: window.i18n.tc('仪表盘'),
        hasAuth: this.authority.NEW_DASHBOARD_AUTH,
        action_id: this.authorityMap.NEW_DASHBOARD_AUTH,
      },
      // {
      //   id: MoreType.dir,
      //   name: window.i18n.tc('目录'),
      //   hasAuth: this.authority.MANAGE_AUTH,
      //   action_id: this.authorityMap.MANAGE_AUTH
      // }
    ];
  }
  get dashboardMoreOptions() {
    return [
      {
        id: MoreType.export,
        name: window.i18n.tc('导出'),
        icon: 'icon-xiazai1',
        hasAuth: true,
      },
      {
        id: MoreType.fav,
        name: window.i18n.tc('收藏'),
        icon: 'icon-mc-uncollect',
        style: {
          'font-size': '12px',
        },
        hasAuth: true,
      },
      {
        id: MoreType.unfav,
        name: window.i18n.tc('取消收藏'),
        icon: 'icon-mc-collect',
        style: {
          'font-size': '12px',
        },
        hasAuth: true,
      },
      {
        id: MoreType.delete,
        name: window.i18n.tc('删除'),
        icon: 'icon-mc-delete-line',
        hasAuth: true,
      },
      {
        id: MoreType.copy,
        name: window.i18n.tc('复制到'),
        icon: 'icon-mc-copy',
        hasAuth: true,
      },
      {
        id: MoreType.migrate,
        name: window.i18n.tc('更新'),
        icon: 'icon-mc-migrate-tool',
        hasAuth: true,
      },
    ];
  }
  /**
   * 处理不同目录的更多选项
   * @param item
   * @returns
   */
  handleMoreOptions(item: TreeMenuItem) {
    const includesMap = [MoreType.export];
    return this.moreOptions.filter(opt => {
      if (item.isGeneralFolder) {
        return includesMap.includes(opt.id);
      }
      return true;
    });
  }

  /** 当前缩进量 */
  get indentPadding() {
    const [item] = this.list;
    return `${(item.level + 1) * this.indent}px`;
  }

  /** 点击项 */
  handleClickRow(_e: MouseEvent, item: TreeMenuItem) {
    if (item.isGroup) {
      item.expend = !item.expend;
    } else {
      item.hasPermission ? this.handleSelected(item) : this.handleShowAuthorityDialog();
    }
  }

  handleShowAuthorityDialog() {
    this.handleShowAuthorityDetail(this.actionId || this.$route.meta.authority?.MANAGE_AUTH);
  }

  handleMouseenter(item?: TreeMenuItem) {
    this.focusId = item?.id ?? null;
  }

  @Emit('selected')
  handleSelected(item: TreeMenuItem) {
    return item;
  }

  /**
   * 检查目录是否处于激活状态
   * @param flag 前置条件
   * @param item TreeMenuItem
   * @returns boolean
   */
  checkedGroupItemFocus(flag: boolean, item: TreeMenuItem): boolean {
    return flag && item.isGroup && (this.focusId === item.id || item.addActive || item.moreActive) && !item.edit;
  }

  checkedDashboardItemFocus(flag: boolean, item: TreeMenuItem): boolean {
    return flag && !item.isGroup && (this.focusId === item.id || item.addActive || item.moreActive);
  }
  /**
   * 检查仪表盘是否处于激活状态
   * @param flag 前置条件
   * @param item TreeMenuItem
   * @returns boolean
   */
  handleAddActive(show: boolean, item: TreeMenuItem, key: string) {
    item[key] = show;
  }

  handleMoreProxy(opt: IIconBtnOptions, item: TreeMenuItem) {
    switch (opt.id) {
      case MoreType.rename:
        item.edit = true;
        setTimeout(() => {
          const input = this.$refs[`input-${item.id}`] as HTMLInputElement;
          input.focus();
        }, 100);
        break;
      default:
        break;
    }
    this.handleEmitMore({
      option: opt,
      item,
    });
  }

  @Emit('more')
  handleEmitMore(data: IMoreData) {
    return data;
  }
  /**
   * 重命名
   */
  @Emit('rename')
  handleRename(item: TreeMenuItem) {
    // item.edit = false;
    // item.title = item.editValue;
    return item;
  }
  getDashboardMoreOptions(item: TreeMenuItem) {
    return this.dashboardMoreOptions
      .filter(set => {
        if (item.isStarred) {
          return set.id !== MoreType.fav;
        }
        return set.id !== MoreType.unfav;
      })
      .filter(set => {
        if (set.id === MoreType.delete) {
          return item.editable;
        }
        return true;
      });
  }
  render() {
    return (
      <div class='tree-list'>
        {this.list.map(item => (
          <div
            id={item.uid}
            key={item.id}
            class='tree-list-item'
          >
            <div
              style={{ 'padding-left': this.indentPadding }}
              class={[
                'list-item-row',
                {
                  checked: item.uid === this.checked,
                  edit: item.edit,
                  disabled: !item.hasPermission,
                },
              ]}
              v-authority={{ active: !(item.hasPermission || item.isGroup) }}
              onClick={e => this.handleClickRow(e, item)}
              onMouseenter={() => this.handleMouseenter(item)}
              onMouseleave={() => this.handleMouseenter()}
            >
              <span class={['list-item-icon', { 'is-null': !(item.curIcon || item.uid === GRAFANA_HOME_ID) }]}>
                {item.curIcon && <i class={['icon-monitor', item.curIcon]} />}
              </span>
              {item.edit ? (
                <div onClick={modifiers.stop(() => {})}>
                  <bk-input
                    ref={`input-${item.id}`}
                    class='rename-input'
                    v-model={item.editValue}
                    onBlur={() => this.handleRename(item)}
                    onEnter={() => this.handleRename(item)}
                  />
                </div>
              ) : (
                <span
                  class='list-item-name'
                  v-bk-overflow-tips={{ interactive: false }}
                >
                  {item.title}
                </span>
              )}
              {item.hasPermission && process.env.APP !== 'external' && item.uid !== GRAFANA_HOME_ID && (
                <span class='list-item-handle'>
                  {item.isFolder && this.checkedGroupItemFocus(this.needAdd, item) && (
                    <IconBtn
                      checked={item.addActive}
                      options={this.addOptions}
                      iconOnly
                      onSelected={opt => this.handleMoreProxy(opt, item)}
                      onShowChange={show => this.handleAddActive(show, item, 'addActive')}
                    >
                      <i
                        class='icon-monitor icon-mc-add'
                        slot='icon'
                      />
                    </IconBtn>
                  )}
                  {this.checkedGroupItemFocus(this.needMore, item) && (
                    <IconBtn
                      checked={item.moreActive}
                      options={this.handleMoreOptions(item)}
                      iconOnly
                      onSelected={opt => this.handleMoreProxy(opt, item)}
                      onShowChange={show => this.handleAddActive(show, item, 'moreActive')}
                    >
                      <i
                        class='icon-monitor icon-mc-more'
                        slot='icon'
                      />
                    </IconBtn>
                  )}
                  {this.checkedDashboardItemFocus(this.needMore, item) && (
                    <IconBtn
                      checked={item.moreActive}
                      options={this.getDashboardMoreOptions(item)}
                      iconOnly
                      onSelected={opt => this.handleMoreProxy(opt, item)}
                      onShowChange={show => this.handleAddActive(show, item, 'moreActive')}
                    >
                      <i
                        class='icon-monitor icon-mc-more'
                        slot='icon'
                      />
                    </IconBtn>
                  )}
                </span>
              )}
            </div>
            {item.isGroup && (
              <Collapse
                key={`${item.id}-${item.children.length}`}
                expand={item.expend}
                needCloseButton={false}
                renderContent={false}
              >
                <TreeList
                  checked={this.checked}
                  list={item.children}
                  needAdd={this.needAdd}
                  onMore={this.handleEmitMore}
                  onSelected={this.handleSelected}
                />
              </Collapse>
            )}
          </div>
        ))}
      </div>
    );
  }
}
