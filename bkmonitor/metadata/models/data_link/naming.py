"""Allocate component identities once, recovering saved references on every retry."""

from django.db import transaction

from metadata.config import DATABASE_CONNECTION_NAME
from metadata.models.data_link import utils
from metadata.models.data_link.component_reuse import ExistingComponentContext
from metadata.models.data_link.constants import DataLinkKind
from metadata.models.data_link.data_link_configs import (
    DataBusConfig,
    ResultTableConfig,
    SurrealDBBindingConfig,
    VMStorageBindingConfig,
)
from metadata.models.vm.record import AccessVMRecord


def resolve_component_names(datalink, *, bk_biz_id, data_source, table_id, scene, context=None, graph=False):
    """Return persisted RT/binding/databus names, including partially created chains.

    The local transaction ends before the caller applies anything to BKBase. Locking
    the DataLink serializes both direct compose calls and the normal apply entry.
    """
    with transaction.atomic(using=DATABASE_CONNECTION_NAME):
        type(datalink).objects.select_for_update().get(pk=datalink.pk)
        context = context or ExistingComponentContext.from_datalink(datalink)
        binding_model = SurrealDBBindingConfig if graph else VMStorageBindingConfig
        sink_kind = DataLinkKind.SURREALDBBINDING.value if graph else DataLinkKind.VMSTORAGEBINDING.value
        rt = context.claim(ResultTableConfig, lambda c: (c.data_type == "graph") == graph, require_unique=True)
        binding = context.claim(binding_model, lambda c: True, require_unique=True)
        databus = context.claim(
            DataBusConfig,
            lambda c: any(s.startswith(f"{DataLinkKind.SURREALDBBINDING.value}:") for s in c.sink_names) == graph,
            require_unique=True,
        )
        data_id_name = (databus.data_id_name if databus else "") or utils.get_registered_bkdata_data_id_name(
            data_source, namespace=datalink.namespace
        )
        scope = {"bk_tenant_id": datalink.bk_tenant_id, "namespace": datalink.namespace}
        common = {**scope, "data_link_name": datalink.data_link_name, "bk_biz_id": bk_biz_id}

        def restore(model, name, **fields):
            existing = model.objects.filter(**scope, name=name).first()
            if existing is not None:
                if existing.data_link_name != datalink.data_link_name:
                    raise ValueError(f"{model.__name__}({name}) belongs to another DataLink")
                return existing
            return model.objects.create(name=name, **common, **fields)

        # A DataBus sink is an identity even if the corresponding binding was lost.
        binding_names = (
            {s.split(":", 1)[1] for s in databus.sink_names if s.startswith(f"{sink_kind}:")} if databus else set()
        )
        if len(binding_names) > 1:
            raise ValueError(f"ambiguous {sink_kind} references: {sorted(binding_names)}")
        saved_binding_name = next(iter(binding_names), "")
        if binding and saved_binding_name and binding.name != saved_binding_name:
            if binding_model.objects.filter(**scope, name=saved_binding_name).exists():
                raise ValueError("DataBus sink conflicts with the existing binding")
        saved_rt_name = binding.bkbase_result_table_name if binding else ""
        if rt and saved_rt_name and rt.name != saved_rt_name:
            if ResultTableConfig.objects.filter(**scope, name=saved_rt_name).exists():
                raise ValueError("binding reference conflicts with the existing ResultTable")
        if not rt:
            if not saved_rt_name and not graph:
                record = (
                    AccessVMRecord.objects.filter(
                        bk_tenant_id=datalink.bk_tenant_id,
                        result_table_id=table_id,
                    )
                    .exclude(vm_result_table_id="")
                    .last()
                )
                if record:
                    saved_rt_name = datalink._strip_bkbase_biz_prefix(record.vm_result_table_id)
            rt_fields = {"table_id": table_id, "data_type": "graph" if graph else "metric"}
            if saved_rt_name:
                rt = restore(ResultTableConfig, saved_rt_name, **rt_fields)
            else:
                rt = utils.create_resource_with_random_name(
                    ResultTableConfig,
                    scene,
                    data_source.bk_data_id,
                    **common,
                    **rt_fields,
                )
        if not binding:
            if saved_binding_name:
                binding = restore(
                    binding_model, saved_binding_name, table_id=table_id, bkbase_result_table_name=rt.name
                )
            elif binding_model.objects.filter(**scope, name=rt.name).exists():
                binding = utils.create_resource_with_random_name(
                    binding_model,
                    scene,
                    data_source.bk_data_id,
                    **common,
                    table_id=table_id,
                    bkbase_result_table_name=rt.name,
                )
            else:
                binding = restore(binding_model, rt.name, table_id=table_id, bkbase_result_table_name=rt.name)
        if not databus:
            fields = {
                "data_id_name": data_id_name,
                "bk_data_id": data_source.bk_data_id,
                "sink_names": [f"{sink_kind}:{binding.name}"],
            }
            if DataBusConfig.objects.filter(**scope, name=rt.name).exists():
                databus = utils.create_resource_with_random_name(
                    DataBusConfig,
                    scene,
                    data_source.bk_data_id,
                    **common,
                    **fields,
                )
            else:
                databus = restore(DataBusConfig, rt.name, **fields)
        return rt.name, binding.name, databus.name, data_id_name
