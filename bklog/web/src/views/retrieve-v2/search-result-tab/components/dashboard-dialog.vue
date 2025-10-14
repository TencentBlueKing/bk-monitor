<script setup>
import { watch, ref } from 'vue';

const props = defineProps({
  isShow: {
    type: Boolean,
    required: true,
  },
  collectionList: {
    type: Array,
    required: false,
  },
});
const emit = defineEmits(['update:isShow']);
const isCreatingDirectory = ref(false);
const newDirectoryName = ref('');
const visible = ref(false); // 控制弹窗显示状态
const formData = ref({
  chartName: '',
  targetType: '',
  directory: '',
  dashboard: '',
})
const formRef = ref(null);
const rules = {
  chartName: [
    {
      required: true,
      message: '图表名称不能为空',
      trigger: 'blur'
    }
  ],
  targetType: [
    {
      required: true,
      message: '请选择添加目标',
      trigger: 'change'
    }
  ],
  directory: [
    {
      required: true,
      message: '请选择所属目录',
      trigger: 'change'
    }
  ],
  dashboard: [
    {
      required: true,
      message: '请选择目标仪表盘',
      trigger: 'change'
    }
  ]
};
const list = ref([
  { id: '1', name: '默认目录' },
  { id: '2', name: '测试目录' },
]);
watch(
  () => props.isShow,
  (newVal) => {
    visible.value = newVal;
  },
  { immediate: true },
);
// 开始创建目录
const startCreateDirectory = () => {
  isCreatingDirectory.value = true;
  newDirectoryName.value = '';
};
// 新增仪表盘相关状态
const isCreatingDashboard = ref(false);
const newDashboardName = ref('');
// 保存目录
const saveDirectory = () => {
  if (!newDirectoryName.value.trim()) {
    return;
  }

  const newId = (list.value.length + 1).toString();
  list.value.push({
    id: newId,
    name: newDirectoryName.value.trim()
  });

  // 设置选中项
  formData.value.directory = newId;

  // 关闭输入框
  isCreatingDirectory.value = false;
  newDirectoryName.value = '';
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

// 保存仪表盘
const saveDashboard = () => {
  if (!newDashboardName.value.trim()) {
    return;
  }

  const newId = (list.value.length + 1).toString();
  list.value.push({
    id: newId,
    name: newDashboardName.value.trim()
  });

  // 设置选中项
  formData.value.dashboard = newId;

  // 关闭输入框
  isCreatingDashboard.value = false;
  newDashboardName.value = '';
};

// 取消创建仪表盘
const cancelCreateDashboard = () => {
  isCreatingDashboard.value = false;
  newDashboardName.value = '';
};
const handleClose = () => {
  visible.value = false;
  emit('update:isShow', false);
};
const handleSubmit = async () => {
  try {
    const valid = await formRef.value.validate();
    if (valid) {
      console.log('表单数据:', formData.value, formRef.value);
    }
  } catch (error) {
    // 验证失败，bk-form会自动显示错误信息
    console.log('表单验证失败:', error);
  }
}; 
</script>
<template>
  <bk-dialog v-model="visible" theme="primary" :mask-close="false" title="添加到仪表盘" header-position="left"
    @close="handleClose" width="520px" @after-leave="handleClose">
    <bk-form :model="formData" ref="formRef" label-width="100px" form-type="vertical" :rules="rules">
      <!-- 图表名称 -->
      <bk-form-item label="图表名称" required property="chartName">
        <bk-input style="width: 432px;" v-model="formData.chartName" placeholder="请输入" maxlength="255" />
      </bk-form-item>

      <!-- 添加目标 -->
      <bk-form-item label="添加目标" required property="targetType">
        <bk-radio-group v-model="formData.targetType">
          <bk-radio value="existing">已有仪表盘</bk-radio>
          <bk-radio value="new" style="margin-left: 15px;">新建仪表盘</bk-radio>
        </bk-radio-group>
      </bk-form-item>

      <!-- 所属目录 -->
      <bk-form-item label="所属目录" required property="directory">
        <bk-select v-model="formData.directory" style="width: 432px;">
          <bk-option v-for="option in list" :key="option.id" :id="option.id" :name="option.name">
          </bk-option>

          <!-- 新增目录按钮 -->
          <div slot="extension" v-if="!isCreatingDirectory" @click="startCreateDirectory"
            style=" margin-top: 8px;cursor: pointer;">
            <i class="bk-icon icon-plus-circle"></i>新增目录
          </div>

          <!-- 输入框模式 -->
          <div slot="extension" v-else style="display: flex; gap: 8px; align-items: center; margin-top: 8px;">
            <bk-input v-model="newDirectoryName" placeholder="请输入目录名称" style="flex: 1;" @keyup.enter="saveDirectory" />
            <bk-button icon="check-1" size="small" @click="saveDirectory" style="color:green">
            </bk-button>
            <bk-button icon="close" size="small" @click="cancelCreateDirectory" style="color:red">
              <bk-icon type="close" />
            </bk-button>
          </div>
        </bk-select>
      </bk-form-item>
      <bk-form-item label="仪表盘名称" required property="chartName" v-if="formData.targetType === 'existing'">
        <bk-input v-model="formData.chartName" placeholder="请输入" style="width: 472px;" />
      </bk-form-item>
      <!-- 目标仪表盘 -->
      <bk-form-item label="目标仪表盘" required property="dashboard" v-else>
        <bk-select v-model="formData.dashboard" style="width: 432px;">
          <bk-option v-for="option in list" :key="option.id" :id="option.id" :name="option.name">
          </bk-option>

          <!-- 新增仪表盘按钮 -->
          <div slot="extension" v-if="!isCreatingDashboard" @click="startCreateDashboard"
            style=" margin-top: 8px;cursor: pointer;">
            <i class="bk-icon icon-plus-circle"></i>新增仪表盘
          </div>

          <!-- 输入框模式 -->
          <div slot="extension" v-else style="display: flex; gap: 8px; align-items: center; margin-top: 8px;">
            <bk-input v-model="newDashboardName" placeholder="请输入仪表盘名称" style="flex: 1;" @keyup.enter="saveDashboard" />
            <bk-button icon="check-1" size="small" @click="saveDashboard" style="color:green">
            </bk-button>
            <bk-button icon="close" size="small" @click="cancelCreateDashboard" style="color:red">
              <bk-icon type="close" />
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