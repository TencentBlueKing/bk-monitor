## MODIFIED Requirements

### Requirement: Compatible date picker upgrade

The log frontend SHALL use @blueking/date-picker 4.0.0-beta.9 through its Vue 2 entry while preserving the TimeRange wrapper's public contract.

#### Scenario: Change display format

- WHEN the user switches the time format
- THEN the controlled picker format updates immediately, SEARCH_DEFAULT_TIME_FORMAT is persisted and format-change is emitted.

#### Scenario: Change timezone

- WHEN the user selects a timezone
- THEN the existing timezone-change event updates the parent's timezone and the picker receives that value.
- AND a date string without an offset is interpreted in the selected timezone, while an offset date or timestamp retains its absolute instant.

#### Scenario: Select time ranges

- WHEN the user selects a relative or absolute range
- THEN the existing change event and cache updates continue to work.
- AND the retrieval picker retains its maximum duration of 180 days.

#### Scenario: Optional smart parsing

- WHEN the picker opens without a host parser
- THEN smart parsing remains disabled.
