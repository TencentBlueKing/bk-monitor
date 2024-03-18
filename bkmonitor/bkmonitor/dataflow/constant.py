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
from dataclasses import dataclass

from django.conf import settings

from bkmonitor.models import AlgorithmModel
from core.drf_resource import api


class VisualType:
    """
    可视化类型
    """

    # 只显示异常点
    NONE = "none"

    # 上下界
    BOUNDARY = "boundary"

    # 异常分值
    SCORE = "score"

    # 时序预测
    FORECASTING = "forecasting"


class AccessStatus:
    """
    数据接入的状态
    注意：这里不是指 flow 的状态，而是监控对 flow 接入流程的自身状态流转
    """

    # 等待中
    PENDING = "pending"

    # 已创建
    CREATED = "created"

    # 执行中
    RUNNING = "running"

    # 成功
    SUCCESS = "success"

    # 失败
    FAILED = "failed"


class RTAccessBkDataStatus:
    # 等待中
    PENDING = "pending"

    # 执行中
    RUNNING = "running"

    # 成功
    SUCCESS = "success"

    # 失败
    FAILED = "failed"


def get_scene_id_by_name(scene_name):
    """
    根据场景名称获取场景ID
    """
    for scene in api.bkdata.list_scene_service():
        if scene["scene_name"] == scene_name:
            return scene["scene_id"]
    return 0


@dataclass
class AlgorithmInfo:
    env_scene_variate_name: str
    env_plan_variate_name: str
    bk_base_name: str


METRIC_RECOMMENDATION_SCENE_NAME = "MetricRecommendation"

ALGORITHM_INFO_MAP = {
    AlgorithmModel.AlgorithmChoices.IntelligentDetect: AlgorithmInfo(
        env_scene_variate_name="BK_DATA_SCENE_ID_INTELLIGENT_DETECTION",
        env_plan_variate_name="BK_DATA_PLAN_ID_INTELLIGENT_DETECTION",
        bk_base_name="KPIAnomalyDetection",
    ),
    AlgorithmModel.AlgorithmChoices.TimeSeriesForecasting: AlgorithmInfo(
        env_scene_variate_name="BK_DATA_SCENE_ID_TIME_SERIES_FORECASTING",
        env_plan_variate_name="",
        bk_base_name="TimeSeriesForecasting",
    ),
    AlgorithmModel.AlgorithmChoices.AbnormalCluster: AlgorithmInfo(
        env_scene_variate_name="BK_DATA_SCENE_ID_ABNORMAL_CLUSTER",
        env_plan_variate_name="",
        bk_base_name="AbnormalCluster",
    ),
    AlgorithmModel.AlgorithmChoices.MultivariateAnomalyDetection: AlgorithmInfo(
        env_scene_variate_name="BK_DATA_SCENE_ID_MULTIVARIATE_ANOMALY_DETECTION",
        env_plan_variate_name="BK_DATA_PLAN_ID_MULTIVARIATE_ANOMALY_DETECTION",
        bk_base_name="MultivariateAnomalyDetection",
    ),
    METRIC_RECOMMENDATION_SCENE_NAME: AlgorithmInfo(
        env_scene_variate_name="BK_DATA_SCENE_ID_METRIC_RECOMMENDATION",
        env_plan_variate_name="BK_DATA_PLAN_ID_METRIC_RECOMMENDATION",
        bk_base_name="MetricRecommendation",
    ),
}


def get_scene_id_by_algorithm(algorithm_id):
    """
    获取算法场景ID
    """
    if not settings.IS_ACCESS_BK_DATA:
        # 未接入数据平台直接跳过
        return 0

    if algorithm_id not in ALGORITHM_INFO_MAP:
        return 0

    algorithm_info = ALGORITHM_INFO_MAP[algorithm_id]
    if not getattr(settings, algorithm_info.env_scene_variate_name):
        setattr(settings, algorithm_info.env_scene_variate_name, get_scene_id_by_name(algorithm_info.bk_base_name))
    return getattr(settings, algorithm_info.env_scene_variate_name)


