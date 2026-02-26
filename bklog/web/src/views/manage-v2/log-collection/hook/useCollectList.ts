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

import { computed, ref } from 'vue';

import * as authorityMap from '@/common/authority-map';
import { projectManages } from '@/common/util';
import useStore from '@/hooks/use-store';
import { useRouter, useRoute } from 'vue-router/composables';
import { getOperatorCanClick } from '../utils';
import type {
  CollectOperateType,
  CollectTypeKey,
  IAuthApplyDataParams,
  ICheckAllowedResponse,
  ICollectListRowData,
  IGetApplyDataResponse,
} from '../type';

type IndexSetId = number | string;

type RouteName =
  | 'collection-item-list'
  | 'collectStop'
  | 'collectAdd'
  | 'collectEdit'
  | 'collectField'
  | 'collectStorage'
  | 'collectMasking'
  | 'manage-collection'
  | 'retrieve'
  | string;

/**
 * 采集列表的自定义 Hook
 */
export const useCollectList = () => {
  const store = useStore();
  const router = useRouter();
  const route = useRoute();
  const loadingStatus = ref(false);
  const isAllowedCreate = ref<boolean | null>(null);
  const isTableLoading = ref(false);
  const spaceUid = computed(() => store.getters.spaceUid);
  const bkBizId = computed(() => store.getters.bkBizId);
  const authGlobalInfo = computed(() => store.getters['globals/authContainerInfo']);
  const isShowMaskingTemplate = computed(() => store.getters.isShowMaskingTemplate);
  const collectProject = computed(() => projectManages(store.state.topMenu, 'collection-item'));
  /**
   * 跳转到采集项列表
   */
  const goListPage = () => {
    router.push({
      name: 'collection-item-list',
      query: {
        bizId: bkBizId.value,
        spaceUid: spaceUid.value,
      },
    });
  };

  /**
   * 是否有创建权限
   */
  const checkCreateAuth = async () => {
    try {
      const res = (await store.dispatch('checkAllowed', {
        action_ids: [authorityMap.CREATE_COLLECTION_AUTH],
        resources: [
          {
            type: 'space',
            id: spaceUid.value,
          },
        ],
      })) as ICheckAllowedResponse;
      isAllowedCreate.value = Boolean(res?.isAllowed);
    } catch (err) {
      console.log(err);
      isAllowedCreate.value = false;
    }
  };

  const buildSpaceCreateApplyData = (): IAuthApplyDataParams => ({
    action_ids: [authorityMap.CREATE_COLLECTION_AUTH],
    resources: [{ type: 'space', id: spaceUid.value }],
  });

  const buildCollectionApplyData = (actionId: string, collectorId: IndexSetId | undefined): IAuthApplyDataParams => ({
    action_ids: [actionId],
    resources: [{ type: 'collection', id: collectorId ?? '' }],
  });

  const buildIndicesApplyData = (actionId: string, indexSetId: IndexSetId | undefined): IAuthApplyDataParams => ({
    action_ids: [actionId],
    resources: [{ type: 'indices', id: indexSetId ?? '' }],
  });
  /**
   * 获取授权数据
   * @param paramData
   */
  const getOptionApplyData = async (paramData: IAuthApplyDataParams) => {
    try {
      isTableLoading.value = true;
      const res = (await store.dispatch('getApplyData', paramData)) as IGetApplyDataResponse;
      store.commit('updateAuthDialogData', res?.data);
    } catch (err) {
      console.log(err);
    } finally {
      isTableLoading.value = false;
    }
  };
  /**
   * leaveCurrentPage：根据操作类型跳转到对应页面，并拼装必要的路由参数
   * - 这里不做权限判断（由 operateHandler 负责），只处理“是否允许跳转/如何跳转”
   */
  const leaveCurrentPage = (
    row: ICollectListRowData,
    operateType: CollectOperateType,
    typeKey: CollectTypeKey,
    indexSetId: IndexSetId | 'all',
  ) => {
    // indexSetId === 'all' 表示“全部索引集”，此时不需要透传 indexSetId
    const indexId = indexSetId !== 'all' ? indexSetId : undefined;

    /**
     * 1) 采集状态页（status）相关的前置拦截
     * - 已停用(terminated) 禁止再次操作状态
     * - 若 status 缺失，视为“未完成”，直接进入编辑页补齐配置
     */
    if (operateType === 'status') {
      if (!loadingStatus.value || row.status === 'terminated') return;
      if (!row.status) return operateHandler(row, 'edit', typeKey);
    }

    /**
     * 2) 启用/停用（start/stop）前置拦截
     * - running/prepare 状态不允许启用/停用（原逻辑用 row.status === 'running' + loadingStatus 判断）
     * - collectProject 为 false 时（非采集项目）不允许进行启停操作
     * - stop：容器采集项需要跳转到停用页展示状态页（collectStop）
     *
     * 注意：start 的“启用”实际执行逻辑在其他地方实现，这里仅保持原逻辑的拦截与跳转行为
     */
    if (operateType === 'start' || operateType === 'stop') {
      if (!loadingStatus.value || row.status === 'running' || !collectProject.value) return;
      if (operateType === 'stop') {
        router.push({
          name: 'collectStop',
          // vue-router 的 params/query 在类型层面更倾向于 string，这里统一做 string 化
          params: { collectorId: String(row.collector_config_id ?? '') },
          query: { spaceUid: String(spaceUid.value) },
        });
      }
      return;
    }

    /**
     * 3) 通用路由映射：操作类型 → 目标路由
     * - 部分操作实际复用同一个页面，通过 query.step / query.type 等参数区分子步骤
     */
    const routeMap: Record<string, RouteName> = {
      add: 'collectAdd',
      view: 'manage-collection',
      status: 'manage-collection',
      edit: 'collectEdit',
      field: 'collectField',
      search: 'retrieve',
      clean: 'collectEdit',
      storage: 'collectEdit',
      clone: 'collectAdd',
      masking: 'collectMasking',
    };

    const targetRoute = routeMap[operateType] ?? (operateType as RouteName);

    // 路由参数/查询参数统一在这里构建，最后一次性 push，方便维护
    const params: Record<string, string> = {};
    const query: Record<string, string | undefined> = { typeKey: String(typeKey) };
    let backRoute: string | null = null;

    // 透传当前“索引集上下文”（非 all 时才传）
    if (indexId) query.indexSetId = String(indexId);

    /**
     * 4) 查看详情（manage-collection）特殊处理
     * - 未完成（table_id 为空）时，详情页不可用，应回到编辑补齐
     */
    if (targetRoute === 'manage-collection' && !row.table_id) {
      return operateHandler(row, 'edit', typeKey);
    }

    /**
     * 5) collectorId 参数拼装
     * - 这些页面都依赖 collectorId 获取/回显配置
     */
    if (
      ['manage-collection', 'collectEdit', 'collectField', 'collectStorage', 'collectMasking'].includes(targetRoute)
    ) {
      params.collectorId = String(row.collector_config_id ?? '');
    }

    /**
     * 6) 不同操作的 query/params 补充
     */
    if (operateType === 'search') {
      // 检索：需要 indexId（优先 index_set_id，否则取 bkdata_index_set_ids 的第一个）
      const bkdataIds = row.bkdata_index_set_ids ?? [];
      if (!(row.index_set_id || bkdataIds.length)) return;
      params.indexId = String(row.index_set_id ? row.index_set_id : bkdataIds[0]);
      // pid 用于在检索页定位父索引集（存在 indexId 时才拼）
      query.pid = indexId ? JSON.stringify([String(indexId)]) : undefined;
    }

    if (operateType === 'clean') {
      // 清洗：复用编辑页，通过 step=2 定位到清洗配置步骤
      query.step = String(2);
      params.collectorId = String(row.collector_config_id ?? '');
      // ITSM 申请中：跳转字段配置（field）继续推进流程
      if (row.itsm_ticket_status === 'applying') return operateHandler(row, 'field', typeKey);
      // 回退路径：用于编辑页返回列表
      backRoute = route.name;
    }

    if (operateType === 'storage') {
      // 存储：复用编辑页，通过 step=3 定位到存储设置步骤
      query.step = String(3);
    }

    if (operateType === 'clone') {
      // 克隆：复用新建页，通过 query 回显源采集项配置
      params.collectorId = String(row.collector_config_id ?? '');
      query.collectorId = String(row.collector_config_id ?? '');
      query.type = 'clone';
    }

    if (operateType === 'masking') {
      // 脱敏：直接进入脱敏页，并隐藏左侧步骤条（通过 type=masking 控制）
      query.type = 'masking';
    }

    if (operateType === 'status') {
      // 状态：详情页的一个子视图标识
      query.type = 'collectionStatus';
    }

    if (operateType === 'edit') {
      // bkdata/es 的编辑：后端使用 index_set_id 作为 collectorId
      if (['bkdata', 'es'].includes(typeKey)) params.collectorId = String(row.index_set_id ?? '');
    }

    // 记录当前操作对象，供目标页回显/继续编辑使用
    store.commit('collect/setCurCollect', row);

    const finalQuery = {
      ...query,
      spaceUid: String(store.state.spaceUid),
      backRoute: backRoute ?? undefined,
    };

    // 操作在新标签页打开
    const resolved = router.resolve({
      name: targetRoute,
      params,
      query: finalQuery,
    });
    window.open(resolved.href, '_blank');
  };

  const operateHandler = (
    row: ICollectListRowData,
    operateType: CollectOperateType,
    typeKey: CollectTypeKey,
    indexSetId: IndexSetId | 'all' = 'all',
  ) => {
    /**
     * operateHandler：负责“是否可点击 + 权限校验（必要时拉起申请弹窗）”，通过后再进入 leaveCurrentPage 做跳转
     * - 权限规则保持与原实现一致：
     *   - add：用 isAllowedCreate 控制（空间创建权限）
     *   - view：校验 VIEW_COLLECTION_AUTH
     *   - search：校验 SEARCH_LOG_AUTH（indices 资源）
     *   - 其他操作：校验 MANAGE_COLLECTION_AUTH（collection 资源）
     */

    // 1) 前置：不可点击直接返回（例如“未完成/运行中”限制等）
    if (!getOperatorCanClick(row, operateType)) return;

    // 2) 按操作类型做权限校验（表驱动），避免大量 if/else
    const guards: Array<{
      match: (_t: CollectOperateType) => boolean;
      isAllowed: () => boolean;
      buildApplyData: () => IAuthApplyDataParams;
    }> = [
      {
        match: _t => _t === 'add',
        isAllowed: () => Boolean(isAllowedCreate.value),
        buildApplyData: () => buildSpaceCreateApplyData(),
      },
      {
        match: _t => _t === 'view',
        isAllowed: () => Boolean(row.permission?.[authorityMap.VIEW_COLLECTION_AUTH]),
        buildApplyData: () => buildCollectionApplyData(authorityMap.VIEW_COLLECTION_AUTH, row.collector_config_id),
      },
      {
        match: _t => _t === 'search',
        isAllowed: () => Boolean(row.permission?.[authorityMap.SEARCH_LOG_AUTH]),
        buildApplyData: () => buildIndicesApplyData(authorityMap.SEARCH_LOG_AUTH, row.index_set_id),
      },
      {
        // 原逻辑：除 add/view/search 外，统一按“管理权限”兜底
        match: _t => !['add', 'view', 'search'].includes(String(_t)),
        isAllowed: () => Boolean(row.permission?.[authorityMap.MANAGE_COLLECTION_AUTH]),
        buildApplyData: () => buildCollectionApplyData(authorityMap.MANAGE_COLLECTION_AUTH, row.collector_config_id),
      },
    ];

    for (const guard of guards) {
      if (!guard.match(operateType)) continue;
      if (!guard.isAllowed()) return getOptionApplyData(guard.buildApplyData());
      break;
    }

    // 3) 通过权限校验后，交由 leaveCurrentPage 统一处理跳转
    leaveCurrentPage(row, operateType, typeKey, indexSetId);
  };

  return {
    spaceUid,
    bkBizId,
    authGlobalInfo,
    isShowMaskingTemplate,

    checkCreateAuth,
    operateHandler,
    goListPage,
  };
};
