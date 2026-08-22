select
    customer_id,
    email as primary_email,
    updated_at
from {{ source('app', 'customers') }}
