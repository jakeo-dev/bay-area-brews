SELECT COALESCE(SUM(amount), 0) AS sum, resource_key, resource_type
FROM ledger_entries
GROUP BY resource_key, resource_type
ORDER BY sum DESC