"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CreateModelCls:
    """
    模型创建
    """

    project_id: int
    model_name: str
    description: str
    processing_cluster_id: int
    storage_cluster_id: int
    scene_name: str = "custom"
    sensitivity: str = "private"
    run_env: str = "python"
    sample_type: str = "timeseries"
    modeling_type: str = "aiops"
    protocol_version: str = "1.2"


@dataclass
class CreateExperimentsCls:
    """
    创建实验
    """

    project_id: int
    template_id: str
    experiment_alias: str
    model_id: str
    experiment_training: bool = True
    continuous_training: bool = True
    protocol_version: str = "1.2"


@dataclass
class GetExperimentsConfigCls:
    """
    查看实验配置
    """

    project_id: int
    model_id: str
    experiment_id: int
    protocol_version: str = "1.1"


@dataclass
class GetExperimentsMetaDataCls:
    """
    查询metadata实验配置
    """

    filter_id: int
    table_name: str = "model_experiment"


@dataclass
class PythonBackendCls:
    worker_nums: int
    memory: int
    worker_group: str = "default"
    core: int = 2


@dataclass
class MemoryStepScalingPolicyCls:
    max_memory: int
    step: int = 1024
    target_worker_type: str = "python_backend"


@dataclass
class SessionAgentCls:
    worker_nums: int = 1
    worker_group: str = "default"
    core: int = 2
    memory: int = 1024


@dataclass
class SessionServerCls:
    worker_nums: int = 1
    worker_group: str = "default"
    core: int = 2
    memory: int = 2048


@dataclass
class PartitionNumberConfigCls:
    partition_number: int = 8


@dataclass
class ChunkPolicyCls:
    type: str = "partition"
    config: PartitionNumberConfigCls = field(default_factory=PartitionNumberConfigCls)


@dataclass
class ChunkedReadSampleSet:
    window: str
    chunk_policy: ChunkPolicyCls = field(default_factory=ChunkPolicyCls)


@dataclass
class SparkSessionCls:
    worker_nums: int = 1
    worker_group: str = "default"
    core: int = 2
    memory: int = 2048


@dataclass
class SessionWorkspaceCls:
    worker_group: str = "default"
    core: int = 2
    memory: int = 1024
    worker_nums: int = 1


@dataclass
class PipelineResourcesCls:
    python_backend: PythonBackendCls
    spark_session: SparkSessionCls = field(default_factory=SparkSessionCls)
    session_workspace: SessionWorkspaceCls = field(default_factory=SessionWorkspaceCls)


@dataclass
class ExecuteConfigCls:
    pipeline_resources: PipelineResourcesCls
    chunked_read_sample_set: ChunkedReadSampleSet
    pipeline_execute_config: dict
    resource_preference: dict
    pipeline_mode: str = "chunked_training"


@dataclass
class UpdateExecuteConfigCls:
    """
    编辑实验metadata配置
    """

    filter_id: int
    execute_config: ExecuteConfigCls
    table_name: str = "model_experiment"


@dataclass
class OutputConfigCls:
    field: list = field(default_factory=list)


@dataclass
class PropertiesCls:
    is_required: bool


@dataclass
class AdvanceConfigCls:
    used_by: str
    allow_modified: bool
    is_advanced_arg: bool


@dataclass
class PropertiesAddOptionalAndDependConfCls:
    is_required: bool
    optional_alias_mapping: dict
    optional: list[str]
    depend: dict


@dataclass
class PropertiesAddOptionalConfCls:
    is_required: bool
    optional_alias_mapping: dict
    optional: list[str]


@dataclass
class PropertiesAddDependConfCls:
    is_required: bool
    depend: dict


@dataclass
class PropertiesChangeToIncludeLabelCls:
    include_label: bool


