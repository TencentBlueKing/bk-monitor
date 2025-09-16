export const log = {
    "log_detail": "====================[bkunifylogbeat] 下发插件配置====================\n\n--------------------初始化进程状态--------------------\n[2025-09-15 16:48:38 INFO] 开始 初始化进程状态.\n[2025-09-15 16:48:38 INFO] 初始化进程状态 成功\n--------------------更新插件部署状态为UNKNOWN--------------------\n[2025-09-15 16:48:39 INFO] 开始 更新插件部署状态为UNKNOWN.\n[2025-09-15 16:48:39 INFO] 更新插件部署状态为UNKNOWN 成功\n--------------------渲染下发配置--------------------\n[2025-09-15 16:48:39 INFO] 开始 渲染下发配置.\n[2025-09-15 16:48:40 INFO] 下发配置文件 [bkunifylogbeat_sub_33561_host_2000058532.conf] 到目标机器路径 [/usr/local/gse2_cloud/plugins/etc/bkunifylogbeat]，若下发失败，请检查作业平台所部署的机器是否已安装AGENT\n作业任务ID为 [20008368975]，点击跳转到 <a href=\"https://s-job.open.woa.com/api_execute/20008368975\" target=\"_blank\">[作业平台]</a>\n[2025-09-15 16:48:45 INFO] 渲染下发配置 成功\n--------------------重载进程--------------------\n[2025-09-15 16:48:46 INFO] 开始 重载进程.\n[2025-09-15 16:48:46 INFO] {\n  \"meta\": {\n    \"namespace\": \"nodeman\",\n    \"name\": \"bkunifylogbeat\"\n  },\n  \"op_type\": 8,\n  \"nodeman_spec\": {\n    \"process_status_id\": 7851593,\n    \"subscription_instance_id\": 57750394\n  },\n  \"hosts\": [\n    {\n      \"ip\": \"9.136.163.107\",\n      \"bk_agent_id\": \"02000000005254005ae3091720612442569e\",\n      \"bk_cloud_id\": 0\n    }\n  ],\n  \"spec\": {\n    \"identity\": {\n      \"index_key\": \"\",\n      \"proc_name\": \"bkunifylogbeat\",\n      \"setup_path\": \"/usr/local/gse2_cloud/plugins/bin\",\n      \"pid_path\": \"/var/run/gse2_cloud/bkunifylogbeat.pid\",\n      \"user\": \"root\"\n    },\n    \"control\": {\n      \"start_cmd\": \"./start.sh bkunifylogbeat\",\n      \"stop_cmd\": \"./stop.sh bkunifylogbeat\",\n      \"restart_cmd\": \"./restart.sh bkunifylogbeat\",\n      \"reload_cmd\": \"./reload.sh bkunifylogbeat\",\n      \"kill_cmd\": \"\",\n      \"version_cmd\": \"./bkunifylogbeat -v\",\n      \"health_cmd\": \"\"\n    },\n    \"resource\": {\n      \"cpu\": 30,\n      \"mem\": 10\n    },\n    \"alive_monitor_policy\": {\n      \"auto_type\": 1,\n      \"start_check_secs\": 30\n    }\n  }\n}\n[2025-09-15 16:48:46 INFO] GSE TASK ID: [O2:20250915084846:C31CCF11B43D47C299C5A3886825B176:54190323]\n[2025-09-15 16:48:52 INFO] 重载进程 成功\n--------------------托管进程--------------------\n[2025-09-15 16:48:52 INFO] 开始 托管进程.\n[2025-09-15 16:48:52 INFO] {\n  \"meta\": {\n    \"namespace\": \"nodeman\",\n    \"name\": \"bkunifylogbeat\"\n  },\n  \"op_type\": 3,\n  \"nodeman_spec\": {\n    \"process_status_id\": 7851593,\n    \"subscription_instance_id\": 57750394\n  },\n  \"hosts\": [\n    {\n      \"ip\": \"9.136.163.107\",\n      \"bk_agent_id\": \"02000000005254005ae3091720612442569e\",\n      \"bk_cloud_id\": 0\n    }\n  ],\n  \"spec\": {\n    \"identity\": {\n      \"index_key\": \"\",\n      \"proc_name\": \"bkunifylogbeat\",\n      \"setup_path\": \"/usr/local/gse2_cloud/plugins/bin\",\n      \"pid_path\": \"/var/run/gse2_cloud/bkunifylogbeat.pid\",\n      \"user\": \"root\"\n    },\n    \"control\": {\n      \"start_cmd\": \"./start.sh bkunifylogbeat\",\n      \"stop_cmd\": \"./stop.sh bkunifylogbeat\",\n      \"restart_cmd\": \"./restart.sh bkunifylogbeat\",\n      \"reload_cmd\": \"./reload.sh bkunifylogbeat\",\n      \"kill_cmd\": \"\",\n      \"version_cmd\": \"./bkunifylogbeat -v\",\n      \"health_cmd\": \"\"\n    },\n    \"resource\": {\n      \"cpu\": 30,\n      \"mem\": 10\n    },\n    \"alive_monitor_policy\": {\n      \"auto_type\": 1,\n      \"start_check_secs\": 30\n    }\n  }\n}\n[2025-09-15 16:48:54 INFO] GSE TASK ID: [O2:20250915084853:8BFE08945E004D938A05D788E5B531EB:54172565]\n[2025-09-15 16:48:59 INFO] 托管进程 成功\n--------------------更新插件部署状态为RUNNING--------------------\n[2025-09-15 16:49:00 INFO] 开始 更新插件部署状态为RUNNING.\n[2025-09-15 16:49:00 INFO] 更新插件部署状态为RUNNING 成功\n--------------------重置重试次数--------------------\n[2025-09-15 16:49:00 INFO] 开始 重置重试次数.\n[2025-09-15 16:49:00 INFO] 重置重试次数 成功",
    "log_result": {
        "task_id": 28605543,
        "record_id": 57750394,
        "instance_id": "host|instance|host|2000058532",
        "create_time": "2025-09-15 16:48:35",
        "pipeline_id": "61a15c617a0f4ad2bca85b06a824e4f9",
        "instance_info": {
            "host": {
                "ip": null,
                "bk_cpu": 8,
                "bk_mem": 31851,
                "bk_state": null,
                "operator": "lampardtang,alickchen,tyleryuwang,herazhang,fighterliu,hailinxiao,durantzhang,tobyjia,jsonwan,v_yuncchi,breezeli,p_cxxincao,jobadmin,v_jingfyang,p_dzhiye,dennismding,sherryyxu,v_hryang,howellliang,jasonjhong,motionsun,linuxhe,willgchen,paladinchen,ramboyang,jinruiliang,javanzhang,v_zijiawen,v_zhiguoshi,bennychen,v_zsczhang,ckzhan,sandrincai,javhou,jairwu,citruswang,rockieluo,uriwang,nekzhang,goldenyang,jeremylv,oaozhang,jayjhwu,markhan,ecoli",
                "bk_biz_id": 100605,
                "bk_os_bit": "64-bit",
                "dept_name": "",
                "relations": [
                    {
                        "bk_set_id": 76522,
                        "bk_set_name": "",
                        "bk_module_id": 526761,
                        "bk_module_name": ""
                    }
                ],
                "bk_host_id": 2000058532,
                "bk_os_name": "",
                "bk_os_type": "1",
                "bk_agent_id": "02000000005254005ae3091720612442569e",
                "bk_biz_name": "cc3.0测试",
                "bk_cloud_id": 0,
                "bk_isp_name": "0",
                "bk_host_name": "WeTERM-GateWay-02",
                "bk_addressing": "static",
                "bk_cloud_name": "直连区域",
                "bk_cpu_module": "Intel(R) Xeon(R) Platinum 8255C CPU @ 2.50GHz",
                "bk_os_version": "",
                "bk_state_name": null,
                "bk_bak_operator": "lampardtang,alickchen,tyleryuwang,herazhang,fighterliu,hailinxiao,durantzhang,tobyjia,jsonwan,v_yuncchi,breezeli,p_cxxincao,jobadmin,v_jingfyang,p_dzhiye,dennismding,sherryyxu,v_hryang,howellliang,jasonjhong,motionsun,linuxhe,willgchen,paladinchen,ramboyang,jinruiliang,javanzhang,v_zijiawen,v_zhiguoshi,bennychen,v_zsczhang,ckzhan,sandrincai,javhou,jairwu,citruswang,rockieluo,uriwang,nekzhang,goldenyang,jeremylv,oaozhang,jayjhwu,markhan,ecoli",
                "bk_host_innerip": "9.136.163.107",
                "bk_host_outerip": "",
                "bk_province_name": null,
                "bk_host_innerip_v6": "",
                "bk_host_outerip_v6": "",
                "bk_cpu_architecture": "x86",
                "bk_supplier_account": "tencent"
            },
            "meta": {
                "GSE_VERSION": "V2"
            },
            "scope": [
                {
                    "ip": "9.136.163.107",
                    "bk_cloud_id": 0,
                    "bk_supplier_id": 0
                }
            ],
            "service": null
        },
        "start_time": "2025-09-15 16:48:38",
        "finish_time": "2025-09-15 16:49:00",
        "steps": [
            {
                "id": "bkunifylogbeat",
                "type": "PLUGIN",
                "index": 0,
                "action": "INSTALL",
                "node_name": "[bkunifylogbeat] 下发插件配置",
                "extra_info": {},
                "pipeline_id": "f54fe0b342494439bd82edad1c5de442",
                "status": "SUCCESS",
                "start_time": "2025-09-15 16:48:38",
                "finish_time": "2025-09-15 16:49:00",
                "target_hosts": [
                    {
                        "node_name": "[bkunifylogbeat] 下发插件配置 0:9.136.163.107",
                        "pipeline_id": "f54fe0b342494439bd82edad1c5de442",
                        "status": "SUCCESS",
                        "start_time": "2025-09-15 16:48:38",
                        "finish_time": "2025-09-15 16:49:00",
                        "sub_steps": [
                            {
                                "index": 0,
                                "node_name": "初始化进程状态",
                                "step_code": "init_process_status",
                                "pipeline_id": "f54fe0b342494439bd82edad1c5de442",
                                "log": "[2025-09-15 16:48:38 INFO] 开始 初始化进程状态.\n[2025-09-15 16:48:38 INFO] 初始化进程状态 成功",
                                "ex_data": null,
                                "status": "SUCCESS",
                                "start_time": "2025-09-15 16:48:38",
                                "finish_time": "2025-09-15 16:48:38"
                            },
                            {
                                "index": 1,
                                "node_name": "更新插件部署状态为UNKNOWN",
                                "step_code": "update_host_process_status",
                                "pipeline_id": "2d6eacc653ff4c1aa9aedfad1476bacf",
                                "log": "[2025-09-15 16:48:39 INFO] 开始 更新插件部署状态为UNKNOWN.\n[2025-09-15 16:48:39 INFO] 更新插件部署状态为UNKNOWN 成功",
                                "ex_data": null,
                                "status": "SUCCESS",
                                "start_time": "2025-09-15 16:48:39",
                                "finish_time": "2025-09-15 16:48:39"
                            },
                            {
                                "index": 2,
                                "node_name": "渲染下发配置",
                                "step_code": "render_and_push_config",
                                "pipeline_id": "f63fb71599fb4c52bc9b17e5f6b89af5",
                                "log": "[2025-09-15 16:48:39 INFO] 开始 渲染下发配置.\n[2025-09-15 16:48:40 INFO] 下发配置文件 [bkunifylogbeat_sub_33561_host_2000058532.conf] 到目标机器路径 [/usr/local/gse2_cloud/plugins/etc/bkunifylogbeat]，若下发失败，请检查作业平台所部署的机器是否已安装AGENT\n作业任务ID为 [20008368975]，点击跳转到 <a href=\"https://s-job.open.woa.com/api_execute/20008368975\" target=\"_blank\">[作业平台]</a>\n[2025-09-15 16:48:45 INFO] 渲染下发配置 成功",
                                "ex_data": null,
                                "status": "SUCCESS",
                                "start_time": "2025-09-15 16:48:39",
                                "finish_time": "2025-09-15 16:48:45",
                                "inputs": {
                                    "instance_info": {
                                        "host": {
                                            "ip": null,
                                            "bk_cpu": 8,
                                            "bk_mem": 31851,
                                            "bk_state": null,
                                            "operator": "lampardtang,alickchen,tyleryuwang,herazhang,fighterliu,hailinxiao,durantzhang,tobyjia,jsonwan,v_yuncchi,breezeli,p_cxxincao,jobadmin,v_jingfyang,p_dzhiye,dennismding,sherryyxu,v_hryang,howellliang,jasonjhong,motionsun,linuxhe,willgchen,paladinchen,ramboyang,jinruiliang,javanzhang,v_zijiawen,v_zhiguoshi,bennychen,v_zsczhang,ckzhan,sandrincai,javhou,jairwu,citruswang,rockieluo,uriwang,nekzhang,goldenyang,jeremylv,oaozhang,jayjhwu,markhan,ecoli",
                                            "bk_biz_id": 100605,
                                            "bk_os_bit": "64-bit",
                                            "dept_name": "",
                                            "relations": [
                                                {
                                                    "bk_set_id": 76522,
                                                    "bk_set_name": "",
                                                    "bk_module_id": 526761,
                                                    "bk_module_name": ""
                                                }
                                            ],
                                            "bk_host_id": 2000058532,
                                            "bk_os_name": "",
                                            "bk_os_type": "1",
                                            "bk_agent_id": "02000000005254005ae3091720612442569e",
                                            "bk_biz_name": "cc3.0测试",
                                            "bk_cloud_id": 0,
                                            "bk_isp_name": "0",
                                            "bk_host_name": "WeTERM-GateWay-02",
                                            "bk_addressing": "static",
                                            "bk_cloud_name": "直连区域",
                                            "bk_cpu_module": "Intel(R) Xeon(R) Platinum 8255C CPU @ 2.50GHz",
                                            "bk_os_version": "",
                                            "bk_state_name": null,
                                            "bk_bak_operator": "lampardtang,alickchen,tyleryuwang,herazhang,fighterliu,hailinxiao,durantzhang,tobyjia,jsonwan,v_yuncchi,breezeli,p_cxxincao,jobadmin,v_jingfyang,p_dzhiye,dennismding,sherryyxu,v_hryang,howellliang,jasonjhong,motionsun,linuxhe,willgchen,paladinchen,ramboyang,jinruiliang,javanzhang,v_zijiawen,v_zhiguoshi,bennychen,v_zsczhang,ckzhan,sandrincai,javhou,jairwu,citruswang,rockieluo,uriwang,nekzhang,goldenyang,jeremylv,oaozhang,jayjhwu,markhan,ecoli",
                                            "bk_host_innerip": "9.136.163.107",
                                            "bk_host_outerip": "",
                                            "bk_province_name": null,
                                            "bk_host_innerip_v6": "",
                                            "bk_host_outerip_v6": "",
                                            "bk_cpu_architecture": "x86",
                                            "bk_supplier_account": "tencent"
                                        },
                                        "meta": {
                                            "GSE_VERSION": "V2"
                                        },
                                        "scope": [
                                            {
                                                "ip": "9.136.163.107",
                                                "bk_cloud_id": 0,
                                                "bk_supplier_id": 0
                                            }
                                        ],
                                        "service": null
                                    }
                                }
                            },
                            {
                                "index": 3,
                                "node_name": "重载进程",
                                "step_code": "gse_operate_proc",
                                "pipeline_id": "466062087b3942188bab6a472d61cbe9",
                                "log": "[2025-09-15 16:48:46 INFO] 开始 重载进程.\n[2025-09-15 16:48:46 INFO] {\n  \"meta\": {\n    \"namespace\": \"nodeman\",\n    \"name\": \"bkunifylogbeat\"\n  },\n  \"op_type\": 8,\n  \"nodeman_spec\": {\n    \"process_status_id\": 7851593,\n    \"subscription_instance_id\": 57750394\n  },\n  \"hosts\": [\n    {\n      \"ip\": \"9.136.163.107\",\n      \"bk_agent_id\": \"02000000005254005ae3091720612442569e\",\n      \"bk_cloud_id\": 0\n    }\n  ],\n  \"spec\": {\n    \"identity\": {\n      \"index_key\": \"\",\n      \"proc_name\": \"bkunifylogbeat\",\n      \"setup_path\": \"/usr/local/gse2_cloud/plugins/bin\",\n      \"pid_path\": \"/var/run/gse2_cloud/bkunifylogbeat.pid\",\n      \"user\": \"root\"\n    },\n    \"control\": {\n      \"start_cmd\": \"./start.sh bkunifylogbeat\",\n      \"stop_cmd\": \"./stop.sh bkunifylogbeat\",\n      \"restart_cmd\": \"./restart.sh bkunifylogbeat\",\n      \"reload_cmd\": \"./reload.sh bkunifylogbeat\",\n      \"kill_cmd\": \"\",\n      \"version_cmd\": \"./bkunifylogbeat -v\",\n      \"health_cmd\": \"\"\n    },\n    \"resource\": {\n      \"cpu\": 30,\n      \"mem\": 10\n    },\n    \"alive_monitor_policy\": {\n      \"auto_type\": 1,\n      \"start_check_secs\": 30\n    }\n  }\n}\n[2025-09-15 16:48:46 INFO] GSE TASK ID: [O2:20250915084846:C31CCF11B43D47C299C5A3886825B176:54190323]\n[2025-09-15 16:48:52 INFO] 重载进程 成功",
                                "ex_data": null,
                                "status": "SUCCESS",
                                "start_time": "2025-09-15 16:48:46",
                                "finish_time": "2025-09-15 16:48:52"
                            },
                            {
                                "index": 4,
                                "node_name": "托管进程",
                                "step_code": "gse_operate_proc",
                                "pipeline_id": "e01de6a2af9b44719d11515282753564",
                                "log": "[2025-09-15 16:48:52 INFO] 开始 托管进程.\n[2025-09-15 16:48:52 INFO] {\n  \"meta\": {\n    \"namespace\": \"nodeman\",\n    \"name\": \"bkunifylogbeat\"\n  },\n  \"op_type\": 3,\n  \"nodeman_spec\": {\n    \"process_status_id\": 7851593,\n    \"subscription_instance_id\": 57750394\n  },\n  \"hosts\": [\n    {\n      \"ip\": \"9.136.163.107\",\n      \"bk_agent_id\": \"02000000005254005ae3091720612442569e\",\n      \"bk_cloud_id\": 0\n    }\n  ],\n  \"spec\": {\n    \"identity\": {\n      \"index_key\": \"\",\n      \"proc_name\": \"bkunifylogbeat\",\n      \"setup_path\": \"/usr/local/gse2_cloud/plugins/bin\",\n      \"pid_path\": \"/var/run/gse2_cloud/bkunifylogbeat.pid\",\n      \"user\": \"root\"\n    },\n    \"control\": {\n      \"start_cmd\": \"./start.sh bkunifylogbeat\",\n      \"stop_cmd\": \"./stop.sh bkunifylogbeat\",\n      \"restart_cmd\": \"./restart.sh bkunifylogbeat\",\n      \"reload_cmd\": \"./reload.sh bkunifylogbeat\",\n      \"kill_cmd\": \"\",\n      \"version_cmd\": \"./bkunifylogbeat -v\",\n      \"health_cmd\": \"\"\n    },\n    \"resource\": {\n      \"cpu\": 30,\n      \"mem\": 10\n    },\n    \"alive_monitor_policy\": {\n      \"auto_type\": 1,\n      \"start_check_secs\": 30\n    }\n  }\n}\n[2025-09-15 16:48:54 INFO] GSE TASK ID: [O2:20250915084853:8BFE08945E004D938A05D788E5B531EB:54172565]\n[2025-09-15 16:48:59 INFO] 托管进程 成功",
                                "ex_data": null,
                                "status": "SUCCESS",
                                "start_time": "2025-09-15 16:48:52",
                                "finish_time": "2025-09-15 16:48:59"
                            },
                            {
                                "index": 5,
                                "node_name": "更新插件部署状态为RUNNING",
                                "step_code": "update_host_process_status",
                                "pipeline_id": "10125a9979c546089385b6be1df2ceea",
                                "log": "[2025-09-15 16:49:00 INFO] 开始 更新插件部署状态为RUNNING.\n[2025-09-15 16:49:00 INFO] 更新插件部署状态为RUNNING 成功",
                                "ex_data": null,
                                "status": "SUCCESS",
                                "start_time": "2025-09-15 16:49:00",
                                "finish_time": "2025-09-15 16:49:00"
                            },
                            {
                                "index": 6,
                                "node_name": "重置重试次数",
                                "step_code": "reset_retry_times",
                                "pipeline_id": "75bf92bec55a457aada3a380f5311edc",
                                "log": "[2025-09-15 16:49:00 INFO] 开始 重置重试次数.\n[2025-09-15 16:49:00 INFO] 重置重试次数 成功",
                                "ex_data": null,
                                "status": "SUCCESS",
                                "start_time": "2025-09-15 16:49:00",
                                "finish_time": "2025-09-15 16:49:00"
                            }
                        ]
                    }
                ]
            }
        ],
        "status": "SUCCESS"
    }
}
export const contents = [
    {
        "is_label": false,
        "label_name": "",
        "bk_obj_name": "主机",
        "node_path": "主机",
        "bk_obj_id": "host",
        "bk_inst_id": "",
        "bk_inst_name": "",
        "child": [
            {
                "host_id": 2000058532,
                "status": "SUCCESS",
                "ip": "9.136.163.107",
                "ipv6": "",
                "host_name": "WeTERM-GateWay-02",
                "cloud_id": 0,
                "log": "",
                "instance_id": "host|instance|host|2000058532",
                "instance_name": "9.136.163.107",
                "task_id": 28605543,
                "bk_supplier_id": "tencent",
                "create_time": "2025-09-15 16:48:35",
                "steps": {
                    "bkunifylogbeat": "INSTALL"
                }
            },
            {
                "host_id": 2000058531,
                "status": "SUCCESS",
                "ip": "9.136.163.56",
                "ipv6": "",
                "host_name": "WeTERM-GateWay-01",
                "cloud_id": 0,
                "log": "",
                "instance_id": "host|instance|host|2000058531",
                "instance_name": "9.136.163.56",
                "task_id": 28605543,
                "bk_supplier_id": "tencent",
                "create_time": "2025-09-15 16:48:35",
                "steps": {
                    "bkunifylogbeat": "INSTALL"
                }
            }
        ]
    }
]