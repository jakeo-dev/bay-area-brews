SELECT transactions.hour, transactions.hour,
COUNT(*) AS total
FROM ledger_entries
JOIN transactions ON ledger_entries.transaction_id = transactions.id
JOIN carts ON transactions.request_id = carts.id
WHERE amount < 0 AND resource_key ILIKE '%_0%'
AND level <= 10
GROUP BY hour
ORDER BY hour ASC