@dataclass
class NodeConfigCls:
    id: int
    arg_name: str
    action_name: str
    arg_alias: str
    arg_index: int
    data_type: str
    properties: (
        PropertiesCls
        | PropertiesAddOptionalConfCls
        | PropertiesAddDependConfCls
        | PropertiesChangeToIncludeLabelCls
        | PropertiesAddOptionalAndDependConfCls
        | dict
    )
    description: str
    default_value: Any
    advance_config: AdvanceConfigCls
    value: Any


@dataclass
class SampleLoadingContentNodeConfigCls:
    sample_set_id: NodeConfigCls
    data_sampling: NodeConfigCls
    sampling_time_range: NodeConfigCls
    sampling_conditions: NodeConfigCls
    sampling_func: NodeConfigCls


@dataclass
class SamplePreparationContentNodeConfigCls:
    data_split: NodeConfigCls
    split_func: NodeConfigCls
    group_enable: NodeConfigCls
    group_mode: NodeConfigCls
    group_fields: NodeConfigCls


@dataclass
class ModelTrainContentNodeConfigCls:
    upload_model_file: NodeConfigCls
    algorithm_selection: NodeConfigCls
    training_input: NodeConfigCls
    upload_method: NodeConfigCls
    model_file: NodeConfigCls
    param_adjust_type: NodeConfigCls
    evaluation_func: NodeConfigCls
    optimize_targets: NodeConfigCls
    optimize_algorithm: NodeConfigCls
    stop_policy_config: NodeConfigCls
    visualization: NodeConfigCls


@dataclass
class ModelEvaluationContentNodeConfigCls:
    algorithm_node_id: NodeConfigCls
    evaluation_func: NodeConfigCls
    evaluate_input: NodeConfigCls


@dataclass
class SampleLoadingContentAlgorithmConfigCls:
    sample_set_table_name: Any = None
    sample_set_table_desc: Any = None
    feature_columns: list[str] = field(default_factory=list)
    add_on_input: list[str] = field(default_factory=list)
    label_columns: list[str] = field(default_factory=list)
    training_output: list[str] = field(default_factory=list)
    predict_output: list[str] = field(default_factory=list)
    training_args: list[str] = field(default_factory=list)
    predict_args: list[str] = field(default_factory=list)
    split_args: list[str] = field(default_factory=list)
    sampling_args: list[str] = field(default_factory=list)
    evaluate_args: list[str] = field(default_factory=list)
    optimize_args: list[str] = field(default_factory=list)
    timestamp_columns: list[str] = field(default_factory=list)
    predicted_columns: list[str] = field(default_factory=list)
    evaluate_output: list[str] = field(default_factory=list)
    feature_columns_changeable: bool = False
    algorithm_properties: dict = field(default_factory=dict)
    data_split: bool = False
    ts_depend: str = "0d"


@dataclass
class SamplePreparationContentAlgorithmConfigCls:
    split_args: list = field(default_factory=list)


@dataclass
class FeatureColumnsCommonPropertiesCls:
    input_type: str


@dataclass
class FeatureColumnsPropertiesCls:
    used_by: str
    allow_modified: bool
    is_advanced: bool
    allow_null: bool
    support: bool


@dataclass
class FeatureColumnsPropertiesAddInputTypeCls:
    used_by: str
    allow_modified: bool
    is_advanced: bool
    allow_null: bool
    support: bool
    input_type: str


@dataclass
class TrainingArgsPropertiesCls:
    input_type: str
    support: bool
    allow_null: bool
    allow_modified: bool
    is_advanced: bool
    used_by: str
    closed: Any
    is_required: bool
    placeholder: str
    allowed_values_map: list[str] = field(default_factory=list)


@dataclass
class AlgorithmConfigConfCls:
    field_name: str
    field_alias: str
    field_index: int
    default_value: Any
    sample_value: Any
    value: Any
    data_field_name: None
    data_field_alias: None
    field_type: str
    roles: dict
    properties: (
        FeatureColumnsPropertiesCls
        | TrainingArgsPropertiesCls
        | FeatureColumnsPropertiesAddInputTypeCls
        | FeatureColumnsCommonPropertiesCls
        | dict
    )
    description: Any
    used_by: str
    origin: list[str] = field(default_factory=list)
    allowed_values: list[str] = field(default_factory=list)


