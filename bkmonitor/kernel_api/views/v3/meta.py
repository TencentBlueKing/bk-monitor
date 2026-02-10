"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.views.renderers import MonitorJSONRenderer
from core.drf_resource import resource as r
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from metadata import resources as resource

RENDER_CLASSES = [MonitorJSONRenderer]


class MetaViewSet(ResourceViewSet):
    renderer_classes = RENDER_CLASSES


class CreateDataIDViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CreateDataIDResource)]


class ModifyDataIDViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ModifyDataSource)]


class StopOrEnableDatasourceViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.StopOrEnableDatasource)]


class ResultTableViewSet(MetaViewSet):
    resource_routes = [
        ResourceRoute("POST", resource.CreateResultTableResource),
        ResourceRoute("GET", resource.ListResultTableResource),
    ]


class ModifyResultTableViewSet(MetaViewSet):
    resource_routes = [
        ResourceRoute("POST", resource.ModifyResultTableResource),
    ]


class AccessBkDataByResultTableViewSet(MetaViewSet):
    resource_routes = [
        ResourceRoute("POST", resource.AccessBkDataByResultTableResource),
    ]


class IsDataLabelExistViewSet(MetaViewSet):
    resource_routes = [
        ResourceRoute("GET", resource.IsDataLabelExistResource),
    ]


class CreateDownSampleDataFlowViewSet(MetaViewSet):
    resource_routes = [
        ResourceRoute("POST", resource.CreateDownSampleDataFlowResource),
    ]


class GetDataIDViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryDataSourceResource)]


class QueryDataSourceBySpaceUidViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.QueryDataSourceBySpaceUidResource)]


class GetResultTableViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryResultTableSourceResource)]


class UpgradeResultTableViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.UpgradeResultTableResource)]


class FullCmdbNodeInfoViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.FullCmdbNodeInfoResource)]


class CreateResultTableMetricSplitViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CreateResultTableMetricSplitResource)]


class CleanResultTableMetricSplitViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CleanResultTableMetricSplitResource)]


class LabelViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.LabelResource)]


class GetResultTableStorageViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.GetResultTableStorageResult)]


class CreateClusterInfoViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CreateClusterInfoResource)]


class ModifyClusterInfoViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ModifyClusterInfoResource)]


class DeleteClusterInfoViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.DeleteClusterInfoResource)]


class GetClusterInfoViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryClusterInfoResource)]


class QueryEventGroupViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryEventGroupResource)]


class CreateEventGroupViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CreateEventGroupResource)]


class ModifyEventGroupViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ModifyEventGroupResource)]


class DeleteEventGroupViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.DeleteEventGroupResource)]


class GetEventGroupViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.GetEventGroupResource)]


class GetLogGroupViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.GetLogGroupResource)]


class QueryLogGroupViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryLogGroupResource)]


class CreateLogGroupViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CreateLogGroupResource)]


class ModifyLogGroupViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ModifyLogGroupResource)]


class DeleteLogGroupViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.DeleteLogGroupResource)]


class GetTimeSeriesMetricsViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.GetTimeSeriesMetricsResource)]


class CreateTimeSeriesGroupViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CreateTimeSeriesGroupResource)]


class ModifyTimeSeriesGroupViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ModifyTimeSeriesGroupResource)]


class DeleteTimeSeriesGroupViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.DeleteTimeSeriesGroupResource)]


class GetTimeSeriesGroupViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.GetTimeSeriesGroupResource)]


class QueryTimeSeriesGroupViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryTimeSeriesGroupResource)]


class QueryTagValuesViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryTagValuesResource)]


class ListTransferClusterViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.ListTransferClusterResource)]


class CheckOrCreateKafkaStorageViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CheckOrCreateKafkaStorageResource)]


class RegisterBCSClusterViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.RegisterBCSClusterResource)]


class ModifyBCSResourceInfoViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ModifyBCSResourceInfoResource)]


class ListBCSResourceInfoViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ListBCSResourceInfoResource)]


class ListBCSClusterInfoViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.ListBCSClusterInfoResource)]


class ListBCSClusterInfoByBizViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.ListBCSClusterInfoByBizResource)]


class ApplyYamlToBCSClusterViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ApplyYamlToBCSClusterResource)]


class QueryBCSMetricsViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryBCSMetricsResource)]


class CreateEsSnapshotRepositoryViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CreateEsSnapshotRepositoryResource)]


class ModifyEsSnapshotRepositoryViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ModifyEsSnapshotRepositoryResource)]


class DeleteEsSnapshotRepositoryViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.DeleteEsSnapshotRepositoryResource)]


class VerifyEsSnapshotRepositoryViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.VerifyEsSnapshotRepositoryResource)]


class EsSnapshotRepositoryViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.EsSnapshotRepositoryResource)]


class ListEsSnapshotRepositoryViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ListEsSnapshotRepositoryResource)]


class CreateResultTableSnapshotViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CreateResultTableSnapshotResource)]


class ModifyResultTableSnapshotViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ModifyResultTableSnapshotResource)]


class DeleteResultTableSnapshotViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.DeleteResultTableSnapshotResource)]


class RetryResultTableSnapshotViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.RetryResultTableSnapshotResource)]


class ListResultTableSnapshotViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ListResultTableSnapshotResource)]


class ListResultTableSnapshotIndicesViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ListResultTableSnapshotIndicesResource)]


class GetResultTableSnapshotStateViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.GetResultTableSnapshotStateResource)]


class GetResultTableSnapshotRecentStateViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.GetResultTableSnapshotRecentStateResource)]


class RestoreResultTableSnapshotViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.RestoreResultTableSnapshotResource)]


class ModifyRestoreResultTableSnapshotViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ModifyRestoreResultTableSnapshotResource)]


class DeleteRestoreResultTableSnapshotViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.DeleteRestoreResultTableSnapshotResource)]


class RetryRestoreResultTableSnapshotViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.RetryRestoreResultTableSnapshotResource)]


class ListRestoreResultTableSnapshotViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ListRestoreResultTableSnapshotResource)]


class GetRestoreResultTableSnapshotStateViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.GetRestoreResultTableSnapshotStateResource)]


class GetRestoreResultTableSnapshotIndicesViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.GetRestoreResultTableSnapshotIndicesResource)]


class ModifyDatasourceResultTable(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ModifyDatasourceResultTable)]


class GetOrCreateAgentEventDataId(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.GetOrCreateAgentEventDataIdResource)]


class EsRouteViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.EsRouteResource)]


class KafkaTailViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.KafkaTailResource)]


class ListSpaceTypesViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.ListSpaceTypesResource)]


class ListSpacesViewSet(MetaViewSet):
    resource_routes = [
        ResourceRoute("GET", resource.ListSpacesResource),
        ResourceRoute("GET", r.commons.list_spaces, endpoint="by_user"),
    ]


class GetSpaceDetailViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.GetSpaceDetailResource)]


class GetClustersBySpaceUidViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.GetClustersBySpaceUidResource)]


class GetBizRelatedBkciSpacesViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.GetBizRelatedBkciSpacesResource)]


class GetNegativeSpaceIdRelatedInfoViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.GetNegativeSpaceIdRelatedInfo)]


class CreateSpaceViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CreateSpaceResource)]


class UpdateSpaceViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.UpdateSpaceResource)]


class MergeSpaceViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.MergeSpaceResource)]


class DisableSpaceViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.DisableSpaceResource)]


class ListStickySpacesViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.ListStickySpacesResource)]


class StickSpaceViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.StickSpaceResource)]


class RefreshMetricForKihanViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.RefreshMetricForKihan)]


class ListClustersViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.ListClusters)]


class GetStorageClusterDetailViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.GetStorageClusterDetail)]


class RegisterClusterViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.RegisterCluster)]


class UpdateRegisteredClusterViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.UpdateRegisteredCluster)]


class QueryDataSourceViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryDataSourceResource)]


class QueryDataLinkInfoViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryDataLinkInfoResource)]


class QueryDataLinkMetadataViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryDataLinkMetadataResource)]


class SpaceDataLinkMetaReportViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.SpaceDataLinkMetaReport)]


class IntelligentDiagnosisMetadataViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.IntelligentDiagnosisMetadataResource)]


class QueryDataIdsByBizIdViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryDataIdsByBizIdResource)]


class GetBCSClusterRelatedDataLinkViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.GetBCSClusterRelatedDataLinkResource)]


class QueryResultTableStorageDetailViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryResultTableStorageDetailResource)]


class NotifyEsDataLinkAdaptNanoViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.NotifyEsDataLinkAdaptNano)]


class CreateVmClusterViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CreateVmCluster)]


class QueryVmDatalinkViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryVmDatalink)]


class QueryBcsClusterVmTableIdsViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryBcsClusterVmTableIds)]


class SwitchKafkaClusterViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.SwitchKafkaCluster)]


class NotifyDataLinkVmChangeViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.NotifyDataLinkVmChange)]


class QueryMetaInfoByVmrtViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryMetaInfoByVmrt)]


class ModifyClusterByVmrtsViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ModifyClusterByVmrts)]


class QueryVmRtBySpaceViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.QueryVmRtBySpace)]


class CreateEsRouterViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CreateEsRouter)]


class UpdateEsRouterViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.UpdateEsRouter)]


class CreateDorisRouterViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CreateDorisRouter)]


class UpdateDorisRouterViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.UpdateDorisRouter)]


class AddBkDataTableIdsViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.AddBkDataTableIdsResource)]


class CreateOrUpdateEsRouterViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CreateOrUpdateLogRouter)]


class CreateOrUpdateLogRouterViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CreateOrUpdateLogRouter)]


class BulkCreateOrUpdateLogRouterViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.BulkCreateOrUpdateLogRouter)]


class CleanLogRouterViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.CleanLogRouter)]


class ModifyDataIdSourceViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.ModifyDataIdSource)]


class GetDataLabelsMapViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("POST", resource.GetDataLabelsMapResource)]


class SyncBkBaseRtMetaByBizIdViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.SyncBkBaseRtMetaByBizIdResource)]


class ListBkBaseRtInfoByBizIdViewSet(MetaViewSet):
    resource_routes = [ResourceRoute("GET", resource.ListBkBaseRtInfoByBizIdResource)]
