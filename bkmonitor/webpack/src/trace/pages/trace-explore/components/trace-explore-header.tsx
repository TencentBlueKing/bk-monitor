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

import { type PropType, computed, defineComponent, onMounted, onUnmounted, shallowRef } from 'vue';

import { Badge, Select } from 'bkui-vue';
import { deepClone, detectOS, random } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import RefreshRate from '../../../components/refresh-rate/refresh-rate';
import SelectMenu, { type ISelectMenuOption } from '../../../components/select-menu/select-menu';
import TimeRange from '../../../components/time-range/time-range';
import { useTraceExploreStore } from '../../../store/modules/explore';

import type { TimeRangeType } from '../../../components/time-range/utils';
import type { HideFeatures, IApplicationItem } from '../typing';

import './trace-explore-header.scss';

export default defineComponent({
  name: 'TraceExploreHeader',
  props: {
    list: {
      type: Array as PropType<IApplicationItem[]>,
      default: () => [],
    },
    isShowFavorite: {
      type: Boolean,
      default: true,
    },
    hideFeatures: {
      type: Array as PropType<HideFeatures>,
      default: () => [],
    },
    thumbtackList: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  emits: [
    'favoriteShowChange',
    'sceneModeChange',
    'timeRangeChange',
    'timezoneChange',
    'immediateRefreshChange',
    'refreshChange',
    'appNameChange',
    'thumbtackChange',
  ],

  setup(props, { emit }) {
    const { t } = useI18n();
    const store = useTraceExploreStore();
    const router = useRouter();
    const route = useRoute();
    const applicationSelectRef = shallowRef<InstanceType<typeof Select>>(null);
    const applicationToggle = shallowRef(false);

    const headerToolMenuList: ISelectMenuOption[] = [{ id: 'config', name: t('应用设置') }];

    function handleMenuSelectChange() {
      if (store.appName) {
        const url = location.href.replace(location.hash, `#/apm/application/config/${store.appName}`);
        window.open(url, '_blank');
      }
    }

    /** 置顶排序后的列表 */
    const sortList = computed<IApplicationItem[]>(() => {
      const thumbtack = [];
      const other = [];
      for (const item of props.list) {
        if (props.thumbtackList.includes(item.app_name)) {
          thumbtack.push({
            ...item,
            isTop: true,
          });
        } else {
          other.push({
            ...item,
            isTop: false,
          });
        }
      }
      return [...thumbtack, ...other];
    });

    const applicationFilter = (keyword: string, item) => {
      return item.name.includes(keyword) || item.id.includes(keyword);
    };

    const handleFavoriteShowChange = () => {
      emit('favoriteShowChange', !props.isShowFavorite);
    };

    function handleApplicationToggle(toggle: boolean) {
      applicationToggle.value = toggle;
    }

    function handleTimeRangeChange(val: TimeRangeType) {
      store.updateTimeRange(val);
      emit('timeRangeChange', val);
    }

    function handleTimezoneChange(v: string) {
      store.updateTimezone(v);
      emit('timezoneChange', v);
    }

    function handleImmediateRefresh() {
      store.updateRefreshImmediate(random(4));
      emit('immediateRefreshChange');
    }

    function handleRefreshChange(v: number) {
      store.updateRefreshInterval(v);
      emit('refreshChange', v);
    }

    function handleApplicationChange(val: string) {
      const application = props.list.find(item => item.app_name === val);
      if (application.app_name === store.appName) return;
      store.updateAppName(application.app_name);
      emit('appNameChange', val);
    }

    function handleDocumentClick(e: KeyboardEvent) {
      const isKeyO = e.key.toLowerCase() === 'o';
      // 检测是否按下 Ctrl 或 Command 键（跨平台兼容）
      const isCtrlOrMeta = e.ctrlKey || e.metaKey;
      if (isKeyO && isCtrlOrMeta) {
        e.preventDefault();
        applicationSelectRef.value.showPopover();
      }
    }

    async function handleThumbtack(e: Event, item: IApplicationItem) {
      e.stopPropagation();
      let list = deepClone(props.thumbtackList);
      if (item.isTop) {
        list = list.filter(appName => appName !== item.app_name);
      } else {
        list = [item.app_name, ...list];
      }
      emit('thumbtackChange', list);
    }

    function handleSceneModelChange(mode: 'span' | 'trace') {
      if (mode === store.mode) return;
      const oldMode = store.mode;
      store.updateMode(mode);
      emit('sceneModeChange', mode, oldMode);
    }

    onMounted(() => {
      window.addEventListener('keydown', handleDocumentClick);
    });

    onUnmounted(() => {
      window.removeEventListener('keydown', handleDocumentClick);
    });

    function handleGotoOld() {
      router.push({
        name: 'trace-old',
        query: route.query,
        params: route.params,
      });
    }

    return {
      t,
      store,
      sortList,
      applicationSelectRef,
      applicationToggle,
      headerToolMenuList,
      handleMenuSelectChange,
      applicationFilter,
      handleApplicationToggle,
      handleApplicationChange,
      handleSceneModelChange,
      handleFavoriteShowChange,
      handleThumbtack,
      handleImmediateRefresh,
      handleRefreshChange,
      handleTimeRangeChange,
      handleTimezoneChange,
      handleGotoOld,
    };
  },

  render() {
    return (
      <div class='trace-explore-header'>
        <div class='header-left'>
          {this.hideFeatures.includes('favorite') ? null : (
            <div class='favorite-container'>
              <div
                class={['favorite-btn', { active: this.isShowFavorite }]}
                onClick={this.handleFavoriteShowChange}
              >
                <i
                  class='icon-monitor icon-shoucangjia'
                  v-bk-tooltips={{ content: this.t(this.isShowFavorite ? '收起收藏夹' : '展开收藏夹') }}
                />
              </div>
            </div>
          )}
          {this.hideFeatures.includes('title') ? null : <div class='header-title'>{this.t('Tracing 检索')}</div>}
          {this.hideFeatures.includes('title') ? null : (
            <div class='event-type-select'>
              <div
                class={{ item: true, active: this.store.mode === 'trace' }}
                onClick={() => this.handleSceneModelChange('trace')}
              >
                {this.t('Trace 视角')}
              </div>
              <div
                class={{ item: true, active: this.store.mode === 'span' }}
                onClick={() => this.handleSceneModelChange('span')}
              >
                {this.t('Span 视角')}
              </div>
            </div>
          )}
          {this.hideFeatures.includes('application') ? null : (
            <Select
              ref='applicationSelectRef'
              class='application-select'
              popoverOptions={{
                extCls: 'trace-explore-application-select-popover',
              }}
              clearable={false}
              filterOption={this.applicationFilter}
              modelValue={this.store.appName}
              filterable
              onSelect={this.handleApplicationChange}
              onToggle={this.handleApplicationToggle}
            >
              {{
                trigger: () => (
                  <div class='application-select-trigger'>
                    <span class='data-prefix'>{this.t('应用')}：</span>
                    {this.store.currentApp && (
                      <span
                        class='application-name'
                        v-overflow-tips
                      >
                        {this.store.currentApp.app_alias}({this.store.currentApp.app_name})
                      </span>
                    )}

                    {!this.applicationToggle && (
                      <div class='select-shortcut-keys'>{detectOS() === 'Windows' ? 'Ctrl+O' : 'Cmd+O'}</div>
                    )}
                    <span class={`icon-monitor icon-mc-arrow-down ${this.applicationToggle ? 'expand' : ''}`} />
                  </div>
                ),
                default: () =>
                  this.sortList.map(item => (
                    <Select.Option
                      id={item.app_name}
                      key={item.app_name}
                      name={item.app_alias}
                    >
                      {this.applicationToggle && (
                        <div class={['application-item-name', { is_top: item.isTop }]}>
                          <i
                            class={[
                              'icon-monitor',
                              'thumbtack',
                              item.isTop ? 'icon-a-pinnedtuding' : 'icon-a-pintuding',
                            ]}
                            onClick={e => this.handleThumbtack(e, item)}
                          />
                          <span
                            class='name-text'
                            v-overflow-tips
                          >
                            {item.app_alias}({item.app_name})
                          </span>
                        </div>
                      )}
                    </Select.Option>
                  )),
              }}
            </Select>
          )}
        </div>
        {this.hideFeatures.includes('dateRange') ? null : (
          <div class='header-tools'>
            <span class='inquire-header-append-item'>
              <TimeRange
                modelValue={this.store.timeRange}
                timezone={this.store.timezone}
                onUpdate:modelValue={this.handleTimeRangeChange}
                onUpdate:timezone={this.handleTimezoneChange}
              />
            </span>
            <span class='inquire-header-append-item'>
              <RefreshRate
                value={this.store.refreshInterval}
                onImmediate={this.handleImmediateRefresh}
                onSelect={this.handleRefreshChange}
              />
              <SelectMenu
                list={this.headerToolMenuList}
                onSelect={this.handleMenuSelectChange}
              >
                <i class='icon-monitor icon-mc-more-tool' />
              </SelectMenu>
            </span>
          </div>
        )}

        <div class='goto-old'>
          <div
            class='goto-old-wrap'
            v-bk-tooltips={{
              content: this.t('回到旧版'),
              placements: ['bottom-end'],
              zIndex: 9999,
            }}
            onClick={() => this.handleGotoOld()}
          >
            <div class='icon'>
              <i class='icon-monitor icon-zhuanhuan' />
            </div>
            {this.$slots.default || (
              <Badge
                count='!'
                theme='warning'
              >
                <span>{this.t('回到旧版')}</span>
              </Badge>
            )}
          </div>
        </div>
      </div>
    );
  },
});
