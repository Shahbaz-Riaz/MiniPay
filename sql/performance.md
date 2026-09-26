-- 01_status_day.sql
SELECT
    DATE(created_at) AS transaction_day,
    status,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_value
FROM transactions
GROUP BY DATE(created_at), status
ORDER BY transaction_day, status;

-- 02_top_customers.sql
SELECT
    c.id,
    c.customer_ref,
    c.name,
    COUNT(t.id) AS successful_transaction_count,
    SUM(t.amount) AS total_value
FROM customers c
JOIN transactions t
    ON c.id = t.customer_id
WHERE t.status = 'SUCCESS'
GROUP BY c.id, c.customer_ref, c.name
ORDER BY total_value DESC
LIMIT 10;

-- 03_stuck_processing.sql
SELECT
    id,
    transaction_ref,
    customer_id,
    amount,
    status,
    created_at
FROM transactions
WHERE status = 'PROCESSING'
  AND created_at < CURRENT_TIMESTAMP - INTERVAL '15 minutes'
ORDER BY created_at;

-- 04_duplicate_refs.sql
SELECT
    transaction_ref,
    COUNT(*) AS occurrence_count
FROM transactions
GROUP BY transaction_ref
HAVING COUNT(*) > 1
ORDER BY occurrence_count DESC;

-- 05_daily_success_rate.sql
SELECT
    DATE(created_at) AS transaction_day,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE status = 'SUCCESS') / COUNT(*),
        2
    ) AS success_pct
FROM transactions
GROUP BY DATE(created_at)
ORDER BY transaction_day;

-- 06_reconciliation.sql
WITH successful_callbacks AS (
    SELECT DISTINCT transaction_id
    FROM callbacks
    WHERE callback_status = 'SUCCESS'
)
SELECT
    COUNT(*) AS successful_transaction_count,
    COALESCE(SUM(t.amount), 0) AS successful_transaction_value,
    COUNT(sc.transaction_id) AS callback_success_count,
    COALESCE(
        SUM(
            CASE
                WHEN sc.transaction_id IS NOT NULL
                THEN t.amount
                ELSE 0
            END
        ),
        0
    ) AS callback_success_value
FROM transactions t
LEFT JOIN successful_callbacks sc
    ON sc.transaction_id = t.id
WHERE t.status = 'SUCCESS';

-- 07_p95.sql
SELECT
    ROUND(
        AVG(EXTRACT(EPOCH FROM (completed_at - created_at)))::numeric,
        2
    ) AS avg_processing_seconds,
    ROUND(
        PERCENTILE_CONT(0.95) WITHIN GROUP (
            ORDER BY EXTRACT(EPOCH FROM (completed_at - created_at))
        )::numeric,
        2
    ) AS p95_processing_seconds
FROM transactions
WHERE completed_at IS NOT NULL
  AND completed_at >= created_at;


# PostgreSQL Query Optimization and Execution Plan

## 1. Query Investigated

The following query was selected for performance investigation because it filters transactions by status, joins them with customers, groups the results, and sorts them to find the top 10 customers by successful transaction value.

```sql
SELECT
    c.id,
    c.customer_ref,
    c.name,
    COUNT(t.id) AS successful_transaction_count,
    SUM(t.amount) AS total_value
FROM customers c
JOIN transactions t
    ON c.id = t.customer_id
WHERE t.status = 'SUCCESS'
GROUP BY c.id, c.customer_ref, c.name
ORDER BY total_value DESC
LIMIT 10;
```

## 2. Before Optimization

The query was first executed using:

```sql
EXPLAIN ANALYZE
SELECT
    c.id,
    c.customer_ref,
    c.name,
    COUNT(t.id) AS successful_transaction_count,
    SUM(t.amount) AS total_value
FROM customers c
JOIN transactions t
    ON c.id = t.customer_id
WHERE t.status = 'SUCCESS'
GROUP BY c.id, c.customer_ref, c.name
ORDER BY total_value DESC
LIMIT 10;
```

### Important observations

The execution plan showed:

```text
Seq Scan on transactions t
```

PostgreSQL scanned the transactions table sequentially and then filtered the rows using:

```text
Filter: ((status)::text = 'SUCCESS'::text)
```

The query processed:

* Total transactions: approximately 50,000
* Successful transactions: 41,036
* Rows removed by the filter: 8,964
* Customers: 1,000

The query used a `Hash Join` to join transactions with customers, followed by `HashAggregate` for grouping and a top-N sort for the final result.

### Before execution time

```text
Execution Time: 25.806 ms
```

## 3. Optimization Attempt

An index was created on the columns used for filtering and joining:

```sql
CREATE INDEX idx_transactions_status_customer
ON transactions(status, customer_id);
```

The same query was then executed again using `EXPLAIN ANALYZE`.

## 4. After Optimization

The execution plan still showed:

```text
Seq Scan on transactions t
```

This means PostgreSQL decided **not to use the newly created index**.

The second execution produced:

```text
Execution Time: 25.632 ms
```

A subsequent execution produced:

```text
Execution Time: 25.095 ms
```

## 5. Why Was the Index Not Used?

PostgreSQL uses a query planner to select the execution strategy it estimates to be the most efficient.

Creating an index does not force PostgreSQL to use it.

In this dataset, approximately 41,036 out of 50,000 transactions are successful:

```text
41,036 / 50,000 ≈ 82%
```

Therefore, the query needs approximately 82% of the transactions.

For a relatively small table where most rows match the filter, PostgreSQL can determine that scanning the table sequentially is cheaper than using an index to locate a large percentage of the table's rows.

The planner therefore continued using:

```text
Seq Scan on transactions
```

## 6. Before vs After

| Metric                  |          Before |           After |
| ----------------------- | --------------: | --------------: |
| Execution time          |       25.806 ms |       25.095 ms |
| Transactions            |         ~50,000 |         ~50,000 |
| Successful transactions |          41,036 |          41,036 |
| Rows filtered out       |           8,964 |           8,964 |
| Index used              |              No |              No |
| Transaction access      | Sequential scan | Sequential scan |

The difference between the measured execution times is approximately **0.711 ms**, which is not sufficient evidence of a meaningful performance improvement.

Small variations between executions are expected because of factors such as cache state and system activity.

## 7. Key PostgreSQL Concept

SQL normally specifies **what result is required**, rather than exactly **how PostgreSQL must retrieve that result**.

For example:

```sql
WHERE status = 'SUCCESS'
```

requires PostgreSQL to return successful transactions, but it does not require PostgreSQL to use an index.

The PostgreSQL query planner evaluates different possible execution strategies and chooses one based on estimated cost.

Therefore:

```text
SQL query
   ↓
Query Planner
   ↓
Cost estimation
   ↓
Selected execution plan
   ↓
Query result
```

In this case, the planner determined that a sequential scan was suitable for the current dataset.

## 8. Conclusion

An index on `(status, customer_id)` was added as a reasonable optimization based on the query's filtering and join conditions.

However, `EXPLAIN ANALYZE` showed that PostgreSQL continued using a sequential scan. The dataset is relatively small and approximately 82% of transactions match the `SUCCESS` condition, making a sequential scan a reasonable choice.

The optimization was therefore **not reported as a performance improvement**. The actual execution plans and measured execution times were used as evidence rather than assuming that an index would automatically improve performance.
