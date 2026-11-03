// 获取仪表盘目录树
const getDashboardDirectoryTree = {
  url: '/grafana/get_dashboard_directory_tree/',
  method: 'get',
};
// 新建仪表盘目录
const createDashboardDirectory = {
  url: '/grafana/create_dashboard_or_folder/',
  method: 'post',
};
// 保存到仪表盘
const saveToDashboard = {
  url: '/grafana/save_to_dashboard/',
  method: 'post',
};
export { getDashboardDirectoryTree, createDashboardDirectory, saveToDashboard };
