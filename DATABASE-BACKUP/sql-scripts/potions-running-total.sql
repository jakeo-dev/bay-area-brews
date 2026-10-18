SELECT amount, date_trunc('hour', created_at) AS rounded_time
FROM ledger_entries
WHERE resource_key ILIKE '%_0%'
GROUP BY amount, rounded_time
ORDER BY rounded_time
LIMIT 10000