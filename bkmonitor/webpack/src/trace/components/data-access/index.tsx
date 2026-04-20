/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { type PropType, computed, defineComponent, onMounted, reactive, shallowRef, watch } from 'vue';

import { Exception, Loading, Popover, Select } from 'bkui-vue';
import { fetchConfigList, fetchGlobalVariables } from 'monitor-api/modules/incident';
import { useI18n } from 'vue-i18n';

import { useAppStore } from '../../store/modules/app';
import DataAccessEmpty from '../data-access-empty';

import type {
  ConfigListData,
  DataSourceContent,
  FetchConfigListParams,
  ModuleCell,
} from '../../typings/incident-config';

import './index.scss';

/** 空间信息 */
export interface SpaceInfo {
  bk_biz_id: number;
  space_id: number | string;
  space_name: string;
}
type ConnectStatus = 'connect' | 'empty' | 'unconnect';
type RequirementType = 'at_least_one' | 'optional' | 'required';

interface StatusConfig {
  connectStatus: ConnectStatus;
  requirement: RequirementType;
}

const STATUS_MAP: Record<string, RequirementType> = {
  required: 'required',
  optional: 'optional',
  has_min_one_selection: 'at_least_one',
};

export default defineComponent({
  name: 'DataAccess',
  props: {
    /** 空间列表 */
    spaceList: {
      type: Array as PropType<SpaceInfo[]>,
      required: true as const,
    },
    /** 展示模式：empty-空状态（默认），guide-接入指引 */
    mode: {
      type: String as PropType<'empty' | 'guide'>,
      default: 'empty',
    },
    /** 所选空间总数（guide 模式下用于展示 count） */
    totalCount: {
      type: Number,
      default: 0,
    },
    /** 是否暗色背景 */
    isDarkTheme: {
      type: Boolean,
      default: false,
    },
    /** 已开启故障分析功能的空间 bizId 列表，传入后"一键开启"按钮根据下拉框选中空间动态判断 */
    enabledBizIds: {
      type: Array as PropType<number[]>,
      default: () => [],
    },
    /** 是否展示"一键开启"按钮，设为 false 时强制隐藏 */
    showEnableButton: {
      type: Boolean,
      default: true,
    },
    /** bk助手链接 */
    wxCsLink: {
      type: String,
      default: '',
    },
  },
  emits: ['enabled'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const appStore = useAppStore();
    const REQUIREMENT_TEXT_MAP: Record<RequirementType, string> = {
      required: t('必选项'),
      optional: t('可选项'),
      at_least_one: t('至少必须有一项'),
    };

    const LEGEND_COLORS = [
      { label: t('绿色：已接入'), cls: 'connected' },
      { label: t('红色：未接入'), cls: 'disconnected' },
    ];

    /** 当前选中的空间 ID（v-model 绑定） */
    const selectedSpace = shallowRef<number>(Number(props.spaceList[0].bk_biz_id));

    /** 当前选中空间是否未开启故障分析功能，动态控制"一键开启"按钮展示 */
    const shouldShowEnableButton = computed(() => {
      // 外部明确设为 false 时直接隐藏
      if (!props.showEnableButton) return false;
      // 有 enabledBizIds 时根据当前选中空间动态判断
      if (props.enabledBizIds.length) {
        return !props.enabledBizIds.includes(selectedSpace.value);
      }
      return true;
    });
    /** 数据类型列表 */
    const dataTypes = shallowRef<{ id: string; name: string }[]>([]);
    /** 模块列表 */
    const moduleList = shallowRef<{ id: string; name: string }[]>([]);
    /** 状态数据，key 为 "数据类型-模块" 的组合 */
    const statusData = reactive<Record<string, null | StatusConfig>>({});
    /** 表格加载状态 */
    const tableLoading = shallowRef(false);
    /** 接口返回的全局变量 */
    const globalVariables = shallowRef<Record<string, { category: string; desc: string; name: string; value: string }>>(
      {}
    );
    /** 数据类型 → 拼接好的跳转链接（加载 globalVariables 后计算） */
    const dataTypeLinks = shallowRef<Record<string, string>>({});

    const getKey = (moduleId: string, dataTypeId: string) => `${moduleId}_${dataTypeId}`;

    const getStatusConfig = (moduleId: string, dataTypeId: string): null | StatusConfig =>
      statusData[getKey(moduleId, dataTypeId)] || null;

    const getCellBgClass = (moduleId: string, dataTypeId: string) => {
      const config = getStatusConfig(moduleId, dataTypeId);
      if (!config || config.connectStatus === 'empty') return '';
      return config.connectStatus === 'connect' ? 'cell-connected' : 'cell-disconnected';
    };

    const getRequirementText = (moduleId: string, dataTypeId: string) => {
      const config = getStatusConfig(moduleId, dataTypeId);
      return config ? REQUIREMENT_TEXT_MAP[config.requirement] || '' : '';
    };

    const getCellTextClass = (moduleId: string, dataTypeId: string) => {
      const config = getStatusConfig(moduleId, dataTypeId);
      if (!config || config.connectStatus === 'empty') return 'text-default';
      return config.connectStatus === 'connect' ? 'text-green' : 'text-red';
    };

    const getModuleUnmetTip = (moduleId: string): string => {
      const hasUnmet = dataTypes.value.some(dt => {
        const config = getStatusConfig(moduleId, dt.id);
        if (!config) return false;
        if (config.requirement === 'required' && config.connectStatus === 'unconnect') return true;
        if (config.requirement === 'at_least_one') {
          const atLeastOneMet = dataTypes.value.some(dt2 => {
            const c2 = getStatusConfig(moduleId, dt2.id);
            return c2?.requirement === 'at_least_one' && c2.connectStatus === 'connect';
          });
          if (!atLeastOneMet) return true;
        }
        return false;
      });
      return hasUnmet ? t('当前功能不满足数据接入要求') : '';
    };

    const parseStatusData = (content: DataSourceContent) => {
      const configArr = content.config || [];
      const labelsArr = content.labels || [];

      dataTypes.value = configArr.map(item => ({
        id: item.name,
        name: item.display_name || item.name,
      }));

      moduleList.value = labelsArr.map(item => ({
        id: item.name,
        name: item.display_name || item.name,
      }));

      const configMap: Record<string, Record<string, ModuleCell>> = {};
      for (const item of configArr) {
        configMap[item.name] = item.module || {};
      }

      for (const dt of dataTypes.value) {
        const dtModules = configMap[dt.id] || {};
        for (const mod of moduleList.value) {
          const cell = dtModules[mod.id];
          statusData[getKey(mod.id, dt.id)] =
            cell?.select_status && cell.select_status !== 'empty'
              ? {
                  connectStatus: cell.connect_status || 'empty',
                  requirement: (STATUS_MAP[cell.select_status] || cell.select_status) as RequirementType,
                }
              : null;
        }
      }
    };

    const loadStatusData = async () => {
      // 清空旧数据，避免切换空间时残留
      dataTypes.value = [];
      moduleList.value = [];
      for (const key of Object.keys(statusData)) {
        delete statusData[key];
      }
      try {
        const res = await fetchConfigList<FetchConfigListParams, ConfigListData<DataSourceContent>>({
          config_type: 'data_source',
          scope_type: 'bkcc',
          bk_biz_id: selectedSpace.value,
        });
        const list = res.objects || [];
        if (list[0]?.content) {
          parseStatusData(list[0].content);
        }
      } catch (e) {
        console.error(e);
      }
    };

    const loadLinkMap = async () => {
      try {
        const res = await fetchGlobalVariables({ bk_biz_id: selectedSpace.value });
        globalVariables.value = res?.variables || {};
        buildDataTypeLinks();
      } catch (e) {
        console.error(e);
      }
    };

    /** 根据接口返回的平台 URL 拼接各数据类型的跳转链接 */
    const buildDataTypeLinks = () => {
      const bizId = String(selectedSpace.value);
      const vars = globalVariables.value;
      const resolve = (key: string, path: string) => (vars[key]?.value ? vars[key].value + path : '');
      const currentSpace = appStore.bizList?.find(item => item.bk_biz_id === selectedSpace.value);
      const spaceUid = currentSpace ? `${currentSpace.space_type_id}_${currentSpace.space_id}` : '';
      dataTypeLinks.value = {
        alert: resolve('bkmonitor_url', `?bizId=${bizId}#/strategy-config`),
        metric_ebpf: '',
        apm: resolve('bkmonitor_url', `?bizId=${bizId}#/apm/home`),
        metric: resolve('bkmonitor_url', `?bizId=${bizId}#/custom-metric`),
        log: resolve('bklog_url', `/#/manage/log-collection/collection-item/list?bizId=${bizId}`),
        event: resolve('bkmonitor_url', `?bizId=${bizId}#/custom-event`),
        knowledge:
          window.bk_incident_saas_host && spaceUid
            ? `${window.bk_incident_saas_host}${spaceUid}/space/setting/knowledge`
            : '',
      };
    };

    /** 获取功能模块的白皮书链接（category: docs） */
    const getModuleDocUrl = (moduleId: string): string => {
      const item = globalVariables.value[moduleId];
      return item?.category === 'docs' && item.value ? item.value : '';
    };

    /** 点击数据列表头，跳转到该数据的接入页 */
    const handleDataHeaderClick = (dataTypeId: string) => {
      const url = dataTypeLinks.value[dataTypeId];
      if (!url) return;
      window.open(url, '_blank');
    };

    /** 点击功能模块名，跳转白皮书链接 */
    const handleModuleClick = (moduleId: string) => {
      const url = getModuleDocUrl(moduleId);
      if (url) {
        window.open(url, '_blank');
      }
    };

    /** 加载数据接入表格 */
    const loadTableData = async () => {
      tableLoading.value = true;
      dataTypes.value = [];
      moduleList.value = [];
      for (const key of Object.keys(statusData)) {
        delete statusData[key];
      }
      try {
        await loadStatusData();
        await loadLinkMap();
      } catch (e) {
        console.error(e);
      } finally {
        tableLoading.value = false;
      }
    };

    onMounted(() => {
      loadTableData();
    });

    /** 切换空间时重新加载表格数据 */
    watch(selectedSpace, () => {
      loadTableData();
    });

    /** 渲染空状态 */
    const renderEmptyStatus = () => {
      return (
        <DataAccessEmpty
          class='incident-empty-status'
          isDarkTheme={props.isDarkTheme}
          mode={props.mode}
          selectedSpaceId={selectedSpace.value}
          showEnableButton={shouldShowEnableButton.value}
          spaceList={props.spaceList}
          totalCount={props.totalCount}
          wxCsLink={props.wxCsLink}
          onEnabled={() => emit('enabled')}
        />
      );
    };

    return () => {
      return (
        <Loading
          class='data-access-container'
          color={props.isDarkTheme ? '#292A2B' : undefined}
          loading={tableLoading.value}
        >
          {renderEmptyStatus()}
          <div class={['data-access-table', { 'data-access-table-dark': props.isDarkTheme }]}>
            <div class='legend-area'>
              {props.spaceList.length > 1 ? (
                <div class='legend-select-wrapper'>
                  <Select
                    class='legend-select'
                    v-model={selectedSpace.value}
                    behavior='simplicity'
                    clearable={false}
                  >
                    {props.spaceList.map(space => (
                      <Select.Option
                        id={space.bk_biz_id}
                        key={space.space_id}
                        name={`${space.space_name} (#${space.space_id})`}
                      />
                    ))}
                  </Select>
                  <div class='legend-select-desc'>
                    <i class='icon-monitor icon-hint' />
                    {t('可以切换查看不同空间的接入数据情况')}
                  </div>
                </div>
              ) : (
                <span class='legend-space-name'>
                  {`${props.spaceList[0].space_name} (#${props.spaceList[0].space_id})`}
                </span>
              )}
              <div class='legend-item-wrapper'>
                {LEGEND_COLORS.map(item => (
                  <div
                    key={item.label}
                    class='legend-item'
                  >
                    <span class={['color-block', item.cls]} />
                    <span>{item.label}</span>
                  </div>
                ))}
              </div>
            </div>
            <table
              class={['status-table', { 'status-table--empty': moduleList.value.length === 0 && !tableLoading.value }]}
            >
              <thead>
                <tr>
                  <th class='module-col diagonal-header-cell'>
                    <div class='diagonal-header'>
                      <span class='label-bottom'>{t('功能模块')}</span>
                      <span class='label-top'>{t('数据')}</span>
                    </div>
                  </th>
                  {dataTypes.value.map(dt => (
                    <th
                      key={dt.id}
                      class={['data-col', { clickable: !!dataTypeLinks.value[dt.id] }]}
                      onClick={() => handleDataHeaderClick(dt.id)}
                    >
                      {dt.id === 'metric_ebpf' ? (
                        <Popover
                          content={t('尚未开放自主接入，请联系管理员')}
                          placement='top'
                          theme='dark'
                        >
                          <span class='data-header-text'>{dt.name}</span>
                        </Popover>
                      ) : (
                        <span class='data-header-text'>{dt.name}</span>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {moduleList.value.length === 0 && !tableLoading.value && (
                  <tr>
                    <td
                      class='empty-no-data'
                      colspan={dataTypes.value.length + 1}
                    >
                      <Exception
                        scene='part'
                        title={t('暂无数据')}
                        type='empty'
                      />
                    </td>
                  </tr>
                )}
                {moduleList.value.map(mod => (
                  <tr key={mod.id}>
                    <td
                      class={[
                        'module-cell',
                        { 'module-disabled': getModuleUnmetTip(mod.id), clickable: !!getModuleDocUrl(mod.id) },
                      ]}
                      onClick={() => getModuleDocUrl(mod.id) && handleModuleClick(mod.id)}
                    >
                      {getModuleUnmetTip(mod.id) ? (
                        <Popover
                          v-slots={{
                            content: () => <span>{getModuleUnmetTip(mod.id)}</span>,
                          }}
                          offset={{ mainAxis: 6, crossAxis: 0 }}
                          placement='right'
                          popover-delay={[100, 0]}
                          theme='dark'
                          trigger='hover'
                        >
                          <span class='module-inner'>
                            <span class='module-name'>{mod.name}</span>
                            <i class='icon-monitor icon-zhongzhi module-tip-icon' />
                          </span>
                        </Popover>
                      ) : (
                        <span class='module-inner'>
                          <span class='module-name'>{mod.name}</span>
                        </span>
                      )}
                    </td>
                    {dataTypes.value.map(dt => (
                      <td
                        key={dt.id}
                        class={['status-cell', getCellBgClass(mod.id, dt.id)]}
                      >
                        {getStatusConfig(mod.id, dt.id) ? (
                          getStatusConfig(mod.id, dt.id)!.connectStatus === 'empty' ? (
                            <i class='icon-monitor bk-incident-icon icon-minus-line' />
                          ) : (
                            <span class={['cell-text', getCellTextClass(mod.id, dt.id)]}>
                              {getRequirementText(mod.id, dt.id)}
                            </span>
                          )
                        ) : (
                          <span class='cell-dash'>-</span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Loading>
      );
    };
  },
});
