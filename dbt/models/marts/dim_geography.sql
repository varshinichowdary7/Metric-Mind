-- Geography dimension. Grain: one row per geo_id.
select
    geo_id,
    country,
    region,
    continent
from {{ ref('stg_geography') }}
