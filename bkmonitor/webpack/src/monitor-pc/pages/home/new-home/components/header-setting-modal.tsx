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
import { Component, Emit, Mixins, Prop, Watch } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';

import MonitorDialog from 'monitor-ui/monitor-dialog';

import UserConfigMixin from '../../../../mixins/userStoreConfig';
import {
  COMMON_ROUTE_LIST,
  COMMON_ROUTE_STORE_KEY,
  DEFAULT_ROUTE_LIST,
  type IRouteConfigItem,
  getLocalStoreRoute,
} from '../../../../router/router-config';

import './header-setting-modal.scss';

// 定义组件属性接口
interface IHeaderSettingModalProps {
  show: boolean;
}

// 定义组件事件接口
interface IHeaderSettingModalEvent {
  onChange: boolean;
  onConfirm: () => void;
  onStoreRoutesChange: IRouteConfigItem[];
}

@Component
class HeaderSettingModal extends Mixins(UserConfigMixin) {
  // 接收父组件传递的属性，控制模态框显示
  @Prop({ required: true, type: Boolean }) readonly show: boolean;

  // 定义组件内部状态
  flatRoutes: IRouteConfigItem[] = [];
  dragoverId = ''; // 当前拖拽经过的路由ID
  dragId = ''; // 当前拖拽的路由ID
  storeUserConfigList: string[] = []; // 存储用户配置的路由ID列表
  storeRoutes: IRouteConfigItem[] = []; // 当前存储的路由配置
  localStoreRoutes: IRouteConfigItem[] = []; // 本地存储的路由配置

  // 组件创建时调用，初始化用户配置和路由数据
  async created() {
    // 获取用户配置的路由ID列表
    this.storeUserConfigList = await this.handleGetUserConfig<string[]>(COMMON_ROUTE_STORE_KEY, { reject403: true });
    // 初始化平面路由列表
    this.flatRoutes = COMMON_ROUTE_LIST;
    // 获取存储的路由配置
    this.storeRoutes = this.getStoreRoutes();
    // 通知父组件路由配置的变化
    this.handleStoreRoutesChange();
  }

  // 监听 show 属性的变化，控制键盘事件的监听
  @Watch('show')
  handleShowChange(v: boolean) {
    if (v) {
      window.addEventListener('keyup', this.handleDocumentKeydown);
    } else {
      window.removeEventListener('keyup', this.handleDocumentKeydown);
    }
    // 获取本地存储的路由配置
    const list = getLocalStoreRoute();
    this.localStoreRoutes = !list?.length ? [] : this.getStoreRoutesByIdList(list);
  }

  // 发出 change 事件，用于通知父组件模态框显示或隐藏状态的变化
  @Emit('change')
  async handleShow(v: boolean) {
    return v;
  }

  @Emit('confirm')
  handleConfirm(): void {}

  // 发出 storeRoutesChange 事件，用于通知父组件路由配置的变化
  @Emit('storeRoutesChange')
  handleStoreRoutesChange() {
    return this.storeRoutes;
  }

  // 处理键盘事件，按下 Esc 键时关闭模态框
  handleDocumentKeydown(e: KeyboardEvent) {
    if (e.code === 'Escape') {
      this.handleShow(false);
    }
  }

  // 获取存储的路由配置
  getStoreRoutes() {
    // 判断 storeUserConfigList 是否为数组
    const configList =
      !Array.isArray(this.storeUserConfigList) || this.storeUserConfigList.length === 0
        ? DEFAULT_ROUTE_LIST
        : this.storeUserConfigList;
    return this.getStoreRoutesByIdList(configList);
  }

  // 根据路由ID列表获取路由配置
  getStoreRoutesByIdList(routeIds: string[]) {
    const routes = [];
    this.flatRoutes.forEach(item => {
      const list = item.children?.filter(set => routeIds.includes(set.id));
      list?.length && routes.push(...list);
    });
    return routeIds.map(id => routes.find(item => item.id === id)).filter(Boolean);
  }

  // 设置存储的路由配置并同步到用户配置
  setStoreRoutes() {
    this.handleSetUserConfig(COMMON_ROUTE_STORE_KEY, JSON.stringify(this.storeRoutes.map(item => item.id)));
    this.handleStoreRoutesChange();
  }

  // 处理拖拽开始事件，记录当前拖拽的路由ID
  handleDragstart(item: IRouteConfigItem) {
    this.dragId = item.id;
  }

  // 处理拖拽经过事件，设置当前拖拽经过的路由ID
  handleDragover(item: IRouteConfigItem, e: MouseEvent) {
    this.dragoverId = item.id;
    e.preventDefault();
  }

  // 处理拖拽离开事件，清除当前拖拽经过的路由ID
  handleDragleave() {
    this.dragoverId = '';
  }

