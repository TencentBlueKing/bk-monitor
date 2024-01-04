1. Webhook Push URL 路径配置 

    | 云 | 是否必填 | source配置 |
    |---|----------|------|
    | 腾讯云 | 必填 | tencent  | 
    | 谷歌云 | 选填 | google   |
    
    注：路径上的token即以上配置的Token（点击查看）
    
    ```
    例子URL：http://www.bk.com/fta/v1/event/?token={{token}}&source={{source}}
    腾讯云：http://www.bk.com/fta/v1/event/?token=Token&source=tencent
    谷歌云：http://www.bk.com/fta/v1/event/?token=Token&source=google
    ```

2. 告警回调配置指引 以下指引腾讯云及谷歌云的告警回调配置
    #### 腾讯云
    （1）访问腾讯云可观测平台：进入[腾讯云可观测平台的通知模板页面](https://console.cloud.tencent.com/monitor/alarm/notice)
    
    （2）创建新通知模板
    
    （3）配置通知模板，接口回调输入回调接口地址
    
    （4）绑定告警策略：进入管理告警策略页面，关联通知模板与告警策略
    
    （5）接收告警信息
    
    （6）查看告警历史
    
    具体详情可参考腾讯云官网：<https://cloud.tencent.com/document/product/248/50409>
    #### 谷歌云
    （1）准备 Webhook 处理程序
    
    （2）访问 Google Cloud 控制台：选择 "Monitoring"，接着选择 "notifications"（提醒）
    
    （3）修改通知渠道
    
    （4）添加新的 Webhook：在 "网络钩子" 部分，点击 "新增"
    
    （5）填写表单
    
    （6）点测试连接：访问接收端点以确认是否成功接收
    
    （7）保存设置
    
    具体详情可参考谷歌云官网：<https://cloud.google.com/monitoring/support/notification-options?hl=zh-cn#webhooks>

3. 完成
    ##
