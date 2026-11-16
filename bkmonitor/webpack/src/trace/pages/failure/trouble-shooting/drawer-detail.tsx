/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the above conditions:
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
import { Exception, Sideslider } from 'bkui-vue';

import EventTable from '../../alarm-center/common-detail/components/panel-event/components/event-table';
import TableFieldSetting from '../../alarm-center/common-detail/components/panel-log/log-table/table-field-setting';
import LogTableNew from './log-table/log-table-new';

import type { DrawerRenderContext } from './composables/use-drawer-detail';

/**
 * 日志表格侧滑 + 事件表格侧滑的统一渲染。
 * ctx 由 useDrawerDetail().getRenderContext() 生成，所有 ref/computed 已解包为值。
 * ref='logScrollBody' 与 useDrawerDetail 内的 useTemplateRef('logScrollBody') 在同一组件实例匹配。
 */
export function renderDrawerDetail(ctx: DrawerRenderContext) {
  return (
    <>
      {/* 日志表格侧滑：叠加在 L0/L1 之上时不创建遮罩，避免组件库 mask 栈把下层 mask 的 opacity 置 0 */}
      <Sideslider
        width={960}
        extCls={'log-viewer-slider'}
        isShow={ctx.showLogSideslider}
        quickClose={true}
        showMask={ctx.logSliderShowMask}
        zIndex={2800}
        onUpdate:isShow={ctx.setLogSidesliderShow}
      >
        {{
          header: () => ctx.currentDrawerContext?.title || ctx.t('日志详情'),
          default: () => (
            <div class='log-viewer-slider-content'>
              <div
                ref={element => ctx.setLogScrollBodyRef(element as HTMLElement | null)}
                class='log-viewer-slider-body'
              >
                {ctx.drawerErrorMessage ? (
                  <Exception
                    class='table-slider-exception'
                    description={ctx.drawerErrorMessage}
                    scene='part'
                    title={ctx.t('查询异常')}
                    type='500'
                  />
                ) : (
                  <LogTableNew
                    key={ctx.drawerRenderKey}
                    allowedMenuTypes={ctx.logAllowedMenuTypes}
                    displayFields={ctx.displayColumnFields}
                    getFieldsData={ctx.getLogFieldsData}
                    getTableData={ctx.getLogTableData}
                    headerAffixedTop={ctx.logHeaderAffixedTop}
                    refreshKey={ctx.logTableRefreshKey}
                    scrollContainer={ctx.logHeaderAffixedTop.container}
                    onAddField={ctx.handleAddField}
                    onClickMenu={ctx.handleLogClickMenu}
                    onRemoveField={ctx.handleRemoveField}
                  >
                    {{
                      settingBtn: () =>
                        ctx.columnConfigEnabled ? (
                          <TableFieldSetting
                            class='table-field-setting'
                            sourceList={ctx.tableColumnsSetting}
                            targetList={ctx.displayColumnFields}
                            onConfirm={ctx.handleDisplayColumnFieldsChange}
                          />
                        ) : null,
                      empty: () => (
                        <Exception
                          class='log-table-empty'
                          type='building'
                        >
                          <span style='margin: 0 24px 16px 24px;font-size: 14px;color: rgb(151, 155, 165);display: inline-block;'>
                            {ctx.t('暂无关联日志')}
                          </span>
                        </Exception>
                      ),
                    }}
                  </LogTableNew>
                )}
              </div>
            </div>
          ),
        }}
      </Sideslider>

      {/* 事件表格侧滑：叠加在 L0/L1 之上时不创建遮罩，避免组件库 mask 栈把下层 mask 的 opacity 置 0 */}
      <Sideslider
        width={960}
        extCls={'event-table-slider'}
        isShow={ctx.showEventTableSideslider}
        quickClose={true}
        showMask={ctx.eventTableSliderShowMask}
        zIndex={2800}
        onClosed={ctx.closeEventTableSlider}
      >
        {{
          header: () => (
            <div class='event-table-slider-header'>
              <span class='mr-2'>{ctx.currentDrawerContext?.title || ctx.t('事件详情')}</span>
            </div>
          ),
          default: () => (
            <div
              ref={element => ctx.setEventScrollBodyRef(element as HTMLElement | null)}
              class='event-table-slider-content'
            >
              {ctx.drawerErrorMessage ? (
                <Exception
                  class='table-slider-exception'
                  description={ctx.drawerErrorMessage}
                  scene='part'
                  title={ctx.t('查询异常')}
                  type='500'
                />
              ) : (
                <EventTable
                  key={ctx.drawerRenderKey}
                  getTableData={ctx.getEventTableData}
                  scrollContainer={ctx.eventScrollContainer}
                  showHeaderOperate={false}
                />
              )}
            </div>
          ),
        }}
      </Sideslider>
    </>
  );
}