@dataclass
class ModelTrainContentAlgorithmConfigCls:
    sample_set_table_name: Any
    sample_set_table_desc: Any
    training_input: list[AlgorithmConfigConfCls]
    training_meta: dict
    training_args: list[AlgorithmConfigConfCls]
    basic_model_id: str
    add_on_input: list[str] = field(default_factory=list)
    label_columns: list[str] = field(default_factory=list)
    training_output: list[str] = field(default_factory=list)
    predict_args: list[str] = field(default_factory=list)
    split_args: list[str] = field(default_factory=list)
    sampling_args: list[str] = field(default_factory=list)
    evaluate_args: list[str] = field(default_factory=list)
    optimize_args: list[str] = field(default_factory=list)
    timestamp_columns: list[str] = field(default_factory=list)
    predicted_columns: list[str] = field(default_factory=list)
    evaluate_output: list[str] = field(default_factory=list)
    feature_columns_changeable: bool = True
    algorithm_properties: dict = field(default_factory=dict)
    data_split: bool = False
    ts_depend: str = "0d"
    run_env: str = "python"
    active: bool = True
    sample_set_table_alias: Any = None


@dataclass
class AlgorithmPropertiesCls:
    algorithm_name: str
    logic: str
    algorithm_framework: str
    algorithm_version: int
    load_mode: str


@dataclass
class ModelEvaluationContentAlgorithmConfigCls:
    algorithm_config: list[AlgorithmConfigConfCls]
    predict_output: list[AlgorithmConfigConfCls]
    training_args: list[AlgorithmConfigConfCls]
    timestamp_columns: list[AlgorithmConfigConfCls]
    feature_columns_changeable: bool
    algorithm_properties: AlgorithmPropertiesCls
    label_columns: list[str] = field(default_factory=list)
    training_output: list[str] = field(default_factory=list)
    predict_args: list[str] = field(default_factory=list)
    split_args: list[str] = field(default_factory=list)
    evaluate_args: list[str] = field(default_factory=list)
    optimize_args: list[str] = field(default_factory=list)
    predicted_columns: list[str] = field(default_factory=list)
    evaluate_output: list[str] = field(default_factory=list)
    data_split: bool = False
    ts_depend: str = "0d"
    run_env: str = "python"


@dataclass
class ContentCls:
    node_config: (
        SampleLoadingContentNodeConfigCls
        | SamplePreparationContentNodeConfigCls
        | ModelTrainContentNodeConfigCls
        | ModelEvaluationContentNodeConfigCls
    )
    algorithm_config: (
        SampleLoadingContentAlgorithmConfigCls
        | SamplePreparationContentAlgorithmConfigCls
        | ModelTrainContentAlgorithmConfigCls
        | ModelEvaluationContentAlgorithmConfigCls
    )
    output_config: OutputConfigCls = field(default_factory=OutputConfigCls)
    input_config: dict = field(default_factory=dict)
    prediction_algorithm_config: dict = field(default_factory=dict)


@dataclass
class NodeCls:
    node_id: str
    model_id: str
    node_name: str
    node_alias: str
    node_index: int
    run_status: str
    operate_status: str
    model_experiment_id: int
    content: ContentCls
    step_name: str
    action_name: str
    action_alias: str

    properties: dict = field(default_factory=dict)
    active: int = 1
    node_role: dict = field(default_factory=dict)
    execute_config: dict = field(default_factory=dict)


@dataclass
class SampleLoadingCls:
    model_id: str
    experiment_id: int
    model_experiment_id: int
    nodes: list[NodeCls]
    pipeline_mode: Any = None
    step_name: str = "sample_loading"


@dataclass
class SamplePreparationCls:
    """
    执行样本切分
    """

    model_id: str
    experiment_id: int
    model_experiment_id: int
    nodes: list[NodeCls]
    pipeline_mode: Any = None
    step_name: str = "sample_preparation"


