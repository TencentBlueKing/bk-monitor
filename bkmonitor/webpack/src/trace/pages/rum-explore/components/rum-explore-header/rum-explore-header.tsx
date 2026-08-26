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

import { Select } from 'bkui-vue';
import { deepClone, detectOS, random } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import RefreshRate from '../../../../components/refresh-rate/refresh-rate';
import TimeRange from '../../../../components/time-range/time-range';
import { useRumExploreStore } from '../../../../store/modules/rum-explore';
import { RUM_MODE_TAB_LIST } from '../../constants';

import type { TimeRangeType } from '../../../../components/time-range/utils';
import type { IRumApplication, RumMode } from '../../typings';

import './rum-explore-header.scss';

export default defineComponent({
  name: 'RumExploreHeader',
  props: {
    applicationList: {
      type: Array as PropType<IRumApplication[]>,
      default: () => [],
    },
    favoriteShow: {
      type: Boolean,
      default: false,
    },
    /** 置顶的应用名列表 */
    thumbtackList: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  emits: {
    favoriteShowChange: (_show: boolean) => true,
    appNameChange: (_appName: string) => true,
    modeChange: (_mode: RumMode, _oldMode: RumMode) => true,
    thumbtackChange: (_list: string[]) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const store = useRumExploreStore();

    const applicationSelectRef = shallowRef<InstanceType<typeof Select>>(null);
    const applicationToggle = shallowRef(false);

    /** 置顶的应用排在前面 */
    const sortedApplicationList = computed<IRumApplication[]>(() => {
      const pinned: IRumApplication[] = [];
      const others: IRumApplication[] = [];
      for (const item of props.applicationList) {
        const target = props.thumbtackList.includes(item.app_name) ? pinned : others;
        target.push({ ...item, isTop: target === pinned });
      }
      return [...pinned, ...others];
    });

    const shortcutKeyText = computed(() => (detectOS() === 'Windows' ? 'Ctrl+O' : 'Cmd+O'));

    function applicationFilter(keyword: string, item: { id: string; name: string }) {
      return item.name.includes(keyword) || item.id.includes(keyword);
    }

    function handleApplicationChange(appName: string) {
      if (appName === store.appName) return;
      store.appName = appName;
      emit('appNameChange', appName);
    }

    function handleModeChange(tab: (typeof RUM_MODE_TAB_LIST)[number]) {
      if (tab.value === store.mode || tab.disabled) return;
      const oldMode = store.mode;
      store.mode = tab.value;
      emit('modeChange', tab.value, oldMode);
    }

    function handleThumbtack(event: Event, item: IRumApplication) {
      event.stopPropagation();
      const list: string[] = deepClone(props.thumbtackList);
      emit('thumbtackChange', item.isTop ? list.filter(name => name !== item.app_name) : [item.app_name, ...list]);
    }

    /** 全局 Cmd/Ctrl + O 唤起应用选择器 */
    function handleShortcutKeydown(event: KeyboardEvent) {
      if (event.key?.toLowerCase() !== 'o' || !(event.ctrlKey || event.metaKey)) return;
      event.preventDefault();
      applicationSelectRef.value?.showPopover();
    }

    onMounted(() => {
      window.addEventListener('keydown', handleShortcutKeydown);
    });

    onUnmounted(() => {
      window.removeEventListener('keydown', handleShortcutKeydown);
    });

    return {
      t,
      store,
      applicationSelectRef,
      applicationToggle,
      shortcutKeyText,
      sortedApplicationList,
      applicationFilter,
      handleApplicationChange,
      handleModeChange,
      handleThumbtack,
      handleTimeRangeChange: (val: TimeRangeType) => {
        store.timeRange = val;
      },
      handleTimezoneChange: (val: string) => {
        store.timezone = val;
      },
      handleRefreshChange: (val: number) => {
        store.refreshInterval = val;
      },
      handleImmediateRefresh: () => {
        store.refreshImmediate = random(4);
      },
      handleApplicationToggle: (toggle: boolean) => {
        applicationToggle.value = toggle;
      },
    };
  },

  render() {
    return (
      <div class='rum-explore-header'>
        <div class='header-left'>
          <div class='favorite-container'>
            <div
              class={['favorite-btn', { active: this.favoriteShow }]}
              v-bk-tooltips={{ content: this.t(this.favoriteShow ? '收起收藏夹' : '展开收藏夹') }}
              onClick={() => this.$emit('favoriteShowChange', !this.favoriteShow)}
            >
              <i class='icon-monitor icon-shoucangjia' />
            </div>
          </div>

          <div class='header-title'>{this.t('RUM 检索')}</div>

          <div class='mode-tab'>
            {RUM_MODE_TAB_LIST.map(item => (
              <div
                key={item.value}
                class={['mode-tab-item', { active: this.store.mode === item.value, disabled: item.disabled }]}
                onClick={() => this.handleModeChange(item)}
              >
                <i class={['icon-monitor', item.icon]} />
                <span>{item.label}</span>
              </div>
            ))}
          </div>

          <Select
            ref='applicationSelectRef'
            class='application-select'
            clearable={false}
            filterOption={this.applicationFilter}
            modelValue={this.store.appName}
            popoverOptions={{ extCls: 'rum-explore-application-select-popover' }}
            search-placeholder={this.t('请输入 关键字')}
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
                  {!this.applicationToggle && <div class='select-shortcut-keys'>{this.shortcutKeyText}</div>}
                  <span class={['icon-monitor icon-mc-arrow-down', { expand: this.applicationToggle }]} />
                </div>
              ),
              default: () =>
                this.sortedApplicationList.map(item => (
                  <Select.Option
                    id={item.app_name}
                    key={item.app_name}
                    name={item.app_alias}
                  >
                    <div class={['application-item-name', { is_top: item.isTop }]}>
                      <i
                        class={['icon-monitor', 'thumbtack', item.isTop ? 'icon-a-pinnedtuding' : 'icon-a-pintuding']}
                        onClick={event => this.handleThumbtack(event, item)}
                      />
                      <span
                        class='name-text'
                        v-overflow-tips
                      >
                        {item.app_alias}({item.app_name})
                      </span>
                    </div>
                  </Select.Option>
                )),
            }}
          </Select>
        </div>

        <div class='header-tools'>
          <TimeRange
            modelValue={this.store.timeRange}
            timezone={this.store.timezone}
            onUpdate:modelValue={this.handleTimeRangeChange}
            onUpdate:timezone={this.handleTimezoneChange}
          />
          <RefreshRate
            value={this.store.refreshInterval}
            onImmediate={this.handleImmediateRefresh}
            onSelect={this.handleRefreshChange}
          />
        </div>
      </div>
    );
  },
});
