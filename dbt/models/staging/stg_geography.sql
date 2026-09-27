-- Geography reference data, typed from the raw landing table.
select
    cast(geo_id    as integer) as geo_id,
    cast(country   as varchar) as country,
    cast(region    as varchar) as region,
    cast(continent as varchar) as continent
from {{ source('raw', 'raw_geography') }}
