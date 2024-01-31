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
from apm.resources import (
    AppConfigResource,
    ApplicationInfoResource,
    ApplyDatasourceResource,
    CreateApplicationResource,
    CreateApplicationSimpleResource,
    CreateOrUpdateBkdataFlowResource,
    DeleteAppConfigResource,
    DeleteApplicationResource,
    GetBkDataFlowDetailResource,
    ListApplicationResources,
    ListEsClusterInfoResource,
    OperateApmDataIdResource,
    QueryAppByHostInstanceResource,
    QueryAppByTraceResource,
    QueryBuiltinProfileDatasourceResource,
    QueryDiscoverRulesResource,
    QueryEndpointResource,
    QueryEsMappingResource,
    QueryEsResource,
    QueryEventResource,
    QueryFieldsResource,
    QueryHostInstanceResource,
    QueryLogRelationByIndexSetIdResource,
    QueryMetricDimensionsResource,
    QueryProfileServiceDetailResource,
    QueryRemoteServiceRelationResource,
    QueryRootEndpointResource,
    QueryServiceStatisticsListResource,
    QuerySpanDetailResource,
    QuerySpanListResource,
    QuerySpanOptionValues,
    QuerySpanResource,
    QuerySpanStatisticsListResource,
    QueryTopoInstanceResource,
    QueryTopoNodeResource,
    QueryTopoRelationResource,
    QueryTraceByHostInstanceResource,
    QueryTraceByIdsResource,
    QueryTraceDetailResource,
    QueryTraceListResource,
    QueryTraceOptionValues,
    ReleaseAppConfigResource,
    StartApplicationResource,
    StopApplicationResource,
    UpdateMetricFieldsResource,
)
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class MetaInfoViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("GET", ListEsClusterInfoResource, endpoint="list_es_cluster_info"),
    ]


class ApplicationViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", CreateApplicationSimpleResource, endpoint="create_application_simple"),
        ResourceRoute("POST", CreateApplicationResource, endpoint="create_application"),
        ResourceRoute("POST", DeleteApplicationResource, endpoint="delete_application"),
        ResourceRoute("POST", ApplyDatasourceResource, endpoint="apply_datasource"),
        ResourceRoute("GET", ListApplicationResources, endpoint="list_application"),
        ResourceRoute("GET", ApplicationInfoResource, endpoint="detail_application"),
        ResourceRoute("GET", StopApplicationResource, endpoint="stop_application"),
        ResourceRoute("GET", StartApplicationResource, endpoint="start_application"),
        ResourceRoute("GET", QueryRootEndpointResource, endpoint="query_root_endpoint"),
        ResourceRoute("GET", QueryFieldsResource, endpoint="query_fields"),
        ResourceRoute("POST", QueryEventResource, endpoint="query_event"),
        ResourceRoute("POST", QuerySpanResource, endpoint="query_span"),
        ResourceRoute("POST", QueryEndpointResource, endpoint="query_endpoint"),
        ResourceRoute("POST", QueryTraceListResource, endpoint="query_trace_list"),
        ResourceRoute("POST", QuerySpanListResource, endpoint="query_span_list"),
        ResourceRoute("POST", QuerySpanStatisticsListResource, endpoint="query_span_statistics"),
        ResourceRoute("POST", QueryServiceStatisticsListResource, endpoint="query_service_statistics"),
        ResourceRoute("POST", QueryTraceOptionValues, endpoint="query_trace_option_values"),
        ResourceRoute("POST", QuerySpanOptionValues, endpoint="query_span_option_values"),
        ResourceRoute("POST", QueryTraceByIdsResource, endpoint="query_trace_by_ids"),
        ResourceRoute("POST", QueryTraceByHostInstanceResource, endpoint="query_trace_by_host_instance"),
        ResourceRoute("POST", QueryAppByTraceResource, endpoint="query_app_by_trace"),
        ResourceRoute("POST", QueryTraceDetailResource, endpoint="query_trace_detail"),
        ResourceRoute("POST", QuerySpanDetailResource, endpoint="query_span_detail"),
        ResourceRoute("POST", UpdateMetricFieldsResource, endpoint="update_metric_fields"),
        ResourceRoute("POST", QueryEsResource, endpoint="query_es"),
        ResourceRoute("POST", QueryHostInstanceResource, endpoint="query_host_instance"),
        ResourceRoute("POST", QueryEsMappingResource, endpoint="query_es_mapping"),
        ResourceRoute("GET", AppConfigResource, endpoint="application_config"),
        ResourceRoute("POST", ReleaseAppConfigResource, endpoint="release_app_config"),
        ResourceRoute("POST", DeleteAppConfigResource, endpoint="delete_app_config"),
        ResourceRoute("POST", QueryAppByHostInstanceResource, endpoint="query_app_by_host_instance"),
        ResourceRoute("POST", QueryLogRelationByIndexSetIdResource, endpoint="query_log_relation_by_index_set_id"),
        ResourceRoute("GET", QueryMetricDimensionsResource, endpoint="query_metric_dimensions"),
        ResourceRoute("POST", QueryDiscoverRulesResource, endpoint="query_discover_rules"),
        ResourceRoute("GET", GetBkDataFlowDetailResource, endpoint="get_bkdata_flow"),
        ResourceRoute("POST", CreateOrUpdateBkdataFlowResource, endpoint="create_or_update_bkdata_flow"),
        ResourceRoute("POST", OperateApmDataIdResource, endpoint="operate_apm_dataid"),
    ]


class TopoViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", QueryTopoInstanceResource, endpoint="query_topo_instance"),
        ResourceRoute("POST", QueryRemoteServiceRelationResource, endpoint="query_remote_service_relation"),
        ResourceRoute("POST", QueryTopoRelationResource, endpoint="query_topo_relation"),
        ResourceRoute("GET", QueryTopoNodeResource, endpoint="query_topo_node"),
    ]


class ProfilingViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("GET", QueryBuiltinProfileDatasourceResource, endpoint="builtin_profile_datasource"),
        ResourceRoute("GET", QueryProfileServiceDetailResource, endpoint="services_detail"),
    ]
