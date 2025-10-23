<script setup>
import { watch, ref, computed } from 'vue';
import useStore from '@/hooks/use-store';
import $http from "@/api";
import { BK_LOG_STORAGE } from '@/store/store.type.ts';
import { bkMessage } from 'bk-magic-vue';
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
})
const formRef = ref(null);


// 修改数据结构定义
const directoryRawData = ref([]); // 存储原始目录数据
const directoryList = computed(() => {
  return directoryRawData.value.map(folder => ({
    id: `folder_${folder.id}`,
    name: folder.title,
    type: 'folder'
  }));
});

// 计算属性：根据选中的目录显示对应的仪表盘
const filteredDashboards = computed(() => {
  if (!formData.value.directory) {
    return [];
  }

  const folderId = formData.value.directory.replace('folder_', '');
  const folder = directoryRawData.value.find(item => item.id == folderId);

  if (!folder || !folder.dashboards) {
    return [];
  }

  return folder.dashboards.map(dashboard => ({
    id: dashboard.id.toString(),
    name: dashboard.title,
    type: 'dashboard',
    uid: dashboard.uid,
    url: dashboard.url,
    uri: dashboard.uri
  }));
});

const currentSearchType = computed(() => {
  return store.state.storage?.[BK_LOG_STORAGE.SEARCH_TYPE];
})

// 获取树状目录数据&& 仪表盘数据
const fetchDirectoryList = () => {
  basicLoading.value = true;
  $http.request('dashboard/get_dashboard_directory_tree', {
    query: {
      bk_biz_id: store.state.bkBizId || 0,
    },
  }).then((res) => {
    const { data } = res;
    console.log('原始数据:', data);
    directoryRawData.value = data || [];
  }).catch((error) => {
    console.error('获取目录列表失败:', error);
  }).finally(() => {
    basicLoading.value = false; // 无论成功或失败都关闭加载状态
  });
}
watch(
  () => props.isShow,
  (newVal) => {
    visible.value = newVal;
    formData.value = {
      chartName: '',
      directory: '',
      dashboard: ''
    };
    formRef.value.clearError();
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
  }
);
// UI模式
const generateQueryStringData = async () => {
  console.log(store.getters.retrieveParams, '查询条件');
  queryStringData.value = await $http.request("retrieve/generateQueryString", {
    data: {
      addition: store.getters.retrieveParams?.addition || []
    },
  })
}

// 开始创建目录
const startCreateDirectory = () => {
  isCreatingDirectory.value = true;
  newDirectoryName.value = '';
};

// 新增仪表盘相关状态
const isCreatingDashboard = ref(false);
const newDashboardName = ref('');

const handleDirectoryEnter = (event) => {
  // 阻止默认行为
  if (event && event.preventDefault) {
    event.preventDefault();
  }
  saveItem('directory');
};

const handleDashboardEnter = (event) => {
  if (event && event.preventDefault) {
    event.preventDefault();
  }
  saveItem('dashboard');
};

const isSaving = ref(false);

