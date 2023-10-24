from dataclasses import dataclass, field
from typing import List

# Q: 为什么不直接使用 protobuf 转换出来的类定义？
# A: 因为我们并不需要通过 protobuf 类转换到其他二进制，只需要一个能完整表达 pprof 数据结构的类定义即可。
#    而原始生成的类定义在使用上非常不方便。同时 pprof 的数据格式变更的非常少，手动维护类定义的成本很低。


@dataclass
class Profile:
    # The kind of events between sampled occurrences. e.g [ "cpu","cycles" ] or [
    # "heap","bytes" ]
    period_type: "ValueType"
    # The number of events between sampled occurrences.
    period: int
    # Index into the string table of the type of the preferred sample value. If
    # unset, clients should default to the last sample value.
    default_sample_type: str
    # A description of the samples associated with each Sample.value. For a cpu
    # profile this might be:   [["cpu","nanoseconds"]] or [["wall","seconds"]] or
    # [["syscall","count"]] For a heap profile, this might be:
    # [["allocations","count"], ["space","bytes"]], If one of the values
    # represents the number of events represented by the sample, by convention it
    # should be at index 0 and use sample_type.unit == "count".
    sample_types: List["ValueType"]
    # frames with Function.function_name fully matching the following regexp will
    # be dropped from the samples, along with their successors.
    drop_frames: str = ""
    # frames with Function.function_name fully matching the following regexp will
    # be kept, even if it matches drop_frames.
    keep_frames: str = ""
    # Time of collection (UTC) represented as nanoseconds past the epoch.
    time_nanos: int = -1
    # Duration of the profile, if a duration makes sense.
    duration_nanos: int = -1
    # The set of samples recorded in this profile.
    samples: List["Sample"] = field(default_factory=list)
    # Mapping from address ranges to the image/binary/library mapped into that
    # address range.  mapping[0] will be the main binary.
    mappings: List["Mapping"] = field(default_factory=list)
    # Locations referenced by samples.
    locations: List["Location"] = field(default_factory=list)
    # Functions referenced by locations.
    functions: List["Function"] = field(default_factory=list)
    # Free-form text associated with the profile. The text is displayed as is to
    # the user by the tools that read profiles (e.g. by pprof). This field should
    # not be used to store any machine-readable information, it is only for
    # human-friendly content. The profile must stay functional if this field is
    # cleaned.
    comments: List[int] = field(default_factory=list)


@dataclass
class ValueType:
    """ValueType describes the semantics and measurement units of a value."""

    type: str
    unit: str


@dataclass
class Sample:
    """
    Each Sample records values encountered in some program context. The program
    context is typically a stack trace, perhaps augmented with auxiliary
    information like the thread-id, some indicator of a higher level request
    being handled etc.
    """

    # The ids recorded here correspond to a Profile.location.id. The leaf is at
    # location_id[0].
    locations: List["Location"] = field(default_factory=list)
    # The type and unit of each value is defined by the corresponding entry in
    # Profile.sample_type. All samples must have the same number of values, the
    # same as the length of Profile.sample_type. When aggregating multiple
    # samples into a single sample, the result has a list of values that is the
    # element-wise sum of the lists of the originals.
    values: List[int] = field(default_factory=list)
    # label includes additional context for this sample. It can include things
    # like a thread id, allocation size, etc. NOTE: While possible, having
    # multiple values for the same label key is strongly discouraged and should
    # never be used. Most tools (e.g. pprof) do not have good (or any) support
    # for multi-value labels. And an even more discouraged case is having a
    # string label and a numeric label of the same name on a sample.  Again,
    # possible to express, but should not be used.
    labels: List["Label"] = field(default_factory=list)


@dataclass
class Label:
    # Index into string table. An annotation for a sample (e.g.
    # "allocation_size") with an associated value. Keys with "pprof::" prefix are
    # reserved for internal use by pprof.
    key: str
    # At most one of the following must be present
    val: int
    num: int
    # Should only be present when num is present. Specifies the units of num. Use
    # arbitrary string (for example, "requests") as a custom count unit. If no
    # unit is specified, consumer may apply heuristic to deduce the unit.
    # Consumers may also  interpret units like "bytes" and "kilobytes" as memory
    # units and units like "seconds" and "nanoseconds" as time units, and apply
    # appropriate unit conversions to these.
    num_unit: str


@dataclass
class Mapping:
    # Unique nonzero id for the mapping.
    id: int
    # Address at which the binary (or DLL) is loaded into memory.
    memory_start: int
    # The limit of the address range occupied by this mapping.
    memory_limit: int
    # Offset in the binary that corresponds to the first mapped address.
    file_offset: int
    # The object this entry is loaded from.  This can be a filename on disk for
    # the main binary and shared libraries, or virtual abstractions like
    # "[vdso]".
    filename: str
    # A string that uniquely identifies a particular program version with high
    # probability. E.g., for binaries generated by GNU tools, it could be the
    # contents of the .note.gnu.build-id field.
    build_id: str
    # The following fields indicate the resolution of symbolic info.
    has_functions: bool
    has_filenames: bool
    has_line_numbers: bool
    has_inline_frames: bool


@dataclass
class Location:
    """Describes function and line table debug information."""

    # Unique nonzero id for the location.  A profile could use instruction
    # addresses or any integer sequence as ids.
    id: int
    # The id of the corresponding profile.Mapping for this location. It can be
    # unset if the mapping is unknown or not applicable for this profile type.
    mapping: Mapping
    # The instruction address for this location, if available.  It should be
    # within [Mapping.memory_start...Mapping.memory_limit] for the corresponding
    # mapping. A non-leaf address may be in the middle of a call instruction. It
    # is up to display tools to find the beginning of the instruction if
    # necessary.
    address: int
    # Provides an indication that multiple symbols map to this location's
    # address, for example due to identical code folding by the linker. In that
    # case the line information above represents one of the multiple symbols.
    # This field must be recomputed when the symbolization state of the profile
    # changes.
    is_folded: bool
    # Multiple line indicates this location has inlined functions, where the last
    # entry represents the caller into which the preceding entries were inlined.
    # E.g., if memcpy() is inlined into printf:    line[0].function_name ==
    # "memcpy"    line[1].function_name == "printf"
    lines: List["Line"] = field(default_factory=list)


@dataclass
class Line:
    # The id of the corresponding profile.Function for this line.
    function: "Function"
    # Line number in source code.
    line: int


@dataclass
class Function:
    # Unique nonzero id for the function.
    id: int
    # Name of the function, in human-readable form if available.
    name: str
    # Name of the function, as identified by the system. For instance, it can be
    # a C++ mangled name.
    system_name: str
    # Source file containing the function.
    filename: str
    # Line number in source file.
    start_line: int
