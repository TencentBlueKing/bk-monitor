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
import os
from typing import Any
from collections.abc import Generator

from langchain.agents import Tool
from tenacity import retry, stop_after_attempt, wait_exponential

from ai_agent.llm import LLMConfig, LLMModel, LLMProvider, get_llm
from metadata.resources.bkdata_link import QueryDataLinkInfoResource

from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.core.extend.models.llm_gateway import ChatModel
from aidev_agent.services.chat import ChatCompletionAgent, ExecuteKwargs
from aidev_agent.services.pydantic_models import ChatPrompt
from django.conf import settings

logger = logging.getLogger("metadata")


class MetadataDiagnosisAgent:
    def __init__(self):
        self.tools = [
            Tool(name="fetch_metadata", func=self.get_metadata_info, description="获取元数据信息"),
            Tool(name="llm_analysis", func=self.llm_analysis_engine, description="LLM决策分析引擎"),
        ]

    def _load_prompt(self, prompt_name):
        """
        加载提示词模版
        """
        prompt_path = os.path.join(f"metadata/agents/prompts/{prompt_name}.md")
        with open(prompt_path, encoding="utf-8") as f:
            prompt = f.read()
        return prompt

    def get_metadata_info(self, bk_data_id: int) -> dict:
        """
        调用接口获取元数据信息
        """
        return QueryDataLinkInfoResource().request(bk_data_id=bk_data_id)

    def _build_diagnosis_prompt(self, metadata: dict) -> str:
        """
        构造诊断引擎提示词
        """
        prompt_template = self._load_prompt("diagnostic")
        return prompt_template.replace("{metadata_json}", json.dumps(metadata, ensure_ascii=False))

    def llm_analysis_engine(self, metadata: dict) -> dict[str, Any]:
        """
        LLM决策分析引擎
        """
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
        """
        诊断工作流
        """
        try:
            # 参数校验
            if not isinstance(bk_data_id, int):
                raise ValueError("bk_data_id必须是整数类型")

            # 阶段1：元数据获取
            yield "status", {"stage": "metadata", "progress": 20, "message": "获取元数据中..."}

            metadata = self.get_metadata_info(bk_data_id)
            if not isinstance(metadata, dict):
                metadata = json.loads(metadata)  # 兼容类型转换

            if not metadata.get("ds_infos"):
                yield "error", {"stage": "metadata", "message": "元数据获取失败，数据源不存在"}
                return

            # 阶段2：分析过程
            yield "status", {"stage": "analysis", "progress": 50, "message": "启动动态决策分析"}
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
            yield "status", {"stage": "reporting", "progress": 90, "message": "生成诊断报告"}

            # 标准化输出格式
            formatted_report = {
                "bk_data_id": bk_data_id,
                "status": "completed",
                "diagnosis": analysis_result,
                "metadata_snapshot": {  # 包含关键元数据用于交叉验证
                    "is_enabled": metadata["ds_infos"].get("是否启用"),
                    "storage_type": next(iter(metadata["rt_infos"].values()), {}).get("存储方案"),
                    "etl_config": metadata["ds_infos"].get("清洗配置(etl_config)"),
                },
            }
            yield "report", formatted_report

        except Exception as e:  # pylint: disable=broad-except
            logger.exception("诊断流程异常")
            yield "error", {"stage": "unknown", "message": f"诊断流程异常: {str(e)}", "details": str(e)}

    def _collect_complete_answer(agent):
        """
        请求AIDEV LLM,结构化封装返回数据
        """
        thinking_content = ""
        answer_content = ""

        for chunk in agent.execute(ExecuteKwargs(stream=True)):
            # 跳过非数据行
            if not chunk.startswith("data: "):
                continue

            # 跳过结束标记
            if chunk.strip() == "data: [DONE]":
                break

            try:
                # 解析JSON数据
                json_str = chunk[6:].strip()  # 移除 "data: " 前缀
                data = json.loads(json_str)

                event_type = data.get("event", "")
                content = data.get("content", "")

                # 收集不同类型的内容
                if event_type == "think":
                    thinking_content += content
                elif event_type == "text":
                    answer_content += content

            except json.JSONDecodeError:
                continue
            except Exception as e:  # pylint: disable=broad-except
                logger.error("MetadataDiagnosisAgent: unexpected error occurs in sdk way->[%s]", e)
                continue

        return {
            "thinking": thinking_content.strip(),
            "answer": answer_content.strip(),
            "full_response": answer_content.strip(),
        }

    @classmethod
    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=10))
    def diagnose(cls, bk_data_id: int) -> dict:
        """
        同步执行诊断流程并返回最终报告
        """
        logger.info("MetadataDiagnosisAgent: start to diagnose with bk_data_id->[%s]", bk_data_id)

        agent = cls()
        generator = agent.diagnosis_flow(bk_data_id)

        final_report = None
        for result in generator:
            result_type, data = result
            if result_type == "report":
                final_report = data
            elif result_type == "error":
                logger.error(
                    "MetadataDiagnosisAgent: bk_data_id->[%s],Diagnosis failed->[%s]", bk_data_id, data["message"]
                )
                raise RuntimeError(f"Diagnosis failed at stage {data['stage']}: {data['message']}")

        if not final_report:
            raise ValueError("Diagnosis completed but no report generated")

        return final_report

    @classmethod
    def diagnose_by_agent_sdk(cls, bk_data_id: int):
        """
        使用AIDEV SDK执行诊断流程
        早期快速迭代中，暂不做更多的封装处理
        @param bk_data_id: 数据源ID
        """

        # 1. 初始化LLM模型服务
        llm_model_name = settings.AIDEV_LLM_MODEL_NAME
        llm = ChatModel.get_setup_instance(model=llm_model_name)
        client = BKAidevApi.get_client()

        # 2. 获取工具（工具注册在AIDEV平台）
        tool_code_list = settings.AIDEV_METADATA_TOOL_CODE_LIST
        tools = [client.construct_tool(tool_code) for tool_code in tool_code_list]

        logger.info(
            "MetadataDiagnosisAgent: start to diagnose with bk_data_id->[%s],use model->[%s]",
            bk_data_id,
            llm_model_name,
        )

        # 3. 构建用户输入
        user_question = f"Please help me check,bk_data_id->{bk_data_id}"

        # 4. 构建Agent ChatHistory -- 包含系统Role Prompt （后续支持根据role-code获取）
        prompt = cls._load_prompt()
        chat_history = [ChatPrompt(role="system", content=prompt), ChatPrompt(role="user", content=user_question)]

        # 5. 构建Agent实例
        agent = ChatCompletionAgent(
            chat_model=llm,
            chat_history=chat_history,
            tools=tools,
        )

        # 6. Agent 启动！
        result = cls._collect_complete_answer(agent)

        logger.info("MetadataDiagnosisAgent: diagnose_by_agent_sdk finished,answer->[%s]", result["answer"])

        # 7. 返回分析结果
        return result