const saveItem = async (type) => {
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
        bk_biz_id: store.state.bkBizId || 0
      };
      const res = await $http.request('dashboard/create_dashboard_directory', {
        data
      });

      if (res.result) {
        // 更新目录数据
        directoryRawData.value.push({
          ...res.data,
          dashboards: []
        });
        formData.value.directory = `folder_${res.data.id}`;
        bkMessage({
          theme: 'success',
          message: '目录创建成功',
        });
      }
    } else {
      // 创建仪表盘
      const folderId = formData.value.directory.replace('folder_', '');
      const res = await $http.request('dashboard/create_dashboard_directory', {
        data: {
          title: inputValue.trim(),
          type: 'dashboard',
          folderId: folderId,
          bk_biz_id: store.state.bkBizId || 0
        }
      });

      if (res.result) {
        const newDashboard = res.data;
        console.log('新仪表盘数据:', newDashboard);
        // 在对应目录中添加新的仪表盘
        const folderIndex = directoryRawData.value.findIndex(item => item.id == folderId);
        if (folderIndex !== -1) {
          // 确保dashboards数组存在
          if (!directoryRawData.value[folderIndex].dashboards) {
            directoryRawData.value[folderIndex].dashboards = [];
          }

          // 将新仪表盘添加到列表中
          directoryRawData.value[folderIndex].dashboards.push({
            ...newDashboard,
            id: newDashboard.id || newDashboard.uid || Date.now(),
            title: newDashboard.title || inputValue.trim()
          });

          // 选中新创建的仪表盘
          const dashboardId = newDashboard.id || newDashboard.uid || '';
          if (dashboardId) {
            formData.value.dashboard = dashboardId.toString();
          }
        }

        bkMessage({
          theme: 'success',
          message: '仪表盘创建成功',
        });
      }
    }
  } catch (error) {
    console.error(`${isDirectory ? '创建目录' : '创建仪表盘'}失败:`, error);
    bkMessage({
      theme: 'error',
      message: `${isDirectory ? '创建目录' : '创建仪表盘'}失败: ${error.message || ''}`,
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
  formRef.value.clearError();
  emit('update:isShow', false);
};

const handleSubmit = async () => {
  try {
    console.log('提交时的表单数据:', JSON.stringify(formData.value));
    console.log('chartName类型和值:', typeof formData.value.chartName, `"${formData.value.chartName}"`);
    console.log('directory类型和值:', typeof formData.value.directory, `"${formData.value.directory}"`);
    console.log('dashboard类型和值:', typeof formData.value.dashboard, `"${formData.value.dashboard}"`);
    const validations = [
      { 
        field: formData.value.chartName?.trim(), 
        message: '请输入图表名称' 
      },
      { 
        field: formData.value.directory, 
        message: '请选择目标目录' 
      },
      { 
        field: formData.value.dashboard, 
        message: '请选择目标仪表盘' 
      }
    ];
    
    // 检查每个字段
    for (const validation of validations) {
      if (!validation.field || validation.field === '') {
        bkMessage({
          theme: 'warning',
          message: validation.message,
        });
        return;
      }
    }
    
    basicLoading.value = true;
    const selectedDashboard = filteredDashboards.value.find(
      dashboard => dashboard.id === formData.value.dashboard
    );
    const dashboardUids = selectedDashboard?.uid ? [selectedDashboard.uid] : [];
    // 判断当前的模式是UI模式还是SQL模式
    currentSearchType.value === 0 ? await generateQueryStringData() : queryStringData.value = store.getters.retrieveParams?.keyword || '';
    await saveChartToDashboard(dashboardUids);
  } catch (error) {
    console.log('表单验证失败:', error);
  } finally {
    basicLoading.value = false;
  }
};
const saveChartToDashboard = async (dashboardUids) => {
  try {
    const result = await $http.request('dashboard/save_to_dashboard', {
      data: {
        "panels": [
          {
            "name": formData.value.chartName || '', // 图表名称
            "queries": [
              {
                "expression": "A",
                "query_configs": [
                  {
                    "query_string": queryStringData.value || "*", // 使用生成的查询字符串
                    "metrics": [
                      {
                        "field": "gseindex",
                        "method": "COUNT",
                        "alias": "A"
                      }
                    ],
                    "table": "",
                    "index_set_id": store.state.indexItem.ids?.join(','), // 动态获取索引集ID
                    "data_source_label": "bk_log_search"
                  }
                ],
                "alias": ""
              }
            ]
          }
        ],
        "dashboard_uids": dashboardUids, // 使用仪表盘UID列表
        "bk_biz_id": store.state.bkBizId || 0,
      }
    });
    if (result.result) {
      bkMessage({
        theme: 'success',
        message: '添加到仪表盘保存成功',
      });
      handleClose();
    } else {
      bkMessage({
        theme: 'error',
        message: `${result.message || '添加到仪表盘保存失败'}`,
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
  <bk-dialog v-model="visible" theme="primary" :mask-close="false" title="添加到仪表盘" header-position="left"
    @close="handleClose" width="520px" @after-leave="handleClose">
    <bk-form :model="formData" ref="formRef" :label-width="100" form-type="vertical"
      v-bkloading="{ isLoading: basicLoading, zIndex: 10 }">
      <bk-form-item label="图表名称" required property="chartName">
        <bk-input class="dashboard-input-full" v-model="formData.chartName" placeholder="请输入图表名称"
          maxlength="255" :clearable="true"></bk-input>
      </bk-form-item>
      <bk-form-item label="添加目标" required property="targetType" v-if="false">
        已有仪表盘
      </bk-form-item>
      <bk-form-item label="所属目录" required property="directory">
        <bk-select v-model="formData.directory" class="dashboard-input-full" :search-with-pinyin="true" searchable>
          <bk-option v-for="option in directoryList" :key="option.id" :id="option.id" :name="option.name">
          </bk-option>

          <div slot="extension" v-if="!isCreatingDirectory" @click="startCreateDirectory"
            class="dashboard-extension-with-gap">
            <i class="bk-icon icon-plus-circle"></i>
            <span>新增目录</span>
          </div>
          <div slot="extension" v-else class="dashboard-extension-flex">
            <bk-input v-model="newDirectoryName" placeholder="请输入目录名称" style="flex: 1;"
              @keyup.enter="handleDirectoryEnter"></bk-input>
            <bk-button icon="check-1" size="small" @click="() => saveItem('directory')" class="dashboard-button-green">
            </bk-button>
            <bk-button icon="close" size="small" @click="cancelCreateDirectory" class="dashboard-button-red">
            </bk-button>
          </div>
        </bk-select>
      </bk-form-item>
      <bk-form-item label="目标仪表盘" required property="dashboard">
        <bk-select v-model="formData.dashboard" class="dashboard-input-full" :search-with-pinyin="true" searchable>
          <bk-option v-for="option in filteredDashboards" :key="option.id" :id="option.id" :name="option.name">
          </bk-option>
          <div slot="extension" v-if="!isCreatingDashboard && formData.directory" @click="startCreateDashboard"
            class="dashboard-extension-with-gap">
            <i class="bk-icon icon-plus-circle"></i>
            <span>新增仪表盘</span>
          </div>
          <div slot="extension" v-else-if="isCreatingDashboard" class="dashboard-extension-flex">
            <bk-input v-model="newDashboardName" placeholder="请输入仪表盘名称" style="flex: 1;"
              @keyup.enter="handleDashboardEnter"></bk-input>
            <bk-button icon="check-1" size="small" @click="saveItem('dashboard')" class="dashboard-button-green">
            </bk-button>
            <bk-button icon="close" size="small" @click="cancelCreateDashboard" class="dashboard-button-red">
            </bk-button>
          </div>
        </bk-select>
      </bk-form-item>
    </bk-form>
    <template #footer>
      <bk-button theme="primary" @click="handleSubmit">确定</bk-button>
      <bk-button @click="handleClose">取消</bk-button>
    </template>
  </bk-dialog>
</template>

<style lang="scss" scoped>
@import './dashboard-dialog.scss';
</style>