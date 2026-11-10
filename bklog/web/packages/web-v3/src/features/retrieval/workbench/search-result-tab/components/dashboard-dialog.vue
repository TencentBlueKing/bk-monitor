<script setup>import { ServicesInstance } from '@/platform/services';

  import { watch, ref, computed } from 'vue';
  import useStore from '@/shared/composables/use-store';
  
  import { BK_LOG_STORAGE } from '@/app/state/store.type.ts';
  import { Dialog, Form, FormItem, Input, Select, Option, Button, MessagePlugin } from 'tdesign-vue-next';
  import { filterWithPinyin } from '@/platform/compat/tdesign/select-filter';
  import 'tdesign-vue-next/es/style/index.css';
  import useLocale from '@/shared/composables/use-locale';
  const { t } = useLocale();
  const store = useStore();
  const props = defineProps({
    isShow: {
      type: Boolean,
      required: true,
    },
  });

  const emit = defineEmits(['update:isShow']);

  const queryStringData = ref(''); // 存储生成的查询字符串
  const basicLoading = ref(false);
  const isCreatingDirectory = ref(false);
  const newDirectoryName = ref('');
  const visible = ref(false); // 控制弹窗显示状态
  const formData = ref({
    chartName: '',
    directory: '',
    dashboard: '',
  });
  const formRef = ref(null);
  const rules = {
    chartName: [{ required: true, message: t('请输入图表名称'), trigger: 'blur' }],
    directory: [{ required: true, message: t('请选择所属目录'), trigger: 'change' }],
    dashboard: [{ required: true, message: t('请选择目标仪表盘'), trigger: 'change' }],
  };

  // 修改数据结构定义
  const directoryRawData = ref([]); // 存储原始目录数据
  const directoryList = computed(() => {
    return directoryRawData.value.map(folder => ({
      id: `folder_${folder.id}`,
      name: folder.title,
      type: 'folder',
    }));
  });

  // 计算属性：根据选中的目录显示对应的仪表盘
  const filteredDashboards = computed(() => {
    if (!formData.value.directory) {
      return [];
    }
    const folderId = formData.value.directory.replace('folder_', '');
    const folder = directoryRawData.value.find(item => String(item.id) === folderId);

    if (!folder || !folder.dashboards) {
      return [];
    }

    return folder.dashboards.map(dashboard => ({
      id: dashboard.id.toString(),
      name: dashboard.title,
      type: 'dashboard',
      uid: dashboard.uid,
      url: dashboard.url,
      uri: dashboard.uri,
    }));
  });

  const currentSearchType = computed(() => {
    return store.state.storage?.[BK_LOG_STORAGE.SEARCH_TYPE];
  });

  // 获取树状目录数据&& 仪表盘数据
  const fetchDirectoryList = () => {
    basicLoading.value = true;
    ServicesInstance.dashboard.getDashboardDirectoryTree({
        query: {
          bk_biz_id: store.state.bkBizId || 0,
        },
      })
      .then(res => {
        const { data } = res;
        directoryRawData.value = data || [];
      })
      .catch(error => {
        console.error('获取目录列表失败:', error);
      })
      .finally(() => {
        basicLoading.value = false; // 无论成功或失败都关闭加载状态
      });
  };
  watch(
    () => props.isShow,
    newVal => {
      visible.value = newVal;
      formData.value = {
        chartName: '',
        directory: '',
        dashboard: '',
      };
      formRef.value?.clearValidate();
      if (newVal) {
        directoryRawData.value = [];
        basicLoading.value = false;
        fetchDirectoryList();
      }
    },
    { immediate: true },
  );
  watch(
    () => formData.value.directory,
    (newVal, oldVal) => {
      if (newVal !== oldVal) {
        formData.value.dashboard = '';
      }
    },
  );
  // UI模式
  const generateQueryStringData = async () => {
    const result = await ServicesInstance.retrieve.generateQueryString({
      data: {
        addition: store.getters.retrieveParams?.addition || [],
      },
    });
    queryStringData.value = result.data?.querystring || '';
  };

  // 开始创建目录
  const startCreateDirectory = () => {
    isCreatingDirectory.value = true;
    newDirectoryName.value = '';
  };

  // 新增仪表盘相关状态
  const isCreatingDashboard = ref(false);
  const newDashboardName = ref('');

  const handleDirectoryEnter = event => {
    // 阻止默认行为
    if (event && event.preventDefault) {
      event.preventDefault();
    }
    saveItem('directory');
  };

  const handleDashboardEnter = event => {
    if (event && event.preventDefault) {
      event.preventDefault();
    }
    saveItem('dashboard');
  };

  const isSaving = ref(false);

  const saveItem = async type => {
    if (isSaving.value) {
      return;
    }
    const isDirectory = type === 'directory';
    const inputValue = isDirectory ? newDirectoryName.value : newDashboardName.value;
    const creatingState = isDirectory ? isCreatingDirectory : isCreatingDashboard;
    const inputRef = isDirectory ? newDirectoryName : newDashboardName;

    if (!inputValue.trim()) {
      return;
    }
    isSaving.value = true;
    basicLoading.value = true;
    try {
      if (isDirectory) {
        // 创建目录
        const data = {
          title: inputValue.trim(),
          type: 'folder',
          bk_biz_id: store.state.bkBizId || 0,
        };
        const res = await ServicesInstance.dashboard.createDashboardDirectory({
          data,
        });

        if (res.result) {
          // 更新目录数据
          directoryRawData.value.push({
            ...res.data,
            dashboards: [],
          });
          formData.value.directory = `folder_${res.data.id}`;
          MessagePlugin({
            theme: 'success',
            content: t('目录创建成功'),
          });
        }
      } else {
        // 创建仪表盘
        const folderId = formData.value.directory.replace('folder_', '');
        const res = await ServicesInstance.dashboard.createDashboardDirectory({
          data: {
            title: inputValue.trim(),
            type: 'dashboard',
            folderId: folderId || '',
            bk_biz_id: store.state.bkBizId || 0,
          },
        });

        if (res.result) {
          const newDashboard = res.data;
          // 在对应目录中添加新的仪表盘
          const folderIndex = directoryRawData.value.findIndex(item => String(item.id) === folderId);
          if (folderIndex !== -1) {
            // 确保dashboards数组存在
            if (!directoryRawData.value[folderIndex].dashboards) {
              directoryRawData.value[folderIndex].dashboards = [];
            }

            // 将新仪表盘添加到列表中
            directoryRawData.value[folderIndex].dashboards.push({
              ...newDashboard,
              id: newDashboard.id || newDashboard.uid || Date.now(),
              title: newDashboard.title || inputValue.trim(),
            });

            // 选中新创建的仪表盘
            const dashboardId = newDashboard.id || newDashboard.uid || '';
            if (dashboardId) {
              formData.value.dashboard = dashboardId.toString();
            }
          }

          MessagePlugin({
            theme: 'success',
            content: t('仪表盘创建成功'),
          });
        }
      }
    } catch (error) {
      console.error(`${isDirectory ? '创建目录' : '创建仪表盘'}失败:`, error);
      MessagePlugin({
        theme: 'error',
        content: `${isDirectory ? t('创建目录') : t('创建仪表盘')}失败: ${error.message || ''}`,
      });
    } finally {
      // 重置所有状态
      isSaving.value = false;
      basicLoading.value = false;
      creatingState.value = false;
      inputRef.value = '';
    }
  };

  // 取消创建
  const cancelCreateDirectory = () => {
    isCreatingDirectory.value = false;
    newDirectoryName.value = '';
  };

  // 开始创建仪表盘
  const startCreateDashboard = () => {
    isCreatingDashboard.value = true;
    newDashboardName.value = '';
  };

  // 取消创建仪表盘
  const cancelCreateDashboard = () => {
    isCreatingDashboard.value = false;
    newDashboardName.value = '';
  };

  const handleClose = () => {
    visible.value = false;
    formRef.value.clearValidate();
    emit('update:isShow', false);
  };

  const handleSubmit = async () => {
    try {
      const validationResult = await formRef.value.validate();
      if (validationResult !== true) return;
      basicLoading.value = true;
      const selectedDashboard = filteredDashboards.value.find(dashboard => dashboard.id === formData.value.dashboard);
      const dashboardUids = selectedDashboard?.uid ? [selectedDashboard.uid] : [];
      // 判断当前的模式是UI模式还是SQL模式
      currentSearchType.value === 0
        ? await generateQueryStringData()
        : (queryStringData.value = store.getters.retrieveParams?.keyword || '');
      await saveChartToDashboard(dashboardUids);
    } catch (error) {
      console.log('表单验证失败:', error);
    } finally {
      basicLoading.value = false;
    }
  };
  const saveChartToDashboard = async dashboardUids => {
    try {
      const result = await ServicesInstance.dashboard.saveToDashboard({
        data: {
          panel_name: formData.value.chartName || '',
          query_string: queryStringData.value || '',
          index_set_id: Number(store.state.indexItem.ids?.join(',')) || 0,
          // "panels": [
          //   {
          //     "name": formData.value.chartName || '', // 图表名称
          //     "queries": [
          //       {
          //         "expression": "A",
          //         "query_configs": [
          //           {
          //             "query_string": queryStringData.value || "*", // 使用生成的查询字符串
          //             "metrics": [
          //               {
          //                 "field": "gseindex",
          //                 "method": "COUNT",
          //                 "alias": "A"
          //               }
          //             ],
          //             "table": "",
          //             "index_set_id": store.state.indexItem.ids?.join(','), // 动态获取索引集ID
          //             "data_source_label": "bk_log_search"
          //           }
          //         ],
          //         "alias": ""
          //       }
          //     ]
          //   }
          // ],
          dashboard_uids: dashboardUids || [], // 使用仪表盘UID列表
          bk_biz_id: store.state.bkBizId || 0,
        },
      });
      if (result.result) {
        MessagePlugin({
          theme: 'success',
          content: '添加到仪表盘保存成功',
        });
        handleClose();
        const url = `${window.MONITOR_URL}/?bizId=${store.state.bkBizId}#${result.data[0]?.url}`;
        window.open(url, '_blank', 'noopener,noreferrer');
      } else {
        MessagePlugin({
          theme: 'error',
          content: `${result.message || '添加到仪表盘保存失败'}`,
        });
      }
    } catch (error) {
      console.log('保存到仪表盘失败:', error);
    } finally {
      basicLoading.value = false;
    }
  };
