"""Product metadata derived from the authoritative original V3 ResourceEnum."""
from bkmonitor.iam.resource import ResourceEnum
from iam_engine.schema.definitions import ResourceTypeDef


def _definition(resource, name_en):
    return ResourceTypeDef(
        id=resource.id,
        name=resource.name,
        ancestor=resource.parent_resource.id if resource.parent_resource else "",
        extensions={"v3": {
            "system_id": resource.system_id,
            "selection_mode": resource.selection_mode,
            "name_en": name_en,
            "related_instance_selections": resource.related_instance_selections,
        }},
    )


class ResourceTypes:
    SPACE = _definition(ResourceEnum.BUSINESS, "Space")
    APM_APPLICATION = _definition(ResourceEnum.APM_APPLICATION, "APM Application")
    GRAFANA_DASHBOARD = _definition(ResourceEnum.GRAFANA_DASHBOARD, "Grafana Dashboard")
    RUM_APPLICATION = _definition(ResourceEnum.RUM_APPLICATION, "RUM Application")
