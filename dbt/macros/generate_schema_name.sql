{#
    Emit custom schema names verbatim (e.g. `staging`, `marts`) instead of
    dbt's default `<target>_<custom>` concatenation, so the Cube.dev semantic
    layer can reference fully-qualified tables like `marts.fct_sales`.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