</script>

<template>
  <Dialog
    v-model:visible="visible"
    :close-on-overlay-click="false"
    :destroy-on-close="false"
    :header="t('添加到仪表盘')"
    width="480px"
    @close="handleClose"
    @closed="handleClose"
  >
    <Form
      ref="formRef"
      v-loading="{ loading: basicLoading, zIndex: 10 }"
      :data="formData"
      :label-width="100"
      label-align="top"
      :rules="rules"
    >
      <FormItem
        :label="t('图表名称')"
        required
        name="chartName"
      >
        <Input
          v-model="formData.chartName"
          class="dashboard-input-full"
          :placeholder="t('请输入图表名称')"
          :maxlength="255"
          :clearable="true"
        />
      </FormItem>
      <FormItem
        :label="t('所属目录')"
        required
        name="directory"
      >
        <Select
          v-model="formData.directory"
          class="dashboard-input-full"
          :filter="filterWithPinyin"
          filterable
        >
          <Option
            v-for="option in directoryList"
            :value="option.id"
            :key="option.id"
            :label="option.name"
          />

          <template #panelBottomContent>
            <div
              v-if="!isCreatingDirectory"
              class="dashboard-extension-with-gap"
              @click="startCreateDirectory"
            >
              <i class="bk-icon icon-plus-circle" />
              <span>{{ t('新增目录') }}</span>
            </div>
            <div
              v-else
              class="dashboard-extension-flex"
            >
              <Input
                v-model="newDirectoryName"
                :placeholder="t('请输入目录名称')"
                style="flex: 1"
                @keyup.enter="handleDirectoryEnter"
              />
              <Button
                size="small"
                class="dashboard-button-green"
                @click="() => saveItem('directory')"
                ><template #icon><i class="bk-icon icon-check-1" /></template
              ></Button>
              <Button
                size="small"
                class="dashboard-button-red"
                @click="cancelCreateDirectory"
                ><template #icon><i class="bk-icon icon-close" /></template
              ></Button>
            </div>
          </template>
        </Select>
      </FormItem>
      <FormItem
        :label="t('目标仪表盘')"
        required
        name="dashboard"
      >
        <Select
          v-model="formData.dashboard"
          class="dashboard-input-full"
          :filter="filterWithPinyin"
          filterable
        >
          <Option
            v-for="option in filteredDashboards"
            :value="option.id"
            :key="option.id"
            :label="option.name"
          />
          <template #panelBottomContent>
            <div
              v-if="!isCreatingDashboard && formData.directory"
              class="dashboard-extension-with-gap"
              @click="startCreateDashboard"
            >
              <i class="bk-icon icon-plus-circle" />
              <span>{{ t('新增仪表盘') }}</span>
            </div>
            <div
              v-else-if="isCreatingDashboard"
              class="dashboard-extension-flex"
            >
              <Input
                v-model="newDashboardName"
                :placeholder="t('请输入仪表盘名称')"
                style="flex: 1"
                @keyup.enter="handleDashboardEnter"
              />
              <Button
                size="small"
                class="dashboard-button-green"
                @click="saveItem('dashboard')"
                ><template #icon><i class="bk-icon icon-check-1" /></template
              ></Button>
              <Button
                size="small"
                class="dashboard-button-red"
                @click="cancelCreateDashboard"
                ><template #icon><i class="bk-icon icon-close" /></template
              ></Button>
            </div>
          </template>
        </Select>
      </FormItem>
    </Form>
    <template #footer>
      <Button
        theme="primary"
        @click="handleSubmit"
      >
        {{ t('确定') }}
      </Button>
      <Button theme="default" @click="handleClose">
        {{ t('取消') }}
      </Button>
    </template>
  </Dialog>
</template>

<style lang="scss" scoped>
@use './dashboard-dialog.scss' as *;
</style>
