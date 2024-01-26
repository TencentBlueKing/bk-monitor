from betterproto import _preprocess_single  # noqa
from betterproto import _serialize_single  # noqa
from betterproto import PACKED_TYPES, TYPE_BYTES, Message


def mocked_bytes(self) -> bytes:
    """
    Get the binary encoded Protobuf representation of this message instance.
    """
    output = bytearray()
    for field_name, meta in self._betterproto.meta_by_field_name.items():
        value = getattr(self, field_name)

        if value is None:
            # Optional items should be skipped. This is used for the Google
            # wrapper types and proto3 field presence/optional fields.
            continue

        # Being selected in a a group means this field is the one that is
        # currently set in a `oneof` group, so it must be serialized even
        # if the value is the default zero value.
        #
        # Note that proto3 field presence/optional fields are put in a
        # synthetic single-item oneof by protoc, which helps us ensure we
        # send the value even if the value is the default zero value.
        selected_in_group = meta.group and self._group_current[meta.group] == field_name

        # Empty messages can still be sent on the wire if they were
        # set (or received empty).
        serialize_empty = isinstance(value, Message) and value._serialized_on_wire

        include_default_value_for_oneof = self._include_default_value_for_oneof(field_name=field_name, meta=meta)

        if value == self._get_field_default(field_name) and not (
            selected_in_group or serialize_empty or include_default_value_for_oneof
        ):
            # Default (zero) values are not serialized. Two exceptions are
            # if this is the selected oneof item or if we know we have to
            # serialize an empty message (i.e. zero value was explicitly
            # set by the user).
            continue

        if isinstance(value, list):
            if meta.proto_type in PACKED_TYPES:
                # Packed lists look like a length-delimited field. First,
                # preprocess/encode each value into a buffer and then
                # treat it like a field of raw bytes.
                buf = bytearray()
                for item in value:
                    buf += _preprocess_single(meta.proto_type, "", item)
                output += _serialize_single(meta.number, TYPE_BYTES, buf)
            else:
                for item in value:
                    output += (
                        _serialize_single(
                            meta.number,
                            meta.proto_type,
                            item,
                            wraps=meta.wraps or "",
                            serialize_empty=True,
                        )
                        # if it's an empty message it still needs to be represented
                        # as an item in the repeated list
                        or b"\n\x00"
                    )

        elif isinstance(value, dict):
            for k, v in value.items():
                assert meta.map_types
                sk = _serialize_single(1, meta.map_types[0], k)
                sv = _serialize_single(2, meta.map_types[1], v)
                output += _serialize_single(meta.number, meta.proto_type, sk + sv)
        else:
            # If we have an empty string and we're including the default value for
            # a oneof, make sure we serialize it. This ensures that the byte string
            # output isn't simply an empty string. This also ensures that round trip
            # serialization will keep `which_one_of` calls consistent.
            if isinstance(value, str) and value == "" and include_default_value_for_oneof:
                serialize_empty = True

            output += _serialize_single(
                meta.number,
                meta.proto_type,
                value,
                serialize_empty=serialize_empty or bool(selected_in_group),
                wraps=meta.wraps or "",
            )

    output += self._unknown_fields
    return bytes(output)


Message.__bytes__ = mocked_bytes
