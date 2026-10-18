select
  resource_key,
  date_trunc('hour', ledger_entries.created_at - INTERVAL '7 hours') AS pdt_time,
  amount,
  potion_mixtures.red_amount,
  potion_mixtures.green_amount,
  potion_mixtures.blue_amount,
  potion_mixtures.dark_amount,
  transactions.day, 
  transactions.hour
from
  ledger_entries
  join transactions on ledger_entries.transaction_id = transactions.id
  join potion_mixtures on ledger_entries.resource_key = potion_mixtures.sku
where
  resource_key ilike '%_0%'
  and amount < 0
order by
  pdt_time desc
limit 10000