@dataclass
class ExecuteStatusCls:
    """
    获取切分步骤状态
    """

    step_name: str
    model_id: str
    experiment_id: int
    node_id_list: list[str]


@dataclass
class ModelTrainCls:
    """
    执行实验训练
    """

    model_id: str
    experiment_id: int
    model_experiment_id: int
    nodes: list[NodeCls]
    pipeline_mode: Any = None
    step_name: str = "model_train"


@dataclass
class ModelTrainNodesContentNodeConfigTrainingInputValueFeatureColumnCls:
    field_type: str
    field_alias: str
    description: None
    is_dimension: bool
    field_name: str
    field_index: int
    default_value: Any
    properties: dict
    sample_value: Any
    attr_type: str
    data_field_name: str
    data_field_alias: str
    roles: dict
    is_ts_field: bool
    used_by: str
    deletable: bool
    err: dict
    is_save: bool
    origin: list[str] = field(default_factory=list)


@dataclass
class ModelTrainNodesContentNodeConfigTrainingInputValueCls:
    """
    模型训练 node_config中training_input value
    """

    feature_columns: list[ModelTrainNodesContentNodeConfigTrainingInputValueFeatureColumnCls]
    label_columns: list[str] = field(default_factory=list)


@dataclass
class ModelTrainNodesContentNodeConfigVisualizationComponentsCls:
    component_type: str
    component_name: str
    component_alias: str
    logic: str
    logic_type: str
    description: str


@dataclass
class ModelTrainNodesContentNodeConfigVisualizationValueCls:
    visualization_name: str
    target_name: str
    target_type: str
    scene_name: str
    components: list[ModelTrainNodesContentNodeConfigVisualizationComponentsCls]


@dataclass
class ModelTrainTrainingStatusCls:
    """
    备选模型训练状态列表
    """

    model_id: str
    experiment_id: int
    project_id: int
    order: str = "algorithm_alias"
    order_type: Any = None
    filter_extra: dict = field(default_factory=dict)


@dataclass
class AiopsGetCostumAlgorithm:
    """
    获取单个自定义算法
    """

    algorithm_name: str
    project_id: int


@dataclass
class ModelEvaluationCls:
    """
    模型评估
    """

    model_experiment_id: int
    model_id: str
    experiment_id: int
    nodes: list[NodeCls]
    pipeline_mode: Any = None
    step_name: str = "model_evaluation"


@dataclass
class EvaluationStatusCls:
    """
    模型评估状态
    """

    project_id: int
    model_id: str
    experiment_id: int
    filter_extra: dict
    order: str = "algorithm_alias"
    order_type: Any = None
    experiment_instance_id: Any = None


# 可以删
# @dataclass
# class EvaluationResultCls(object):
#     """
#     模型评估结果
#     """
#
#     project_id: int
#     model_id: str
#     experiment_id: int
#     basic_model_id: str
#     filter_extra: Dict = field(default_factory=dict)
#     experiment_instance_id: Any = None

# 可以删
# @dataclass
# class PreCommitCls(object):
#     """
#     实验提交前查看配置
#     """
#
#     model_id: str
#     project_id: int
#     model_experiment_id: int
#     experiment_id: int
#     passed_config: Dict
#     nodes: List[str] = field(default_factory=list)


@dataclass
class CommitServingConfigFeatureColumnCls:
    field_name: str
    field_type: str
    field_alias: str
    field_index: int
    value: Any
    default_value: Any
    sample_value: Any
    comparison: Any
    conflict_type: str
    attr_type: str
    is_ts_field: bool
    roles: dict
    origin: list[str]
    data_field_name: str
    data_field_alias: str
    used_by: str


@dataclass
class CommitServingConfigCls:
    feature_columns: list[CommitServingConfigFeatureColumnCls]
    predict_output: list[CommitServingConfigFeatureColumnCls]
    predict_args: list[str] = field(default_factory=list)


