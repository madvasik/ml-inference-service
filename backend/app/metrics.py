from prometheus_client import Counter, Gauge, Histogram


prediction_requests_total = Counter(
    "prediction_requests_total",
    "Total number of prediction requests",
    ["status", "model_id"],
)

prediction_latency_seconds = Histogram(
    "prediction_latency_seconds",
    "Prediction execution latency in seconds",
    ["model_id"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

prediction_errors_total = Counter(
    "prediction_errors_total",
    "Total number of prediction errors",
    ["error_type"],
)

billing_transactions_total = Counter(
    "billing_transactions_total",
    "Total number of billing transactions",
    ["type"],
)

payments_total = Counter(
    "payments_total",
    "Total number of processed payments",
    ["status", "provider"],
)

prediction_discount_credits_total = Counter(
    "prediction_discount_credits_total",
    "Total number of discounted credits granted",
)

active_users = Gauge(
    "active_users",
    "Number of active users",
)

loyalty_users_total = Gauge(
    "loyalty_users_total",
    "Number of users in each loyalty tier",
    ["tier"],
)