AI_SETTING_ALGORITHMS = [
    AlgorithmModel.AlgorithmChoices.IntelligentDetect,
    AlgorithmModel.AlgorithmChoices.MultivariateAnomalyDetection,
]


def get_plan_id_by_algorithm(algorithm_id):
    if not settings.IS_ACCESS_BK_DATA:
        # 未接入数据平台直接跳过
        return 0

    if algorithm_id not in ALGORITHM_INFO_MAP:
        return 0

    algorithm_info = ALGORITHM_INFO_MAP[algorithm_id]

    if not algorithm_info.env_plan_variate_name:
        return 0

    if not getattr(settings, algorithm_info.env_plan_variate_name):
        plans = api.bkdata.list_scene_service_plans(scene_id=get_scene_id_by_algorithm(algorithm_id))

        if not plans:
            return 0

        setattr(settings, algorithm_info.env_plan_variate_name, plans[0]["plan_id"])
    return getattr(settings, algorithm_info.env_plan_variate_name)


def get_aiops_env_bkdata_biz_id():
    result = api.bkdata.get_aiops_envs()
    return result.get("BKDATA_BIZ_ID")


FLINK_KEY_WORDS = [
    'A',
    'ABS',
    'ABSOLUTE',
    'ACTION',
    'ADA',
    'ADD',
    'ADMIN',
    'AFTER',
    'ALL',
    'ALLOCATE',
    'ALLOW',
    'ALTER',
    'ALWAYS',
    'AND',
    'ANY',
    'ARE',
    'ARRAY',
    'AS',
    'ASC',
    'ASENSITIVE',
    'ASSERTION',
    'ASSIGNMENT',
    'ASYMMETRIC',
    'AT',
    'ATOMIC',
    'ATTRIBUTE',
    'ATTRIBUTES',
    'AUTHORIZATION',
    'AVG',
    'BEFORE',
    'BEGIN',
    'BERNOULLI',
    'BETWEEN',
    'BIGINT',
    'BINARY',
    'BIT',
    'BLOB',
    'BOOLEAN',
    'BOTH',
    'BREADTH',
    'BY',
    'BYTES',
    'C',
    'CALL',
    'CALLED',
    'CARDINALITY',
    'CASCADE',
    'CASCADED',
    'CASE',
    'CAST',
    'CATALOG',
    'CATALOG_NAME',
    'CEIL',
    'CEILING',
    'CENTURY',
    'CHAIN',
    'CHAR',
    'CHARACTER',
    'CHARACTERISTICS',
    'CHARACTERS',
    'CHARACTER_LENGTH',
    'CHARACTER_SET_CATALOG',
    'CHARACTER_SET_NAME',
    'CHARACTER_SET_SCHEMA',
    'CHAR_LENGTH',
    'CHECK',
    'CLASS_ORIGIN',
    'CLOB',
    'CLOSE',
    'COALESCE',
    'COBOL',
    'COLLATE',
    'COLLATION',
    'COLLATION_CATALOG',
    'COLLATION_NAME',
    'COLLATION_SCHEMA',
    'COLLECT',
    'COLUMN',
    'COLUMNS',
    'COLUMN_NAME',
    'COMMAND_FUNCTION',
    'COMMAND_FUNCTION_CODE',
    'COMMIT',
    'COMMITTED',
    'CONDITION',
    'CONDITION_NUMBER',
    'CONNECT',
    'CONNECTION',
    'CONNECTION_NAME',
    'CONSTRAINT',
    'CONSTRAINTS',
    'CONSTRAINT_CATALOG',
    'CONSTRAINT_NAME',
    'CONSTRAINT_SCHEMA',
    'CONSTRUCTOR',
    'CONTAINS',
    'CONTINUE',
    'CONVERT',
    'CORR',
    'CORRESPONDING',
    'COUNT',
    'COVAR_POP',
    'COVAR_SAMP',
    'CREATE',
    'CROSS',
    'CUBE',
    'CUME_DIST',
    'CURRENT',
    'CURRENT_CATALOG',
    'CURRENT_DATE',
    'CURRENT_DEFAULT_TRANSFORM_GROUP',
    'CURRENT_PATH',
    'CURRENT_ROLE',
    'CURRENT_SCHEMA',
    'CURRENT_TIME',
    'CURRENT_TIMESTAMP',
    'CURRENT_TRANSFORM_GROUP_FOR_TYPE',
    'CURRENT_USER',
    'CURSOR',
    'CURSOR_NAME',
    'CYCLE',
    'DATA',
    'DATABASE',
    'DATE',
    'DATETIME_INTERVAL_CODE',
    'DATETIME_INTERVAL_PRECISION',
    'DAY',
    'DEALLOCATE',
    'DEC',
    'DECADE',
    'DECIMAL',
    'DECLARE',
    'DEFAULT',
    'DEFAULTS',
    'DEFERRABLE',
    'DEFERRED',
    'DEFINED',
    'DEFINER',
    'DEGREE',
    'DELETE',
    'DENSE_RANK',
    'DEPTH',
    'DEREF',
    'DERIVED',
    'DESC',
    'DESCRIBE',
    'DESCRIPTION',
    'DESCRIPTOR',
    'DETERMINISTIC',
    'DIAGNOSTICS',
    'DISALLOW',
    'DISCONNECT',
    'DISPATCH',
    'DISTINCT',
    'DOMAIN',
    'DOUBLE',
    'DOW',
    'DOY',
    'DROP',
    'DYNAMIC',
    'DYNAMIC_FUNCTION',
    'DYNAMIC_FUNCTION_CODE',
    'EACH',
    'ELEMENT',
    'ELSE',
    'END',
    'END-EXEC',
    'EPOCH',
    'EQUALS',
    'ESCAPE',
    'EVERY',
    'EXCEPT',
    'EXCEPTION',
    'EXCLUDE',
    'EXCLUDING',
    'EXEC',
    'EXECUTE',
    'EXISTS',
    'EXP',
    'EXPLAIN',
    'EXTEND',
    'EXTERNAL',
    'EXTRACT',
    'FALSE',
    'FETCH',
    'FILTER',
    'FINAL',
    'FIRST',
    'FIRST_VALUE',
    'FLOAT',
    'FLOOR',
    'FOLLOWING',
    'FOR',
    'FOREIGN',
    'FORTRAN',
    'FOUND',
    'FRAC_SECOND',
    'FREE',
    'FROM',
    'FULL',
    'FUNCTION',
    'FUSION',
    'G',
    'GENERAL',
    'GENERATED',
    'GET',
    'GLOBAL',
    'GO',
    'GOTO',
    'GRANT',
    'GRANTED',
    'GROUP',
    'GROUPING',
    'HAVING',
    'HIERARCHY',
    'HOLD',
    'HOUR',
    'IDENTITY',
    'IMMEDIATE',
    'IMPLEMENTATION',
    'IMPORT',
    'IN',
    'INCLUDING',
    'INCREMENT',
    'INDICATOR',
    'INITIALLY',
    'INNER',
    'INOUT',
    'INPUT',
    'INSENSITIVE',
    'INSERT',
    'INSTANCE',
    'INSTANTIABLE',
    'INT',
    'INTEGER',
    'INTERSECT',
    'INTERSECTION',
    'INTERVAL',
    'INTO',
    'INVOKER',
    'IS',
    'ISOLATION',
    'JAVA',
    'JOIN',
    'K',
    'KEY',
    'KEY_MEMBER',
    'KEY_TYPE',
    'LABEL',
    'LANGUAGE',
    'LARGE',
    'LAST',
    'LAST_VALUE',
    'LATERAL',
    'LEADING',
    'LEFT',
    'LENGTH',
    'LEVEL',
    'LIBRARY',
    'LIKE',
    'LIMIT',
    'LN',
    'LOCAL',
    'LOCALTIME',
    'LOCALTIMESTAMP',
    'LOCATOR',
    'LOWER',
    'M',
    'MAP',
    'MATCH',
    'MATCHED',
    'MAX',
    'MAXVALUE',
    'MEMBER',
    'MERGE',
    'MESSAGE_LENGTH',
    'MESSAGE_OCTET_LENGTH',
    'MESSAGE_TEXT',
    'METHOD',
    'MICROSECOND',
    'MILLENNIUM',
    'MIN',
    'MINUTE',
    'MINVALUE',
    'MOD',
    'MODIFIES',
    'MODULE',
    'MODULES',
    'MONTH',
    'MORE',
    'MULTISET',
    'MUMPS',
    'NAME',
    'NAMES',
    'NATIONAL',
    'NATURAL',
    'NCHAR',
    'NCLOB',
    'NESTING',
    'NEW',
    'NEXT',
    'NO',
    'NONE',
    'NORMALIZE',
    'NORMALIZED',
    'NOT',
    'NULL',
    'NULLABLE',
    'NULLIF',
    'NULLS',
    'NUMBER',
    'NUMERIC',
    'OBJECT',
    'OCTETS',
    'OCTET_LENGTH',
    'OF',
    'OFFSET',
    'OLD',
    'ON',
    'ONLY',
    'OPEN',
    'OPTION',
    'OPTIONS',
    'OR',
    'ORDER',
    'ORDERING',
    'ORDINALITY',
    'OTHERS',
    'OUT',
    'OUTER',
    'OUTPUT',
    'OVER',
    'OVERLAPS',
    'OVERLAY',
    'OVERRIDING',
    'PAD',
    'PARAMETER',
    'PARAMETER_MODE',
    'PARAMETER_NAME',
    'PARAMETER_ORDINAL_POSITION',
    'PARAMETER_SPECIFIC_CATALOG',
    'PARAMETER_SPECIFIC_NAME',
    'PARAMETER_SPECIFIC_SCHEMA',
    'PARTIAL',
    'PARTITION',
    'PASCAL',
    'PASSTHROUGH',
    'PATH',
    'PERCENTILE_CONT',
    'PERCENTILE_DISC',
    'PERCENT_RANK',
    'PLACING',
    'PLAN',
    'PLI',
    'POSITION',
    'POWER',
    'PRECEDING',
    'PRECISION',
    'PREPARE',
    'PRESERVE',
    'PRIMARY',
    'PRIOR',
    'PRIVILEGES',
    'PROCEDURE',
    'PUBLIC',
    'QUARTER',
    'RANGE',
    'RANK',
    'RAW',
    'READ',
    'READS',
    'REAL',
    'RECURSIVE',
    'REF',
    'REFERENCES',
    'REFERENCING',
    'REGR_AVGX',
    'REGR_AVGY',
    'REGR_COUNT',
    'REGR_INTERCEPT',
    'REGR_R2',
    'REGR_SLOPE',
    'REGR_SXX',
    'REGR_SXY',
    'REGR_SYY',
    'RELATIVE',
    'RELEASE',
    'REPEATABLE',
    'RESET',
    'RESTART',
    'RESTRICT',
    'RESULT',
    'RETURN',
    'RETURNED_CARDINALITY',
    'RETURNED_LENGTH',
    'RETURNED_OCTET_LENGTH',
    'RETURNED_SQLSTATE',
    'RETURNS',
    'REVOKE',
    'RIGHT',
    'ROLE',
    'ROLLBACK',
    'ROLLUP',
    'ROUTINE',
    'ROUTINE_CATALOG',
    'ROUTINE_NAME',
    'ROUTINE_SCHEMA',
    'ROW',
    'ROWS',
    'ROW_COUNT',
    'ROW_NUMBER',
    'SAVEPOINT',
    'SCALE',
    'SCHEMA',
    'SCHEMA_NAME',
    'SCOPE',
    'SCOPE_CATALOGS',
    'SCOPE_NAME',
    'SCOPE_SCHEMA',
    'SCROLL',
    'SEARCH',
    'SECOND',
    'SECTION',
    'SECURITY',
    'SELECT',
    'SELF',
    'SENSITIVE',
    'SEQUENCE',
    'SERIALIZABLE',
    'SERVER',
    'SERVER_NAME',
    'SESSION',
    'SESSION_USER',
    'SET',
    'SETS',
    'SIMILAR',
    'SIMPLE',
    'SIZE',
    'SMALLINT',
    'SOME',
    'SOURCE',
    'SPACE',
    'SPECIFIC',
    'SPECIFICTYPE',
    'SPECIFIC_NAME',
    'SQL',
    'SQLEXCEPTION',
    'SQLSTATE',
    'SQLWARNING',
    'SQL_TSI_DAY',
    'SQL_TSI_FRAC_SECOND',
    'SQL_TSI_HOUR',
    'SQL_TSI_MICROSECOND',
    'SQL_TSI_MINUTE',
    'SQL_TSI_MONTH',
    'SQL_TSI_QUARTER',
    'SQL_TSI_SECOND',
    'SQL_TSI_WEEK',
    'SQL_TSI_YEAR',
    'SQRT',
    'START',
    'STATE',
    'STATEMENT',
    'STATIC',
    'STDDEV_POP',
    'STDDEV_SAMP',
    'STREAM',
    'STRING',
    'STRUCTURE',
    'STYLE',
    'SUBCLASS_ORIGIN',
    'SUBMULTISET',
    'SUBSTITUTE',
    'SUBSTRING',
    'SUM',
    'SYMMETRIC',
    'SYSTEM',
    'SYSTEM_USER',
    'TABLE',
    'TABLESAMPLE',
    'TABLE_NAME',
    'TEMPORARY',
    'THEN',
    'TIES',
    'TIME',
    'TIMESTAMP',
    'TIMESTAMPADD',
    'TIMESTAMPDIFF',
    'TIMEZONE_HOUR',
    'TIMEZONE_MINUTE',
    'TINYINT',
    'TO',
    'TOP_LEVEL_COUNT',
    'TRAILING',
    'TRANSACTION',
    'TRANSACTIONS_ACTIVE',
    'TRANSACTIONS_COMMITTED',
    'TRANSACTIONS_ROLLED_BACK',
    'TRANSFORM',
    'TRANSFORMS',
    'TRANSLATE',
    'TRANSLATION',
    'TREAT',
    'TRIGGER',
    'TRIGGER_CATALOG',
    'TRIGGER_NAME',
    'TRIGGER_SCHEMA',
    'TRIM',
    'TRUE',
    'TYPE',
    'UESCAPE',
    'UNBOUNDED',
    'UNCOMMITTED',
    'UNDER',
    'UNION',
    'UNIQUE',
    'UNKNOWN',
    'UNNAMED',
    'UNNEST',
    'UPDATE',
    'UPPER',
    'UPSERT',
    'USAGE',
    'USER',
    'USER_DEFINED_TYPE_CATALOG',
    'USER_DEFINED_TYPE_CODE',
    'USER_DEFINED_TYPE_NAME',
    'USER_DEFINED_TYPE_SCHEMA',
    'USING',
    'VALUE',
    'VALUES',
    'VARBINARY',
    'VARCHAR',
    'VARYING',
    'VAR_POP',
    'VAR_SAMP',
    'VERSION',
    'VIEW',
    'WEEK',
    'WHEN',
    'WHENEVER',
    'WHERE',
    'WIDTH_BUCKET',
    'WINDOW',
    'WITH',
    'WITHIN',
    'WITHOUT',
    'WORK',
    'WRAPPER',
    'WRITE',
    'XML',
    'YEAR',
    'ZONE',
]
