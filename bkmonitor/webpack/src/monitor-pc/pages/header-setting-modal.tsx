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

import UserConfigMixin from '../mixins/userStoreConfig';
import {
  type IRouteConfigItem,
  COMMON_ROUTE_LIST,
  COMMON_ROUTE_STORE_KEY,
  DEFAULT_ROUTE_LIST,
  getLocalStoreRoute,
} from '../router/router-config';

import './header-setting-modal.scss';

interface IHeaderSettingModalEvent {
  onChange: boolean;
  onStoreRoutesChange: IRouteConfigItem[];
}
interface IHeaderSettingModalProps {
  show: boolean;
}
@Component
class HeaderSettingModal extends Mixins(UserConfigMixin) {
  @Prop({ required: true, type: Boolean }) readonly show: boolean;
  flatRoutes: IRouteConfigItem[] = [];
  dragoverId = '';
  dragId = '';
  storeUserConfigList: string[] = [];
  storeRoutes: IRouteConfigItem[] = [];
  localStoreRoutes: IRouteConfigItem[] = [];
  async created() {
    this.storeUserConfigList = await this.handleGetUserConfig<string[]>(COMMON_ROUTE_STORE_KEY, { reject403: true });
    this.flatRoutes = COMMON_ROUTE_LIST;
    this.storeRoutes = this.getStoreRoutes();
    this.handleStoreRoutesChange();
  }
  @Watch('show')
  handleShowChange(v: boolean) {
    if (v) {
      window.addEventListener('keyup', this.handleDocumentKeydown);
    } else {
      window.removeEventListener('keyup', this.handleDocumentKeydown);
    }
    const list = getLocalStoreRoute();
    this.localStoreRoutes = !list?.length ? [] : this.getStoreRoutesByIdList(list);
  }
  @Emit('change')
  async handleShow(v: boolean) {
    return v;
  }
  @Emit('storeRoutesChange')
  handleStoreRoutesChange() {
    return this.storeRoutes;
  }
  handleDocumentKeydown(e: KeyboardEvent) {
    if (e.code === 'Escape') {
      this.handleShow(false);
    }
  }
  getStoreRoutes() {
    const configList =
      !Array.isArray(this.storeUserConfigList) || this.storeUserConfigList.length === 0
        ? DEFAULT_ROUTE_LIST
        : this.storeUserConfigList;
    return this.getStoreRoutesByIdList(configList);
  }
  getStoreRoutesByIdList(routeIds: string[]) {
    const routes = [];
    this.flatRoutes.forEach(item => {
      const list = item.children?.filter(set => routeIds.includes(set.id));
      list?.length && routes.push(...list);
    });
    return routeIds.map(id => routes.find(item => item.id === id)).filter(Boolean);
  }
  setStoreRoutes() {
    this.handleSetUserConfig(COMMON_ROUTE_STORE_KEY, JSON.stringify(this.storeRoutes.map(item => item.id)));
    this.handleStoreRoutesChange();
  }
  handleDragstart(item: IRouteConfigItem) {
    this.dragId = item.id;
  }
  handleDragover(item: IRouteConfigItem, e: MouseEvent) {
    this.dragoverId = item.id;
    e.preventDefault();
  }
  handleDragleave() {
    this.dragoverId = '';
  }
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
  handleDeleteStoreRoute(index: number) {
    this.storeRoutes.splice(index, 1);
    this.setStoreRoutes();
  }
  handleStoreRoute(item: IRouteConfigItem) {
    const index = this.storeRoutes.findIndex(set => item.id === set.id);
    if (index > -1) {
      this.storeRoutes.splice(index, 1);
    } else this.storeRoutes.push({ ...item });
    this.setStoreRoutes();
  }
  isStoredRoute(id: string) {
    return this.storeRoutes.some(item => item.id === id);
  }
  contentHeader() {
    return (
      <div class='content-header'>
        {this.$t('最近访问')}
        <ul class='latest-list'>
          {this.localStoreRoutes
            .filter(Boolean)
            .slice(-6)
            .map(item => (
              <li
                key={item.id}
                class='latest-item'
              >
                {this.$t(`route-${item.name}`)}
              </li>
            ))}
        </ul>
      </div>
    );
  }
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
  leftRoutes() {
    return (
      <div class='left-route'>
        <div class='left-route-title'>
          {this.$t('常用导航')}
          <span class='route-count'>{this.storeRoutes.length}</span>
        </div>
        <ul class='route-list'>
          {this.storeRoutes.map((item, index) => (
            <li
              key={item.id}
              class={`route-list-item ${this.dragoverId === item.id ? 'is-dragover' : ''}`}
              draggable={true}
              onDragleave={this.handleDragleave}
              onDragover={e => this.handleDragover(item, e)}
              onDragstart={() => this.handleDragstart(item)}
              onDrop={this.handleDrop}
            >
              <i class={`${item.icon} item-icon`} />
              <span class='icon-monitor icon-mc-tuozhuai item-drag' />
              {this.$t(item.name.startsWith('route-') ? item.name : `route-${item.name}`)}
              <span
                class='icon-monitor icon-mc-close item-close'
                onClick={() => this.handleDeleteStoreRoute(index)}
              />
            </li>
          ))}
        </ul>
      </div>
    );
  }
  render() {
    return (
      <MonitorDialog
        class='header-setting-modal'
        fullScreen={true}
        maskClose={true}
        needFooter={false}
        needHeader={false}
        value={this.show}
        zIndex={2000}
        onChange={this.handleShow}
      >
        <div class='route-setting'>
          <div class='route-setting-left'>{this.leftRoutes()}</div>
          <div class='route-setting-right'>
            {this.contentHeader()}
            {this.contentRoutes()}
          </div>
        </div>
      </MonitorDialog>
    );
  }
}

export default tsx.ofType<IHeaderSettingModalProps, IHeaderSettingModalEvent>().convert(HeaderSettingModal);
