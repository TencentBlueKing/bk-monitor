import { Emit, Mixins, Prop } from 'vue-property-decorator';

import { deepClone } from 'monitor-common/utils';
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
import Component from 'vue-class-component';

import UserConfigMixin from '../../../../mixins/userStoreConfig';
import { COMMON_ROUTE_LIST, COMMON_ROUTE_STORE_KEY, DEFAULT_ROUTE_LIST } from '../../../../router/router-config';
import emptyImageSrc from '../../../../static/images/png/empty.png';
import AiWhaleInput from './ai-whale-input';
import HeaderSettingModal from './header-setting-modal';

import './quick-access.scss';

@Component({})
export default class QuickAccess extends Mixins(UserConfigMixin) {
  @Prop({ default: false, type: Boolean }) categoriesHasTwoRows: boolean;
  @Prop({ default: false, type: Boolean }) enableAiAssistant: boolean;

  loadingQuickList = true; // 快捷入口loading

  quickAccessList = []; // 快捷入口列表

  showModal = false; // 控制模态框显示

  async created() {
    try {
      await this.initQuickAccessData();
    } catch {}
  }

  // 初始化快捷入口的数据
  async initQuickAccessData() {
    try {
      this.loadingQuickList = true;
      /** 根据当前bizId区分是要展示新版的k8s还是旧版的k8s, 当isEnableK8sV2为true时，不展示旧版 */
      const filterKey = this.$store.getters.isEnableK8sV2 ? 'k8s' : 'k8s-new';
      const data = (await this.handleGetUserConfig<string[]>(COMMON_ROUTE_STORE_KEY, { reject403: true })) || [];
      const routes = [];
      for (const item of COMMON_ROUTE_LIST) {
        const list = item.children?.filter(set => data.includes(set.id));
        list?.length && routes.push(...list);
      }
      this.quickAccessList = (
        data.length
          ? data.map(id => routes.find(item => item.id === id)).filter(Boolean)
          : this.getDefaultQuickAccessList()
      ).filter(item => item.id !== filterKey);
    } catch {
    } finally {
      this.loadingQuickList = false;
    }
  }

  // 获取默认快捷入口配置
  getDefaultQuickAccessList() {
    const routes = [];
    for (const item of COMMON_ROUTE_LIST) {
      const list = item.children?.filter(set => DEFAULT_ROUTE_LIST.includes(set.id));
      list?.length && routes.push(...list);
    }
    return DEFAULT_ROUTE_LIST.map(id => routes.find(item => item.id === id)).filter(Boolean);
  }

  // 缓存快捷入口
  async handleSetQuickAccess(v) {
    this.loadingQuickList = true;
    this.showModal = false;
    this.quickAccessList = deepClone(v);
    await this.handleSetUserConfig(COMMON_ROUTE_STORE_KEY, JSON.stringify(this.quickAccessList.map(item => item.id)));
    this.$nextTick(() => {
      this.loadingQuickList = false;
    });
  }

  // 显示或隐藏头部设置模态框
  handleHeaderSettingShowChange(visible: boolean) {
    this.showModal = visible;
  }

  @Emit('handleGoStoreRoute')
  handleGoStoreRoute(item) {
    return item;
  }
  @Emit('handleKeyDown')
  handleKeyDown(e) {
    return e;
  }

  render() {
    return (
      <div class='quick-access'>
        <div class='quick-head'>
          <div class='quick-title'>{this.$t('快捷入口')}</div>
          <div
            class='customize'
            onClick={() => (this.showModal = true)}
          >
            <i class='icon-monitor icon-customize' />
            <span>{this.$t('自定义')}</span>
          </div>
        </div>
        <div class='quick-list'>
          {!this.loadingQuickList ? (
            <ul class={{ 'quick-items': true, 'no-ai-whale': !this.enableAiAssistant }}>
              {this.quickAccessList.length ? (
                this.quickAccessList
                  ?.filter(item => item.id)
                  .map(item => (
                    <li
                      key={item.id}
                      class='quick-item'
                      onClick={() => this.handleGoStoreRoute(item)}
                    >
                      <i class={`${item.icon} list-item-icon`} />
                      <span>{this.$t(item.name.startsWith('route-') ? item.name : `route-${item.name}`)}</span>
                    </li>
                  ))
              ) : (
                <div class='quick-items-empty'>
                  {' '}
                  <div class='empty-img'>
                    <img
                      alt=''
                      src={emptyImageSrc}
                    />
                  </div>
                  {this.$t('尚未配置，自定义')}
                </div>
              )}
            </ul>
          ) : (
            <div class={{ skeleton: true, 'no-ai-whale': !this.enableAiAssistant }}>
              {Array(this.enableAiAssistant ? 6 : 7)
                .fill(null)
                .map((_, index) => (
                  <div
                    key={index}
                    class='skeleton-element'
                  />
                ))}
            </div>
          )}
        </div>
        {/* AI 小鲸 */}
        {this.enableAiAssistant && (
          <AiWhaleInput
            categoriesHasTwoRows={this.categoriesHasTwoRows}
            onKeyDown={this.handleKeyDown}
          />
        )}
        {/* 快捷入口模态框 */}
        <HeaderSettingModal
          quickAccessList={this.quickAccessList}
          show={this.showModal}
          onChange={this.handleHeaderSettingShowChange}
          onConfirm={v => this.handleSetQuickAccess(v)}
        />
      </div>
    );
  }
}
