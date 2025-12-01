//获取仪表盘目录树
const get_dashboard_directory_tree = {
    url: '/grafana/get_dashboard_directory_tree/',
    method: 'get',
}
//新建仪表盘目录
const create_dashboard_directory = {
    url: '/grafana/create_dashboard_or_folder/',
    method: 'post',
}
//保存到仪表盘
const save_to_dashboard = {
    url: '/grafana/save_to_dashboard/',
    method: 'post',
}
export {get_dashboard_directory_tree,create_dashboard_directory,save_to_dashboard}