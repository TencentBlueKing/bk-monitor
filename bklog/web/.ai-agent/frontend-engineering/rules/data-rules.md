# Data Access Patterns

覆盖 21 个模式：

- Repository
- DAO
- Data Mapper
- Active Record
- Unit of Work
- Identity Map
- Cache Aside
- Read Through
- Write Through
- Write Behind
- CQRS
- DTO
- Serializer
- Deserializer
- Normalization
- Denormalization
- Pagination
- Cursor
- Lazy Loading
- Prefetch
- Batching

## Rules

DATA-001
Data access MUST be separated from presentation when complexity requires it.

DATA-002
API response models MUST NOT automatically become UI models.

DATA-003
Repository MUST abstract meaningful data access behavior.

DATA-004
Do not create repositories for trivial one-line API wrappers.

DATA-005
Cache MUST define invalidation semantics.

DATA-006
Cache Aside MUST define source-of-truth behavior.

DATA-007
Lazy Loading MUST define loading and failure states.

DATA-008
Batching MUST preserve request semantics.

DATA-009
Pagination MUST define consistency behavior.

DATA-010
Normalization MUST only be introduced when duplicated entity state creates meaningful problems.