  // 处理拖拽放置事件，交换拖拽和拖拽经过的路由位置
  handleDrop(e: MouseEvent) {
    if (this.dragoverId && this.dragId && this.dragId !== this.dragoverId) {
      e.preventDefault();
      const dragItem = this.storeRoutes.find(item => item.id === this.dragId);
      const dragoverItem = this.storeRoutes.find(item => item.id === this.dragoverId);
      this.storeRoutes = this.storeRoutes.map(item => {
        if (item.id === this.dragId) {
          return dragoverItem;
        }
        if (item.id === this.dragoverId) {
          return dragItem;
        }
        return item;
      });
      this.setStoreRoutes();
      this.dragoverId = '';
      this.dragId = '';
    }
  }

  // 处理删除存储路由的操作
  handleDeleteStoreRoute(index: number) {
    this.storeRoutes.splice(index, 1);
    this.setStoreRoutes();
  }

  // 处理存储路由的切换操作
  handleStoreRoute(item: IRouteConfigItem) {
    const index = this.storeRoutes.findIndex(set => item.id === set.id);
    if (index > -1) {
      this.storeRoutes.splice(index, 1);
    } else this.storeRoutes.push({ ...item });
    this.setStoreRoutes();
  }

  // 判断某个路由是否已存储
  isStoredRoute(id: string) {
    return this.storeRoutes.some(item => item.id === id);
  }

  // 渲染最近访问的路由部分
  contentHeader() {
    // return (
    //   <div class='content-header'>
    //     {this.$t('最近访问')}
    //     <ul class='latest-list'>
    //       {this.localStoreRoutes
    //         .filter(Boolean)
    //         .slice(-6)
    //         .map(item => (
    //           <li
    //             key={item.id}
    //             class='latest-item'
    //           >
    //             {this.$t(`route-${item.name}`)}
    //           </li>
    //         ))}
    //     </ul>
    //   </div>
    // );
  }

  // 渲染所有可用路由部分
  contentRoutes() {
    return (
      <div class='content-routes'>
        {this.flatRoutes.map(item => (
          <div
            key={item.id}
            class='route-content'
          >
            <span class='route-title'>
              {this.$t(item.name.startsWith('route-') ? item.name : `route-${item.name}`)}
            </span>
            <ul class='route-list'>
              {item.children?.map(child => (
                <li
                  key={child.id}
                  class={`route-item ${this.isStoredRoute(child.id) ? 'is-stored' : ''}`}
                  onClick={() => this.handleStoreRoute(child)}
                >
                  {this.$t(child.name.startsWith('route-') ? child.name : `route-${child.name}`)}
                  <i
                    class={`icon-monitor route-check ${
                      this.isStoredRoute(child.id) ? 'icon-mc-check-fill' : 'icon-check'
                    }`}
                  />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    );
  }

  // 渲染常用导航的路由部分
  leftRoutes() {
    return (
      <div class='right-route'>
        <div class='right-route-title'>
          {this.$t('结果预览')}
          <span class='route-count'>{this.storeRoutes.length}</span>
        </div>
        <ul class='route-list'>
          {this.storeRoutes.map((item, index) => (
            <li
              key={item.id}
              class='route-list-item'
              draggable={true}
              onDragleave={this.handleDragleave}
              onDragover={e => this.handleDragover(item, e)}
              onDragstart={() => this.handleDragstart(item)}
              onDrop={this.handleDrop}
            >
              <span class='icon-monitor icon-mc-tuozhuai item-drag' />
              <div class={`route-list-item-main ${this.dragoverId === item.id ? 'is-dragover' : ''}`}>
                <i class={`${item.icon} item-icon`} />
                {this.$t(item.name.startsWith('route-') ? item.name : `route-${item.name}`)}
                <span
                  class='icon-monitor icon-mc-close item-close'
                  onClick={() => this.handleDeleteStoreRoute(index)}
                />
              </div>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  // 渲染函数，定义模态框的结构和内容
  render() {
    return (
      <MonitorDialog
        width='1054'
        class='quick-access-modal'
        appendToBody={true}
        maskClose={true}
        needCloseIcon={false}
        needFooter={true}
        needHeader={false}
        value={this.show}
        zIndex={2000}
        onChange={this.handleShow}
        onConfirm={this.handleConfirm}
      >
        <div class='route-setting'>
          <div class='route-setting-left'>
            <div class='content-header'>{this.$t('快捷入口管理')}</div>
            {this.contentRoutes()}
          </div>
          <div class='route-setting-right'>{this.leftRoutes()}</div>
        </div>
      </MonitorDialog>
    );
  }
}

export default tsx.ofType<IHeaderSettingModalProps, IHeaderSettingModalEvent>().convert(HeaderSettingModal);
