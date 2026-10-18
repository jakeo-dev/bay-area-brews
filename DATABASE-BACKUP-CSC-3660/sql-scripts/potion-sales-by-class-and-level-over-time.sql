SELECT date_trunc('hour', ledger_entries.created_at - INTERVAL '7 hours') AS pdt_time, ledger_entries.resource_key, ledger_entries.amount, carts.character_class, carts.level, transactions.day, transactions.hour
FROM ledger_entries
JOIN transactions ON ledger_entries.transaction_id = transactions.id
JOIN carts ON transactions.request_id = carts.id
WHERE amount < 0 AND resource_key ILIKE '%_0%'
ORDER BY pdt_time DESC
LIMIT 10000