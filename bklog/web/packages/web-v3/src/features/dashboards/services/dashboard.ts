import { defineEndpoint } from '@/platform/services/runtime/service-client';
// 获取仪表盘目录树
const getDashboardDirectoryTree = defineEndpoint({
  url: '/grafana/get_dashboard_directory_tree/',
  method: 'get',
});
// 新建仪表盘目录
const createDashboardDirectory = defineEndpoint({
  url: '/grafana/create_dashboard_or_folder/',
  method: 'post',
});
// 保存到仪表盘
const saveToDashboard = defineEndpoint({
  url: '/grafana/save_to_dashboard/',
  method: 'post',
});
export { getDashboardDirectoryTree, createDashboardDirectory, saveToDashboard };
