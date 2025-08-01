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
    const users = ref<any[]>([]); // 用户列表
    const showManageDialog = ref(false); // 是否显示管理对话框
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
    const confirmCreateOrEdit = async (strategyData: any) => {
      if (strategyData === null) {
        showManageDialog.value = false;
        return;
      }

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
    const handleCloseSidebar = async () => {
      return await directoryRef.value?.handleCloseSidebar();
    };

    // 渲染表格列
    const renderTableColumns = () => {
      return [
        {
          label: t('名称'),
          minWidth: '100',
          scopedSlots: {
            default: ({ row }: any) => (
              <div class="table-ceil-container">
                <span v-bk-overflow-tips>{row.strategy_name}</span>
              </div>
            ),
          },
        },
        {
          label: t('授权目标'),
          minWidth: '100',
          scopedSlots: {
            default: ({ row }: any) => (
              <div class="table-ceil-container">
                <span v-bk-overflow-tips>
                  {row.modules.map((item: any) => item.bk_inst_name).join('; ')}
                </span>
              </div>
            ),
          },
        },
        {
          label: t('文件目录'),
          minWidth: '100',
          scopedSlots: {
            default: ({ row }: any) => (
              <div class="table-ceil-container">
                <span v-bk-overflow-tips>{row.visible_dir.join('; ')}</span>
              </div>
            ),
          },
        },
        {
          label: t('文件后缀'),
          minWidth: '100',
          scopedSlots: {
            default: ({ row }: any) => (
              <div class="table-ceil-container">
                <span v-bk-overflow-tips>{row.file_type.join('; ')}</span>
              </div>
            ),
          },
        },
        {
          label: t('执行人'),
          minWidth: '100',
          scopedSlots: {
            default: ({ row }: any) => (
              <div class="table-ceil-container">
                <span v-bk-overflow-tips>{row.operator || '--'}</span>
              </div>
            ),
          },
        },
        {
          label: t('创建时间'),
          minWidth: '100',
          prop: 'created_at',
        },
        {
          label: t('创建人'),
          minWidth: '80',
          prop: 'created_by',
        },
        {
          label: t('操作'),
          minWidth: '80',
          scopedSlots: {
            default: ({ row }: any) => (
              <div class="task-operation-container">
                <span
                  class="task-operation"
                  onClick={() => handleEditStrategy(row)}
                >
                  {t('编辑')}
                </span>
                <span
                  class="task-operation"
                  onClick={() => handleDeleteStrategy(row)}
                >
                  {t('删除')}
                </span>
              </div>
            ),
          },
        },
      ];
    };

    // 组件挂载时初始化
    onMounted(() => {
      checkManageAuth();
    });

    // 主渲染函数
    return () => (
      <div
        class="extract-auth-manage"
        v-bkloading={{ isLoading: isLoading.value }}
        data-test-id="extractAuthManage_div_extractAuthManageBox"
      >
        <div>
          <bk-button
            style="width: 120px; margin: 20px 0"
            class="king-button"
            {...{
              directives: [{
                name: 'cursor',
                value: {
                  active: isAllowedManage.value === false,
                },
              }],
            }}
            disabled={isAllowedManage.value === null || isLoading.value}
            loading={isButtonLoading.value}
            data-test-id="extractAuthManageBox_button_addNewExtractAuthManage"
            theme="primary"
            onClick={handleCreateStrategy}
          >
            {t('新增')}
          </bk-button>
        </div>
        
        <bk-table
          class="king-table"
          data={strategyList.value}
          row-key="strategy_id"
        >
          {renderTableColumns().map((column: any) => (
            <bk-table-column
              key={column.label}
              label={column.label}
              min-width={column.minWidth}
              prop={column.prop}
              scoped-slots={column.scopedSlots}
            />
          ))}
          
          <template slot="empty">
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
          </template>
        </bk-table>

        <bk-sideslider
          before-close={handleCloseSidebar}
          {...{
            on: {
              'update:is-show': (val: boolean) => {
                showManageDialog.value = val;
              },
            },
          }}
          is-show={showManageDialog.value}
          quick-close={true}
          title={type.value === 'create' ? t('新增') : t('编辑')}
          width={520}
          transfer
        >
          <template slot="content">
            {/* <DirectoryManage
              ref={directoryRef}
              v-bkloading={{ isLoading: isSliderLoading.value }}
              allow-create={allowCreate.value}
              strategy-data={strategyData.value}
              user-api={userApi.value}
              {...{
                on: {
                  confirm: confirmCreateOrEdit,
                },
              }}
            /> */}
          </template>
        </bk-sideslider>
      </div>
    );
  },
});
