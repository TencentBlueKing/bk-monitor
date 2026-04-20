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

import { type PropType, defineComponent, onMounted, reactive, shallowRef, watch } from 'vue';

import { Exception, Loading, Popover } from 'bkui-vue';
import { fetchConfigList, fetchGlobalVariables } from 'monitor-api/modules/incident';
import { useI18n } from 'vue-i18n';

import { useAppStore } from '../../store/modules/app';

import type {
  ConfigListData,
  DataSourceContent,
  FetchConfigListParams,
  ModuleCell,
} from '../../typings/incident-config';

import './index.scss';

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
    bkBizId: {
      type: [Number, String] as PropType<number | string>,
      default: undefined,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const appStore = useAppStore();
    const REQUIREMENT_TEXT_MAP: Record<RequirementType, string> = {
      required: t('必须项'),
      optional: t('可选项'),
      at_least_one: t('至少必须有一项'),
    };

    const LEGEND_COLORS = [
      { label: t('绿色：已接入'), cls: 'connected' },
      { label: t('红色：未接入'), cls: 'disconnected' },
    ];

    const dataTypes = shallowRef<{ id: string; name: string }[]>([]);
    const moduleList = shallowRef<{ id: string; name: string }[]>([]);
    const statusData = reactive<Record<string, null | StatusConfig>>({});
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
            return c2 && c2.requirement === 'at_least_one' && c2.connectStatus === 'connect';
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
      tableLoading.value = true;
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
          ...(props.bkBizId != null ? { bk_biz_id: Number(props.bkBizId) } : {}),
        });
        const list = res.objects || [];
        if (list[0]?.content) {
          parseStatusData(list[0].content);
        }
      } catch (e) {
        console.error(e);
      } finally {
        tableLoading.value = false;
      }
    };

    const loadLinkMap = async () => {
      try {
        const res = await fetchGlobalVariables(props.bkBizId != null ? { bk_biz_id: props.bkBizId } : undefined);
        globalVariables.value = res?.variables || {};
        buildDataTypeLinks();
      } catch (e) {
        console.error(e);
      }
    };

    /** 根据接口返回的平台 URL 拼接各数据类型的跳转链接 */
    const buildDataTypeLinks = () => {
      const bizId = String(props.bkBizId ?? '');
      const vars = globalVariables.value;
      const resolve = (key: string, path: string) => (vars[key]?.value ? vars[key].value + path : '');
      const currentSpace = appStore.bizList?.find(item => item.bk_biz_id === props.bkBizId);
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

    onMounted(() => {
      loadStatusData();
      loadLinkMap();
    });

    watch(
      () => props.bkBizId,
      () => {
        loadStatusData();
        loadLinkMap();
      }
    );

    return () => (
      <div class='data-access-container'>
        <Loading
          class='table-wrapper'
          loading={tableLoading.value}
        >
          <table class='status-table'>
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
                    class='empty-cell'
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
                          <i class='icon-monitor bk-incident-icon icon-zhongzhi module-tip-icon' />
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
        </Loading>
        <div class='legend-area'>
          {LEGEND_COLORS.map(item => (
            <div
              key={item.label}
              class='legend-item'
            >
              <span class={['color-block', item.cls]}></span>
              <span>{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    );
  },
});
