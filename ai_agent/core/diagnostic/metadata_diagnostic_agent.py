# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
from typing import Any, Dict, Generator, Optional

from langchain.agents import AgentExecutor, Tool
from langchain.agents.chat.base import ChatAgent
from langchain_core.prompts import ChatPromptTemplate

from ai_agent.llm import LLMConfig, LLMModel, LLMProvider, get_llm
from metadata.resources.bkdata_link import QueryDataLinkInfoResource

logger = logging.getLogger("ai_agent")


class MetadataDiagnosisAgent:
    def __init__(self):
        self.tools = [
            Tool(name="fetch_metadata", func=self.get_metadata_info, description="获取元数据信息"),
            Tool(name="llm_analysis", func=self.llm_analysis_engine, description="LLM决策分析引擎"),
        ]

    def get_metadata_info(self, bk_data_id: int) -> dict:
        """获取元数据信息"""
        return QueryDataLinkInfoResource().request(bk_data_id=bk_data_id)

    def _build_diagnosis_prompt(self, metadata: dict) -> str:
        structured_prompt = """
        # ROLE
            监控平台元数据诊断分析专家
            你是一位监控平台排障专家,严格依照这里提供的提示词进行工作,严格遵循 `RULES` 中定义的规则
        
            
        ## Initialization
            你是一位监控平台排障专家,熟悉监控平台整体架构,了解数据链路的构成与查询路由的工作原理,能够快速定位获取到的数据元信息中的异常问题。
            ！严格按照 `RULES` 中定义的规则进行工作！严格按照 `WORKFLOW` 中定义的工作流进行工作 ！
            监控平台的链路按照存储类型大致分为两类,指标和日志链路,指标类型使用VictoriaMetrics进行存储,日志类型使用Elasticsearch进行存储。
            数据链路大致可以描述为: DS(数据源)-> Transfer / BkBase (清洗) -> VM / ES (存储) 通过RT(结果表)进行查询
            指标类型的元数据信息中,会包含 `bkbase_infos` 字段,即接入计算平台信息,因为指标链路目前是接入到计算平台进行清洗和入库的
            日志类型的元数据信息中,会包含 `es_storage_infos`字段,即ES配置信息,包含了数据的ES索引各项配置,如大小切分阈值、过期时间等
            整体的数据查询路由,主要有结果表详情(RESULT_TABLE_DETAIL)、空间<->结果表授权访问关系(SPACE_TO_RESULT_TABLE)等信息构成
            
        
            
        ## Configuration & Input
            {metadata_json}  你要分析的是某个bk_data_id的元数据信息，其是JSON格式，其中包含以下信息：
            ds_infos: 数据源关联信息,主要关注清洗配置、是否启用、链路版本、Transfer集群ID
            etl_infos: 清洗配置,主要关注前端Kafka集群信息和分区数量以及Topic名称,若获取失败,则会显示集群配置获取异常
            rt_infos: 结果表关联信息,主要关注存储方案(InfluxDB/VM/ES) 和是否启用，以及后端Kafka配置信息
            es_storage_infos: 日志链路关联ES配置信息,主要关注索引状态、是否需要轮转、分片数量、分片副本数量、索引大小、索引过期时间、索引详情信息等
            bkbase_infos: 指标链路接入计算平台信息,主要关注接入计算平台记录是否存在以及VM结果表ID和查询集群地址
            authorized_space_uids: 空间授权访问关系,有权限访问该数据源的空间UID,{space_type}__{space_id},如bkcc__2,bkci__tkex
            expired_metrics: 一般情况下为空,指标链路会存在该信息,若不为空,说明指标发现服务异常
            rt_detail_router: 结果表详情路由,主要关注结果表中是否存在缺失指标,正常情况下,会显示 "status": "RT详情路由正常"
            space_to_result_table_router_infos: 空间<->结果表授权访问关系,主要关注授权关系是否正常
            
        ## DecisionTree
            Step1. 数据源是否禁用：if ds_infos.是否启用 == False → 数据源未启用,无数据
            Step2. 计算平台接入: (注意，仅当存储方案为InfluxDB/VM时进行此检验) if bkbase_infos.接入计算平台记录不存在 → 计算平台接入异常,兜底任务5min一次
            Step3. 清洗配置获取: if etl_infos.status == '集群配置获取异常'  → 清洗配置获取异常,整体链路接入异常,需联系管理员
            Step4. 日志链路关联检验： (注意，仅当存储方案为ES时进行5&6&7&8步骤检验)
            Step5. 日志链路-- ES集群状态: if es_storage_infos.当前索引详情信息.index_status != "green" → ES集群状态异常
            Step6. 日志链路-- ES集群分片: if es_storage_infos.是否需要进行索引轮转==True → 采集项索引异常,需要进行索引轮转
            Step7. 日志链路-- ES集群分片: if es_storage_infos.当前索引详情信息.index_size(GB) > es_storage_infos.ES索引大小切分阈值(GB) → 采集项索引需要进行轮转
            Step8. 日志链路-- 索引清理: if es_storage_infos.当前索引详情信息.index_related_alias_info.expired_alias != [] → 索引轮转异常,存在可清理的过期别名
            Step9. 指标发现服务: if expired_metrics != [] → 指标发现服务异常,存在过期指标
            Step10. 指标链路--RT详情路由: if rt_detail_router.status != "RT详情路由正常" → RT详情路由异常,存在缺失指标
            Step11. 空间授权访问关系路由: if space_to_result_table_router_infos.{space_uid}.status == "异常" → 空间授权访问关系异常,空间无数据查询权限
            
        ## OUTPUT
        你必须保证输出是严格的JSON类型
            {
                "bk_data_id": 数据源ID,
                "result_table_id": 结果表ID,
                "storage_type": 存储方案，InfluxDB/VM/ES,
                "datalink_version": 链路版本,
                "diagnosis_steps": [
                    {
                        "step": "决策步骤",
                        "result": "决策结果",
                        "evidence": "决策证据,罗列出具体的数据证据(如果有的话)",
                    },
                    ...
                ]
            }

        
        ## EXAMPLE
            以下是提供给你的一个指标数据样例,你可以参考这里的处理流程
        
            INPUT: {"ds_infos":{"数据源ID":566123,"是否启用":True,"链路版本":"V4链路"},"rt_infos":{"1001_bkmonitor_time_series_566123.__default":{"存储方案":"InfluxDB"},"bkbase_infos":[{"异常信息":"接入计算平台记录不存在！"}]}
            
            决策环节:
                依照DecisionTree中的Step2,首先由于存储方案为InfluxDB,所以需要进行计算平台接入异常检验,发现bkbase_infos中提示接入计算平台记录不存在
            
            OUTPUT:
                {
                    "bk_data_id": 566123,
                    "result_table_id": "1001_bkmonitor_time_series_566123.__default",
                    "storage_type": "InfluxDB",
                    "datalink_version": "V4链路",
                    "diagnosis_steps": [
                        {
                            "step": "计算平台接入异常",
                            "result": "异常",
                            "evidence": "接入计算平台记录不存在！"
                        }
                    ]
                }
        
        ## WORKFLOW
        
            1. 接收 输入（遵循 `Configuration & Input` 的JSON格式数据信息）
            2. 严格遵循 `RULES` 中定义的工作规则
            3. 根据 `DecisionTree`中定义的决策分析步骤,一步步按顺序进行分析决策
            4. 严格按照 `OUTPUT` 定义的输出格式,结合分析决策结果,输出分析诊断报告,禁止进行额外发散
        
        
        ## RULES
            1. 严格按照 `WORKFLOW` 定义的流程进行操作
            2. 严格结合 `Configuration&Input` 按照 `DecisionTree` 进行决策分析
            3. 严格按照 `OUTPUT` 的格式进行输出,禁止进行其余发散
            4. 严格按照 `OUTPUT` 定义的格式进行输出,禁止进行发散
            5. 输出报告时,必须罗列出关联的具体证据,比如当你发现索引切分阈值异常时,你应该指出当前数据中实际的值
            5. 输出报告时,不需要输出检验正常的部分,只需要输出异常部分
            6. 当你发现你的输出违背了以上规则中的任意一条时,重新开始WORKFLOW,重新组织输出
        
        请你务必严格遵守上述定义的各项规则执行！
        """
        return structured_prompt.replace("{metadata_json}", json.dumps(metadata, ensure_ascii=False))

    def llm_analysis_engine(self, metadata: dict) -> Dict[str, Any]:
        """优化后的LLM决策分析核心"""
        try:
            # 构造带格式约束的prompt
            structured_prompt = self._build_diagnosis_prompt(metadata)
            llm = get_llm(
                LLMConfig(
                    provider=LLMProvider.BLUEKING,
                    model=LLMModel.HUNYUAN_TURBO,
                )
            )

            # 获取带格式约束的响应
            response = llm.invoke(
                structured_prompt,
                temperature=0.1,  # 降低随机性确保稳定性
            )

            # 提取JSON部分（兼容可能的代码块包裹场景）
            json_str = response.content.split("```json")[-1].split("```")[0].strip()

            # 严格解析JSON
            return json.loads(json_str)

        except json.JSONDecodeError as e:
            logger.error(f"LLM响应解析失败: {e}\n原始响应: {response.content}")
            return {"error": "LLM响应格式异常", "details": str(e)}
        except Exception as e:
            logger.exception("LLM分析引擎异常")
            return {"error": "分析引擎异常", "details": str(e)}

    def diagnosis_flow(self, bk_data_id: int) -> Generator:
        """优化后的诊断流程"""
        try:
            # 参数校验
            if not isinstance(bk_data_id, int):
                raise ValueError("bk_data_id必须是整数类型")

            # 阶段1：元数据获取
            yield ("status", {"stage": "metadata", "progress": 20, "message": "获取元数据中..."})
            metadata = json.loads(self.get_metadata_info(bk_data_id))

            yield ("status", {"stage": "metadata", "progress": 40, "message": type(metadata)})
            if not metadata.get("ds_infos"):
                yield ("error", {"stage": "metadata", "message": "元数据获取失败，数据源不存在"})
                return

            # 阶段2：分析过程
            yield ("status", {"stage": "analysis", "progress": 50, "message": "启动动态决策分析"})
            analysis_result = self.llm_analysis_engine(metadata)

            if "error" in analysis_result:
                yield (
                    "error",
                    {
                        "stage": "analysis",
                        "message": f"分析引擎异常: {analysis_result.get('error')}",
                        "details": analysis_result.get("details"),
                    },
                )
                return

            # 阶段3：生成报告
            yield ("status", {"stage": "reporting", "progress": 90, "message": "生成诊断报告"})

            # 标准化输出格式
            formatted_report = {
                "bk_data_id": bk_data_id,
                "status": "completed",
                "diagnosis": analysis_result,
                "metadata_snapshot": {  # 包含关键元数据用于交叉验证
                    "is_enabled": metadata["ds_infos"].get("是否启用"),
                    "storage_type": next(iter(metadata["rt_infos"].values()), {}).get("存储方案"),
                    "etl_status": metadata["etl_infos"].get("status"),
                },
            }
            yield ("report", formatted_report)

        except Exception as e:
            logger.exception("诊断流程异常")
            yield ("error", {"stage": "unknown", "message": f"诊断流程异常: {str(e)}", "details": str(e)})

    @classmethod
    def diagnose(cls, bk_data_id: int) -> dict:
        """
        同步执行诊断流程并返回最终报告
        用法示例：
        report = MetadataDiagnosisAgent.diagnose(bk_data_id=12345)
        """
        agent = cls()
        generator = agent.diagnosis_flow(bk_data_id)

        final_report = None
        for result in generator:
            result_type, data = result
            if result_type == "report":
                final_report = data
            elif result_type == "error":
                raise RuntimeError(f"Diagnosis failed at stage {data['stage']}: {data['message']}")

        if not final_report:
            raise ValueError("Diagnosis completed but no report generated")

        return final_report
