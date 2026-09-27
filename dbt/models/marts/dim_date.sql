-- Date dimension derived from the distinct order dates.
-- Grain: one row per calendar date that appears in the fact.
with dates as (
    select distinct order_date as date
    from {{ ref('stg_orders') }}
)

select
    cast(strftime(date, '%Y%m%d') as integer)               as date_id,
    date,
    cast(extract(day   from date) as integer)               as day,
    cast(extract(month from date) as integer)               as month,
    strftime(date, '%B')                                    as month_name,
    cast(extract(quarter from date) as integer)             as quarter,
    cast(extract(year from date) as integer)                as year,
    extract(year from date) || '-Q' || extract(quarter from date) as quarter_label
from dates
