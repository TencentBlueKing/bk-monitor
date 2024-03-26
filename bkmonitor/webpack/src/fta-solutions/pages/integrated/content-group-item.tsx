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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { IGroupData } from './group';
import StatusTips, { MapType, StatusType } from './status-tips';

import './content-group-item.scss';

// 插件 安装、详情、启用、禁用
export type OperateType = 'install' | 'detail' | 'enabled' | 'config';
interface IContentGroupItemProps {
  data: IGroupData;
}

interface IContentGroupItemEvents {
  onOperate: ({ type, item }: { type: OperateType; item: IPluginDetail }) => void;
  onGotoWorkbench: () => void;
}

export type PluginCategory = 'event' | 'service';
export interface IPluginDetail {
  plugin_category: PluginCategory;
  bk_biz_id: number;
  plugin_id: string;
  plugin_display_name: string;
  plugin_type: string;
  main_type: string;
  plugin_type_display: string;
  main_type_display: string;
  summary: string;
  logo: string;
  tags: string[];
  popularity: number;
  status: StatusType;
  create_user: string;
  create_time: string;
  update_user: string;
  update_time: string;
  is_official: boolean;
  scenario: string;
  show: boolean;
  author: string;
  version?: string;
  is_installed?: boolean;
}

@Component({ name: 'ContentGroupItem' })
export default class ContentGroupItem extends tsc<IContentGroupItemProps, IContentGroupItemEvents> {
  @Prop({ type: Object, default: () => ({}) }) readonly data: IGroupData;

  activePanel: string | number = '';

  render() {
    return (
      <div>
        {this.data.data?.length ? (
          this.data.data.map(item => (
            <div class='group-item'>
              {/* 插件分组：事件插件 | 周边服务 */}
              {item.name ? (
                <div class='group-item-title'>
                  <span class='title-tips mr5'></span>
                  {item.name}
                </div>
              ) : null}
              {/* 插件信息 */}
              <div class='group-item-content'>
                {item?.data?.length ? (
                  item.data.map(item => this.pluginPanelRender(item))
                ) : (
                  <bk-exception
                    type='empty'
                    scene='part'
                    class='empty'
                  >
                    {this.$t('暂无事件源')}
                  </bk-exception>
                )}
              </div>
            </div>
          ))
        ) : (
          <div class='group-item'>
            <bk-exception
              type='empty'
              scene='part'
              class='empty'
            >
              {this.$t('暂无事件源')}
            </bk-exception>
          </div>
        )}
      </div>
    );
  }

  /**
   * 渲染插件Panel
   * @param item
   * @returns
   */
  pluginPanelRender(item: IPluginDetail) {
    return (
      <div
        class='plugin-panel mb15 mr15'
        style={{ display: item.show ? 'flex' : 'none' }}
        onMouseenter={() => this.handleCardMouseEnter(item)}
        onMouseleave={this.handleCardMouseLeave}
      >
        {/* 插件状态 */}
        <StatusTips status={item.status}></StatusTips>
        {/* 插件ICON和名称 */}
        <div class='plugin-panel-content'>
          {item.logo ? (
            <img
              alt=''
              class='img-logo'
              src={`data:image/png;base64,${item.logo}`}
            />
          ) : (
            <span class='text-logo'>
              {(item.plugin_display_name || item.plugin_id).slice(0, 1).toLocaleUpperCase()}
            </span>
          )}
          <span class='title mt10'>{item.plugin_display_name || item.plugin_id}</span>
        </div>
        <div class='plugin-panel-footer'>
          {/* 插件来源 */}
          <span class='footer-left'>
            {item.author}
            {item.is_official ? <i class='icon-monitor icon-mc-official'></i> : null}
          </span>
          {/* 插件热度 */}
          <span class='footer-right'>
            {item.popularity}
            <i class='icon-monitor icon-mc-heat'></i>
          </span>
        </div>
        {/* 插件描述 */}
        {/* <transition name="slide"> */}
        {this.pluginDetailRender(item)}
        {/* </transition> */}
      </div>
    );
  }

  /**
   * 渲染悬浮时详情DOM
   * @param item
   */
  pluginDetailRender(item: IPluginDetail) {
    const operateVnode = this.pluginOperateRender(item);

    if (!operateVnode) return;

    return (
      <div
        class='plugin-panel-detail'
        v-show={this.activePanel === item.plugin_id}
      >
        <div
          class='plugin-desc'
          onClick={() => this.pluginOperate(item, 'detail')}
        >
          {item.summary || this.$t('简介怎么是空的！ 点击查看具体详情吧。')}
        </div>
        {operateVnode}
      </div>
    );
  }

  /**
   * 渲染插件操作DOM
   * @param item
   * @returns
   */
  pluginOperateRender(item: IPluginDetail) {
    const operateMap: MapType<StatusType> = {
      // 已停用类插件操作
      DISABLED: (
        <span class='plugin-operate'>
          <span
            class='operate-btn detail pr20'
            onClick={() => this.pluginOperate(item, 'detail')}
          >
            <i class='mt4 icon-monitor icon-tips'></i>
            {this.$t('详情')}
          </span>
          <span
            class='operate-btn pl20'
            onClick={() => this.pluginOperate(item, 'enabled')}
          >
            <i class='mt4 icon-monitor icon-bofang'></i>
            {this.$t('启用')}
          </span>
        </span>
      ),
      //   // 将下架插件操作
      //   REMOVE_SOON: (
      //     <span class="plugin-operate operate-btn" onClick={() => this.pluginOperate(item, 'config')}>
      //       <i class="icon-monitor icon-menu-config"></i>{this.$t('配置')}
      //     </span>
      //   ),
      // 未安装插件
      AVAILABLE: (
        <span class='plugin-operate'>
          <span
            class='operate-btn detail pr20'
            onClick={() => this.pluginOperate(item, 'detail')}
          >
            <i class='mt4 icon-monitor icon-tips'></i>
            {this.$t('详情')}
          </span>
          <span
            class='operate-btn pl20'
            onClick={() => this.pluginOperate(item, 'install')}
          >
            <i class='mt4 icon-monitor icon-mc-add'></i>
            {this.$t('安装')}
          </span>
        </span>
      )
    };

    if (item.is_installed)
      return (
        <span
          class='plugin-operate operate-btn'
          onClick={() => this.pluginOperate(item, 'config')}
        >
          <i class='icon-monitor icon-menu-config'></i>
          {this.$t('配置')}
        </span>
      );

    return <div class='operate'>{operateMap[item.status]}</div>;
  }

  handleCardMouseEnter(item: IPluginDetail) {
    this.activePanel = item.plugin_id;
  }

  handleCardMouseLeave() {
    this.activePanel = '';
  }

  /**
   * 插件操作事件
   * @param item
   * @param type
   * @returns
   */
  @Emit('operate')
  pluginOperate(item: IPluginDetail, type: OperateType) {
    return {
      item,
      type
    };
  }

  @Emit('gotoWorkbench')
  gotoWorkbench() {}
}