@dataclass
class CommitPassedConfigPredictResult:
    status: str
    status_alias: str
    used_time: float
    error_message: Any


@dataclass
class CommitPassedConfigCls:
    basic_model_id: str
    basic_model_name: str
    basic_model_alias: str
    basic_model_run_status: str
    algorithm_name: str
    algorithm_alias: str
    algorithm_version: str
    algorithm_generate_type: str
    description: str
    model_id: str
    experiment_id: int
    experiment_instance_id: int
    training_args: list[AlgorithmConfigConfCls]
    evaluation_disable: bool
    indicators: dict
    predict_result: CommitServingConfigFeatureColumnCls
    evaluation_result: CommitServingConfigFeatureColumnCls
    assess_value: bool
    index: int


# 可以删
# @dataclass
# class CommitCls(object):
#     """
#     实验提交
#     """
#
#     project_id: int
#     model_id: str
#     model_experiment_id: int
#     experiment_id: int
#     serving_config: CommitServingConfigCls
#     passed_config: CommitPassedConfigCls
#     experiment_config: Dict = field(default_factory=dict)
#     nodes: List[str] = field(default_factory=list)


@dataclass
class ReleaseServingConfigAutomlCls:
    param_adjust_type: str
    evaluation_func: str


@dataclass
class ReleaseServingConfigCls:
    feature_columns: list[CommitServingConfigFeatureColumnCls]
    predict_output: list[CommitServingConfigFeatureColumnCls]
    training_args: list[AlgorithmConfigConfCls]
    timestamp_columns: list[AlgorithmConfigConfCls]
    predicted_columns: list[AlgorithmConfigConfCls]
    evaluate_output: list[AlgorithmConfigConfCls]
    feature_columns_changeable: bool
    algorithm_properties: AlgorithmPropertiesCls
    data_split: bool
    ts_depend: str
    run_env: str
    algorithm_framework: str
    automl: ReleaseServingConfigAutomlCls
    label_columns: list[str] = field(default_factory=list)
    training_output: list[str] = field(default_factory=list)
    predict_args: list[str] = field(default_factory=list)
    split_args: list[str] = field(default_factory=list)
    evaluate_args: list[str] = field(default_factory=list)
    optimize_args: list[str] = field(default_factory=list)


# 可以删
# @dataclass
# class ReleaseConfigCls(object):
#     """
#     发布配置
#     """
#
#     project_id: int
#     model_id: str
#     experiment_id: int
#     basic_model_id: str


# 可以删
@dataclass
# class ReleaseCls(object):
#     """
#     模型发布
#     """
#
#     model_id: str
#     model_experiment_id: int
#     experiment_id: int
#     basic_model_id: str
#     project_id: int
#     description: str
#     serving_config: ReleaseServingConfigCls
#     sample_feedback: bool = False


@dataclass
class UpdateTrainingScheduleCls:
    model_id: str
    project_id: int
    training_schedule: dict = field(
        default_factory=lambda: {
            "start_time": 0,
            "training_freq": 1,
            "success_rate_threshold": 0.8,
            "training_freq_unit": "h",
            "sample_change_count": 1,
        }
    )
    release_config: dict = field(default_factory=lambda: {"release_mode": "auto"})


@dataclass
class AiopsReleaseCls:
    model_id: str
    project_id: int
    extra_filters: str = "{}"


@dataclass
class AiopsReleaseModelReleaseIdModelFileCls:
    model_id: str
    model_release_id: str
    compat: str = "true"


@dataclass
class AiopsExperimentsDebugInputConfigCls:
    algorithm_name: str
    input_data: list
    feature_columns: list
    training_args: list
    result_table_id: str = "test"
    sql: str = "test"
    label_columns: list = field(default_factory=list)
    predict_args: list = field(default_factory=lambda: [{"value": 0, "field_name": "__start_time__"}])


@dataclass
class AiopsExperimentsDebugCls:
    input_config: AiopsExperimentsDebugInputConfigCls
    project_id: int
