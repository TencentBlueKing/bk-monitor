import { defineComponent, ref, reactive, computed, watch, nextTick } from 'vue';
import useStore from '@/hooks/use-store';
import useLocale from '@/hooks/use-locale';
import http from '@/api';
// @ts-ignore
import ModuleSelect from './module-select';
// @ts-ignore
import ValidateInput from './validate-input';
// @ts-ignore
import ValidateUserSelector from './validate-user-selector';

import './config-slider.scss';

export default defineComponent({
  name: 'ConfigSlider',
  components: {
    ModuleSelect,
    ValidateInput,
    ValidateUserSelector,
  },
  props: {
    strategyData: {
      type: Object,
      default: () => ({
        strategy_name: '',
        user_list: [],
        visible_dir: [''],
        file_type: [''],
        select_type: '',
        modules: [],
        operator: '',
      }),
    },
    userApi: {
      type: String,
      required: true,
    },
    allowCreate: {
      type: Boolean,
      required: true,
    },
    onHandleUpdatedTable: { type: Function },
    onHandleCancelSlider: { type: Function },
  },
  emits: ['handleUpdatedTable', 'handleCancelSlider'],
  setup(props, { emit }) {
    const store = useStore();
    const { t } = useLocale();

    // 响应式数据
    const isChangeOperatorLoading = ref(false); // 修改执行人加载状态
    const showSelectDialog = ref(false); // 是否显示选择对话框
    const manageStrategyData = reactive(JSON.parse(JSON.stringify(props.strategyData))); // 管理策略数据

    // 初始化数据，避免后台造的数据为空数组
    if (!manageStrategyData.visible_dir?.length) {
      manageStrategyData.visible_dir = [''];
    }
    if (!manageStrategyData.file_type?.length) {
      manageStrategyData.file_type = [''];
    }

    // 计算属性
    const isValidated = computed(() => {
      return (
        manageStrategyData.strategy_name &&
        manageStrategyData.user_list.length &&
        manageStrategyData.visible_dir.every((item: string) => Boolean(validateVisibleDir(item))) &&
        manageStrategyData.file_type.every((item: string) => Boolean(validateFileExtension(item))) &&
        manageStrategyData.modules.length &&
        manageStrategyData.operator
      );
    });

    // 监听 props 变化，更新本地数据
    watch(
      () => props.strategyData,
      newVal => {
        Object.assign(manageStrategyData, JSON.parse(JSON.stringify(newVal)));
        if (!manageStrategyData.visible_dir?.length) {
          manageStrategyData.visible_dir = [''];
        }
        if (!manageStrategyData.file_type?.length) {
          manageStrategyData.file_type = [''];
        }
      },
      { deep: true },
    );

    // 校验授权目录
    const validateVisibleDir = (val: string) => {
      // 只允许：数字 字母 _-./
      // 不得出现 ./
      // 必须以 / 开头
      // 必须以 / 结尾
      return !/[^\w\-\.\/]/.test(val) && !/\.\//.test(val) && val.startsWith('/') && val.endsWith('/');
    };

    // 校验文件后缀
    const validateFileExtension = (val: string) => {
      return !val.startsWith('.') && val;
    };

    // 添加授权目录
    const handleAddVisibleDir = () => {
      manageStrategyData.visible_dir.push('');
      nextTick(() => {
        const inputList = document.querySelectorAll('.visible-dir input');
        if (inputList.length > 0) {
          (inputList[inputList.length - 1] as HTMLInputElement).focus();
        }
      });
    };

    // 添加文件类型
    const handleAddFileType = () => {
      manageStrategyData.file_type.push('');
      nextTick(() => {
        const inputList = document.querySelectorAll('.file-type input');
        if (inputList.length > 0) {
          (inputList[inputList.length - 1] as HTMLInputElement).focus();
        }
      });
    };

    // 确认选择
    const handleConfirmSelect = (selectType: string, modules: any[]) => {
      manageStrategyData.select_type = selectType;
      manageStrategyData.modules = modules;
    };

    // 修改执行人
    const changeOperator = async () => {
      const { operator } = store.state.userMeta;
      if (operator) {
        manageStrategyData.operator = operator;
        return;
      }

      try {
        isChangeOperatorLoading.value = true;
        const res = await http.request('userInfo/getUsername');
        store.commit('updateUserMeta', res.data);
        manageStrategyData.operator = res.data.operator;
      } catch (e) {
        console.warn(e);
      } finally {
        isChangeOperatorLoading.value = false;
      }
    };

    // 处理取消
    const handleCancel = () => {
      emit('handleCancelSlider');
    };

    // 处理确认
    const handleConfirm = () => {
      emit('handleUpdatedTable', manageStrategyData);
    };

    // 渲染授权目录列表
    const renderVisibleDirList = () => {
      return manageStrategyData.visible_dir.map((item: string, index: number) => (
        <div
          class='flex-box add-minus-component visible-dir'
          key={index}
        >
          <ValidateInput
            style='width: 256px; margin-right: 4px'
            value={item}
            onChange={(val: string) => {
              manageStrategyData.visible_dir[index] = val;
            }}
            validator={validateVisibleDir}
          />
          <span
            class='bk-icon icon-plus-circle'
            onClick={handleAddVisibleDir}
          />
          <span
            class='bk-icon icon-minus-circle'
            style={{ display: manageStrategyData.visible_dir.length > 1 ? 'inline' : 'none' }}
            onClick={() => manageStrategyData.visible_dir.splice(index, 1)}
          />
        </div>
      ));
    };

    // 渲染文件类型列表
    const renderFileTypeList = () => {
      return manageStrategyData.file_type.map((item: string, index: number) => (
        <div
          class='flex-box add-minus-component file-type'
          key={index}
        >
          <ValidateInput
            style='width: 256px; margin-right: 4px'
            value={item}
            onChange={(val: string) => {
              manageStrategyData.file_type[index] = val;
            }}
            validator={validateFileExtension}
          />
          <span
            class='bk-icon icon-plus-circle'
            onClick={handleAddFileType}
          />
          <span
            class='bk-icon icon-minus-circle'
            style={{ display: manageStrategyData.file_type.length > 1 ? 'inline' : 'none' }}
            onClick={() => manageStrategyData.file_type.splice(index, 1)}
          />
        </div>
      ));
    };

    // 主渲染函数
    return () => (
      <div
        class='directory-manage-container'
        data-test-id='addNewExtractAuthManage_div_addNewExtractBox'
      >
        <div class='directory-manage'>
          {/* 名称 */}
          <div class='row-container'>
            <div class='title'>
              {t('名称')}
              <span class='required'> * </span>
              <span
                class='bklog-icon bklog-info-fill'
                v-bk-tooltips={{ width: 200, content: t('不同类别的授权用户，通过用户组名区分，单业务下唯一') }}
              />
            </div>
            <div class='content'>
              <ValidateInput
                style='width: 400px'
                value={manageStrategyData.strategy_name}
                onChange={(val: string) => {
                  manageStrategyData.strategy_name = val;
                }}
              />
            </div>
          </div>

          {/* 用户列表 */}
          <div class='row-container'>
            <div class='title'>
              {t('用户列表')}
              <span class='required'> * </span>
              <span
                class='bklog-icon bklog-info-fill'
                v-bk-tooltips={{
                  width: 200,
                  content: props.allowCreate
                    ? t('多个QQ号粘贴请使用英文分号 " ; " 分隔 ，手动输入QQ号请键入 Enter 保存')
                    : t('多个用户名粘贴请使用英文分号 " ; " 分隔 ，手动输入用户名请键入 Enter 保存'),
                }}
              />
            </div>
            <div class='content'>
              <ValidateUserSelector
                value={manageStrategyData.user_list}
                onChange={(val: any[]) => {
                  manageStrategyData.user_list = val;
                }}
                allowCreate={props.allowCreate}
                api={props.userApi}
                placeholder={props.allowCreate ? t('请输入QQ并按Enter结束（可多次添加）') : ''}
              />
            </div>
          </div>

          {/* 授权目录 */}
          <div class='row-container'>
            <div class='title'>
              {t('授权目录')}
              <span class='required'> * </span>
              <span
                class='bklog-icon bklog-info-fill'
                v-bk-tooltips={{ width: 200, content: t('目录以 / 结尾，windows 服务器以 /cygdrive/ 开头') }}
              />
            </div>
            <div class='content'>{renderVisibleDirList()}</div>
          </div>

          {/* 文件后缀 */}
          <div class='row-container'>
            <div class='title'>
              {t('文件后缀')}
              <span class='required'> * </span>
              <span
                class='bklog-icon bklog-info-fill'
                v-bk-tooltips={t('请输入不带点号(.)的后缀名，匹配任意文件可填写星号(*)')}
              />
            </div>
            <div class='content'>{renderFileTypeList()}</div>
          </div>

          {/* 授权目标 */}
          <div class='row-container'>
            <div class='title'>
              {t('授权目标')}
              <span class='required'> * </span>
            </div>
            <div class='content'>
              <div class='flex-box'>
                <bk-button
                  size='small'
                  onClick={() => {
                    showSelectDialog.value = true;
                  }}
                >
                  + {t('选择目标')}
                </bk-button>
                <div class='select-text'>
                  <i18n path='已选择{0}个节点'>
                    <span class={manageStrategyData.modules.length ? 'primary' : 'error'}>
                      {` ${manageStrategyData.modules.length} `}
                    </span>
                  </i18n>
                </div>
              </div>
              <ModuleSelect
                selectedModules={manageStrategyData.modules}
                selectedType={manageStrategyData.select_type}
                showSelectDialog={showSelectDialog.value}
                {...{
                  on: {
                    'update:showSelectDialog': (val: boolean) => {
                      showSelectDialog.value = val;
                    },
                    confirm: handleConfirmSelect,
                  },
                }}
              />
            </div>
          </div>

          {/* 执行人 */}
          <div class='row-container'>
            <div class='title'>
              {t('执行人')}
              <span class='required'> * </span>
              <span
                class='bklog-icon bklog-info-fill'
                v-bk-tooltips={{
                  width: 200,
                  content: t('全局设置，下载过程中需使用job传输，将以执行人身份进行，请确保执行人拥有业务权限'),
                }}
              />
            </div>
            <div class='content'>
              <div class='flex-box'>
                <bk-input
                  style='width: 256px; margin-right: 10px'
                  class={!manageStrategyData.operator && 'is-input-error'}
                  value={manageStrategyData.operator}
                  readonly
                />
                <bk-button
                  loading={isChangeOperatorLoading.value}
                  size='small'
                  onClick={changeOperator}
                >
                  {t('改为我')}
                </bk-button>
              </div>
            </div>
          </div>
        </div>

        {/* 按钮容器 */}
        <div class='button-container'>
          <bk-button
            style='margin-right: 24px'
            disabled={!isValidated.value}
            theme='primary'
            onClick={handleConfirm}
          >
            {t('确认')}
          </bk-button>
          <bk-button onClick={handleCancel}>{t('取消')}</bk-button>
        </div>
      </div>
    );
  },
});
