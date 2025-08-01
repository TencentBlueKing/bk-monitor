import { defineComponent, ref, computed, onMounted } from 'vue';
import useStore from '@/hooks/use-store';
import useLocale from '@/hooks/use-locale';
import http from '@/api';
import * as authorityMap from '@/common/authority-map';
import EmptyStatus from '@/components/empty-status/index.vue';
import DirectoryManage from './directory-manage.vue';
import { Message, InfoBox } from 'bk-magic-vue';

import './index.scss';

export default defineComponent({
  name: 'ManageExtract',
  components: {
    DirectoryManage,
    EmptyStatus,
  },
  setup() {
    const store = useStore();
    const { t } = useLocale();
    const directoryRef = ref<any>(null);

    const isLoading = ref(true); // 页面加载状态
    const strategyList = ref<any[]>([]); // 策略列表
    const allowCreate = ref(false); // 是否允许创建
    const isAllowedManage = ref(null); // 是否有管理权限
    const isButtonLoading = ref(false); // 没有权限时点击新增按钮请求权限链接
    const showManageDialog = ref(false); // 是否显示右侧滑栏
    const isSliderLoading = ref(false); // 侧滑加载状态
    const type = ref(''); // 新增或编辑策略
    const strategyData = ref<any>({}); // 新增或编辑策略时传递的数据
    const userApi = ref(''); // 用户API
    const emptyType = ref('empty'); // 空状态类型

    // 计算属性
    const spaceUid = computed(() => store.getters.spaceUid); // 空间UID
    const bkBizId = computed(() => store.state.bkBizId); // 业务ID
    const userMeta = computed(() => store.state.userMeta); // 用户元数据

    // 检查管理权限
    const checkManageAuth = async () => {
      try {
        const res = await store.dispatch('checkAllowed', {
          action_ids: [authorityMap.MANAGE_EXTRACT_AUTH],
          resources: [
            {
              type: 'space',
              id: spaceUid.value,
            },
          ],
        });
        isAllowedManage.value = res.isAllowed;
        if (res.isAllowed) {
          initStrategyList();
          allowCreate.value = false;
          userApi.value = (window as any).BK_LOGIN_URL;
        } else {
          isLoading.value = false;
        }
      } catch (err) {
        console.warn(err);
        isLoading.value = false;
        isAllowedManage.value = false;
      }
    };

    // 初始化策略列表
    const initStrategyList = async () => {
      try {
        isLoading.value = true;
        const res = await http.request('extractManage/getStrategyList', {
          query: { bk_biz_id: bkBizId.value },
        });
        strategyList.value = res.data;
      } catch (e) {
        console.warn(e);
        emptyType.value = '500';
      } finally {
        isLoading.value = false;
      }
    };

    // 处理创建策略
    const handleCreateStrategy = async () => {
      if (!isAllowedManage.value) {
        try {
          isButtonLoading.value = true;
          const res = await store.dispatch('getApplyData', {
            action_ids: [authorityMap.MANAGE_EXTRACT_AUTH],
            resources: [
              {
                type: 'space',
                id: spaceUid.value,
              },
            ],
          });
          store.commit('updateAuthDialogData', res.data);
        } catch (err) {
          console.warn(err);
        } finally {
          isButtonLoading.value = false;
        }
        return;
      }

      type.value = 'create';
      showManageDialog.value = true;
      strategyData.value = {
        strategy_name: '',
        user_list: [],
        visible_dir: [''],
        file_type: [''],
        operator: userMeta.value.operator,
        select_type: 'topo',
        modules: [],
      };
    };

    // 处理编辑策略
    const handleEditStrategy = (row: any) => {
      type.value = 'edit';
      showManageDialog.value = true;
      strategyData.value = row;
    };

    // 处理删除策略
    const handleDeleteStrategy = (row: any) => {
      InfoBox({
        title: `${t('确定要删除')}【${row.strategy_name}】？`,
        closeIcon: false,
        confirmFn: () => confirmDeleteStrategy(row.strategy_id),
      });
    };

    // 确认删除策略
    const confirmDeleteStrategy = async (id: number) => {
      try {
        isLoading.value = true;
        await http.request('extractManage/deleteStrategy', {
          params: {
            strategy_id: id,
          },
        });
        Message({
          theme: 'success',
          message: t('删除成功'),
        });
        await initStrategyList();
      } catch (e) {
        console.warn(e);
        isLoading.value = false;
      }
    };

    // 确认创建或编辑
    const handleUpdatedTable = async (strategyData: any) => {
        
      isSliderLoading.value = true;
      const data = Object.assign(strategyData, {
        bk_biz_id: bkBizId.value,
      });

      if (type.value === 'create') {
        try {
          await http.request('extractManage/createStrategy', {
            data,
          });
          showManageDialog.value = false;
          Message({
            theme: 'success',
            message: t('创建成功'),
          });
          await initStrategyList();
        } catch (e) {
          console.warn(e);
        } finally {
          isSliderLoading.value = false;
        }
      } else if (type.value === 'edit') {
        try {
          await http.request('extractManage/updateStrategy', {
            params: {
              strategy_id: data.strategy_id,
            },
            data,
          });
          Message({
            theme: 'success',
            message: t('修改成功'),
          });
          showManageDialog.value = false;
          await initStrategyList();
        } catch (e) {
          console.warn(e);
        } finally {
          isSliderLoading.value = false;
        }
      }
    };

    // 处理操作
    const handleOperation = (type: string) => {
      if (type === 'refresh') {
        emptyType.value = 'empty';
        initStrategyList();
        return;
      }
    };

    // 处理关闭侧边栏
    const handleCloseSidebar = () => {
      InfoBox({
        title: t('确认离开当前页？'),
        subTitle: t('离开将会导致未保存信息丢失'),
        okText: t('离开'),
        cancelText: t('取消'),
        confirmFn: () => {
          showManageDialog.value = false;
        },
      });
    };

    // 组件挂载时初始化
    onMounted(() => {
      checkManageAuth();
    });

    // 表头渲染函数
    const renderHeader = (_: any, { column }: any) => <span>{column.label}</span>;

    // 主渲染函数
    return () => (
      <div
        class='extract-auth-manage'
        v-bkloading={{ isLoading: isLoading.value }}
        data-test-id='extractAuthManage_div_extractAuthManageBox'
      >
        {/* 新增按钮区域 */}
        <div>
          <bk-button
            style='width: 120px; margin: 20px 0'
            class='king-button'
            {...{
              directives: [
                {
                  name: 'cursor',
                  value: {
                    active: isAllowedManage.value === false,
                  },
                },
              ],
            }}
            disabled={isAllowedManage.value === null || isLoading.value}
            loading={isButtonLoading.value}
            data-test-id='extractAuthManageBox_button_addNewExtractAuthManage'
            theme='primary'
            onClick={handleCreateStrategy}
          >
            {t('新增')}
          </bk-button>
        </div>

        {/* 策略列表表格 */}
        <bk-table
          class='king-table'
          data={strategyList.value}
          row-key='strategy_id'
          scopedSlots={{
            empty: () => (
              <div>
                <EmptyStatus
                  empty-type={emptyType.value}
                  {...{
                    on: {
                      operation: handleOperation,
                    },
                  }}
                />
              </div>
            ),
          }}
        >
          {/* 名称列 */}
          <bk-table-column
            label={t('名称')}
            min-width='100'
            renderHeader={renderHeader}
            scopedSlots={{
              default: ({ row }: any) => (
                <div class='table-ceil-container'>
                  <span v-bk-overflow-tips>{row.strategy_name}</span>
                </div>
              ),
            }}
          />

          {/* 授权目标列 */}
          <bk-table-column
            label={t('授权目标')}
            min-width='100'
            renderHeader={renderHeader}
            scopedSlots={{
              default: ({ row }: any) => (
                <div class='table-ceil-container'>
                  <span v-bk-overflow-tips>{row.modules.map((item: any) => item.bk_inst_name).join('; ')}</span>
                </div>
              ),
            }}
          />

          {/* 文件目录列 */}
          <bk-table-column
            label={t('文件目录')}
            min-width='100'
            renderHeader={renderHeader}
            scopedSlots={{
              default: ({ row }: any) => (
                <div class='table-ceil-container'>
                  <span v-bk-overflow-tips>{row.visible_dir.join('; ')}</span>
                </div>
              ),
            }}
          />

          {/* 文件后缀列 */}
          <bk-table-column
            label={t('文件后缀')}
            min-width='100'
            renderHeader={renderHeader}
            scopedSlots={{
              default: ({ row }: any) => (
                <div class='table-ceil-container'>
                  <span v-bk-overflow-tips>{row.file_type.join('; ')}</span>
                </div>
              ),
            }}
          />

          {/* 执行人列 */}
          <bk-table-column
            label={t('执行人')}
            min-width='100'
            renderHeader={renderHeader}
            scopedSlots={{
              default: ({ row }: any) => (
                <div class='table-ceil-container'>
                  <span v-bk-overflow-tips>{row.operator || '--'}</span>
                </div>
              ),
            }}
          />

          {/* 创建时间列 */}
          <bk-table-column
            label={t('创建时间')}
            min-width='100'
            prop='created_at'
            renderHeader={renderHeader}
          />

          {/* 创建人列 */}
          <bk-table-column
            label={t('创建人')}
            min-width='80'
            prop='created_by'
            renderHeader={renderHeader}
          />

          {/* 操作列 */}
          <bk-table-column
            label={t('操作')}
            min-width='80'
            renderHeader={renderHeader}
            scopedSlots={{
              default: ({ row }: any) => (
                <div class='task-operation-container'>
                  <span
                    class='task-operation'
                    onClick={() => handleEditStrategy(row)}
                  >
                    {t('编辑')}
                  </span>
                  <span
                    class='task-operation'
                    onClick={() => handleDeleteStrategy(row)}
                  >
                    {t('删除')}
                  </span>
                </div>
              ),
            }}
          />
        </bk-table>

        {/* 侧边栏弹窗 - 用于新增/编辑策略 */}
        <bk-sideslider
          width={520}
          is-show={showManageDialog.value}
          quick-close={true}
          show-mask={true}
          title={type.value === 'create' ? t('新增') : t('编辑')}
          transfer
          onAnimation-end={handleCloseSidebar}
        >
          {/* 侧边栏内容区域 */}
          <template slot='content'>
            {/* 目录管理组件 */}
            <DirectoryManage
              ref={directoryRef}
              v-bkloading={{ isLoading: isSliderLoading.value }}
              allowCreate={allowCreate.value}
              strategyData={strategyData.value}
              userApi={userApi.value}
              onHandleUpdatedTable={handleUpdatedTable}
              onHandleCancelSlider={handleCloseSidebar}
            />
          </template>
        </bk-sideslider>
      </div>
    );
  },
});
