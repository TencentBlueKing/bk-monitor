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

import { defineComponent, shallowRef, computed, type PropType, onMounted, onUnmounted } from 'vue';
import { useI18n } from 'vue-i18n';

import { Select } from 'bkui-vue';
import { detectOS, random } from 'monitor-common/utils';

import useUserConfig from '../../../hooks/useUserConfig';
import { useTraceExploreStore } from '../../../store/modules/explore';

// import GotoOldVersion from '../../monitor-k8s/components/k8s-nav-bar/goto-old';

import RefreshRate from '../../../components/refresh-rate/refresh-rate';
import SelectMenu, { type ISelectMenuOption } from '../../../components/select-menu/select-menu';
import TimeRange from '../../../components/time-range/time-range';

import type { TimeRangeType } from '../../../components/time-range/utils';
import type { HideFeatures, IApplicationItem } from '../typing';

import './trace-explore-header.scss';

/** 置顶的data_id */
const TRACE_EXPLORE_APPLICATION_ID_THUMBTACK = 'trace_explore_application_id_thumbtack';

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
  },
  emits: ['favoriteShowChange'],

  setup(props, { emit }) {
    const { t } = useI18n();
    const store = useTraceExploreStore();
    const { handleGetUserConfig, handleSetUserConfig } = useUserConfig();
    const applicationSelectRef = shallowRef<InstanceType<typeof Select>>(null);
    const applicationToggle = shallowRef(false);

    const headerToolMenuList: ISelectMenuOption[] = [{ id: 'config', name: t('应用设置') }];

    function handleMenuSelectChange() {
      const appName = props.list?.find(app => app.app_name === store.application?.app_name)?.app_name || '';
      if (appName) {
        const url = location.href.replace(location.hash, `#/apm/application/config/${appName}`);
        window.open(url, '_blank');
      }
    }

    /** 置顶的列表 */
    const thumbtackList = shallowRef<string[]>([]);

    /** 置顶排序后的列表 */
    const sortList = computed(() => {
      const thumbtack = [];
      const other = [];
      for (const item of props.list) {
        if (thumbtackList.value.includes(item.metric_result_table_id)) {
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

    const handleFavoriteShowChange = () => {
      emit('favoriteShowChange', !props.isShowFavorite);
    };

    function handleApplicationToggle(toggle: boolean) {
      applicationToggle.value = toggle;
    }

    function handleTimeRangeChange(val: TimeRangeType) {
      store.updateTimeRange(val);
    }

    function handleTimezoneChange(v: string) {
      store.updateTimezone(v);
    }

    function handleImmediateRefresh() {
      store.updateRefreshImmediate(random(4));
    }

    function handleRefreshChange(v: number) {
      store.updateRefreshInterval(v);
    }

    function handleApplicationChange(val: string) {
      const application = props.list.find(item => item.app_name === val);
      console.log(val, application);
      store.updateApplicationId(application);
    }

    function handleDocumentClick(e: KeyboardEvent) {
      const isKeyO = e.key.toLowerCase() === 'o';
      // 检测是否按下 Ctrl 或 Command 键（跨平台兼容）
      const isCtrlOrMeta = e.ctrlKey || e.metaKey;
      if (isKeyO && isCtrlOrMeta) {
        e.preventDefault();
        console.log(applicationSelectRef.value);
        applicationSelectRef.value.showPopover();
      }
    }

    async function handleThumbtack(e: Event, item: IApplicationItem) {
      e.stopPropagation();
      if (item.isTop) {
        thumbtackList.value = thumbtackList.value.filter(id => id !== item.id);
      } else {
        thumbtackList.value = [item.id, ...thumbtackList.value];
      }
      await handleSetUserConfig(TRACE_EXPLORE_APPLICATION_ID_THUMBTACK, JSON.stringify(thumbtackList.value));
    }

    function handleSceneModelChange(mode: 'span' | 'trace') {
      store.updateMode(mode);
    }

    onMounted(() => {
      document.addEventListener('keydown', handleDocumentClick);
      handleGetUserConfig<string[]>(TRACE_EXPLORE_APPLICATION_ID_THUMBTACK).then(res => {
        thumbtackList.value = res || [];
      });
    });

    onUnmounted(() => {
      document.removeEventListener('keydown', handleDocumentClick);
    });

    return {
      t,
      store,
      sortList,
      applicationSelectRef,
      applicationToggle,
      headerToolMenuList,
      handleMenuSelectChange,
      handleApplicationToggle,
      handleApplicationChange,
      handleSceneModelChange,
      handleFavoriteShowChange,
      handleThumbtack,
      handleImmediateRefresh,
      handleRefreshChange,
      handleTimeRangeChange,
      handleTimezoneChange,
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
                  v-bk-tooltips={{ content: this.$t(this.isShowFavorite ? '收起收藏夹' : '展开收藏夹') }}
                />
              </div>
            </div>
          )}
          {this.hideFeatures.includes('title') ? null : <div class='header-title'>{this.$t('Tracing 检索')}</div>}
          {this.hideFeatures.includes('title') ? null : (
            <div class='event-type-select'>
              <div
                class={{ item: true, active: this.store.mode === 'trace' }}
                onClick={() => this.handleSceneModelChange('trace')}
              >
                {this.$t('Tracing 视角')}
              </div>
              <div
                class={{ item: true, active: this.store.mode === 'span' }}
                onClick={() => this.handleSceneModelChange('span')}
              >
                {this.$t('Span 视角')}
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
              modelValue={this.store.application?.metric_result_table_id}
              onSelect={this.handleApplicationChange}
              onToggle={this.handleApplicationToggle}
            >
              {{
                trigger: () => (
                  <div class='application-select-trigger'>
                    <span class='data-prefix'>{this.$t('应用')}：</span>
                    {this.store.application && (
                      <span
                        class='application-name'
                        // v-bk-overflow-tips
                      >
                        {this.store.application.app_alias}({this.store.application.app_name})
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
                      key={item.trace_result_table_id}
                      name={item.app_name}
                    >
                      <div class={['application-item-name', { is_top: item.isTop }]}>
                        <i
                          class={['icon-monitor', 'thumbtack', item.isTop ? 'icon-a-pinnedtuding' : 'icon-a-pintuding']}
                          onClick={e => this.handleThumbtack(e, item)}
                        />
                        <span
                          class='name-text'
                          // v-bk-overflow-tips
                        >
                          {item.app_alias}({item.app_name})
                        </span>
                      </div>
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

        {/* {!this.needMenu ? null : (
          <GotoOldVersion
            tips={this.$tc('新版事件检索尚未完全覆盖旧版功能，如需可切换到旧版查看')}
            onClick={this.handleGotoOldVersion}
          />
        )} */}
      </div>
    );
  },
});
