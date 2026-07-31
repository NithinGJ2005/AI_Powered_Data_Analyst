"""QA Phase 1-8 offline test runner with correct st mock and correct production signatures."""
import sys, os
import unittest.mock as mock

# Patch streamlit with passthrough decorators
st_mock = mock.MagicMock()
st_mock.cache_data = lambda func=None, **kw: (func if func else lambda f: f)
st_mock.cache_resource = lambda func=None, **kw: (func if func else lambda f: f)
sys.modules['streamlit'] = st_mock
sys.path.insert(0, os.getcwd())

import pandas as pd
import numpy as np

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

all_results = []
bugs = []

def record(phase, test, status, note=""):
    all_results.append((phase, test, status, note))
    sym = "OK" if status == PASS else ("WW" if status == WARN else "XX")
    print(f"  [{sym}] [{phase}] {test}: {note[:110]}")

def record_bug(phase, feature, severity, desc, file_, fix):
    bugs.append(dict(phase=phase, feature=feature, severity=severity, desc=desc, file=file_, fix=fix))
    print(f"  [BUG-{severity}] {phase}/{feature}: {desc[:90]}")

# ═══════════════════════ PHASE 1: Dataset Loading ═══════════════════════
print("\n=== PHASE 1: Dataset Loading ===")
from modules.loader import load_csv_from_bytes

datasets_raw = {}
dataset_paths = {
    "superstore_sales.csv":       "datasets/superstore_sales.csv",
    "customers.csv":              "datasets/customers.csv",
    "orders.csv":                 "datasets/orders.csv",
    "stock_market.csv":           "datasets/stock_market.csv",
    "financial_transactions.csv": "datasets/financial_transactions.csv",
}

for name, path in dataset_paths.items():
    with open(path, "rb") as f:
        raw = f.read()
    res = load_csv_from_bytes(raw, name)
    err = res.get("error") if isinstance(res, dict) else "Not a dict"
    if err:
        record("P1", "Load " + name, FAIL, str(err))
    else:
        datasets_raw[name] = res
        note = "shape=" + str(res["shape"]) + " cols=" + str(res["columns"])
        record("P1", "Load " + name, PASS, note)

e = load_csv_from_bytes(b"col1,col2\n", "empty.csv")
record("P1", "Empty CSV rejected", PASS if (isinstance(e, dict) and e.get("error")) else FAIL,
       str(e.get("error", "Not rejected") if isinstance(e, dict) else e))

d = load_csv_from_bytes(b"a,a,b\n1,2,3\n", "dup_cols.csv")
record("P1", "Duplicate cols rejected", PASS if (isinstance(d, dict) and d.get("error")) else FAIL,
       str(d.get("error", "Not rejected") if isinstance(d, dict) else d))

try:
    inv = load_csv_from_bytes(b"\xff\xfe garbage binary", "invalid.bin")
    record("P1", "Binary input handled", PASS if (isinstance(inv, dict) and inv.get("error")) else WARN, str(inv)[:80])
except Exception as ex:
    record("P1", "Binary input handled", FAIL, str(ex)[:80])
    record_bug("P1", "Error handling", "MEDIUM", "Unhandled exception on binary: " + str(ex), "modules/loader.py", "Catch all exceptions")

# ═══════════════════════ PHASE 2: SQL Engine ═══════════════════════
print("\n=== PHASE 2: SQL Engine ===")
from services.sql_service import SQLService
data_ctx = {name: res["df"] for name, res in datasets_raw.items()}

sql_tests = [
    ("Simple SELECT",         "SELECT * FROM superstore_sales LIMIT 3",                                   "df"),
    ("COUNT aggregation",     "SELECT COUNT(*) as cnt FROM superstore_sales",                             "df"),
    ("GROUP BY Region",       "SELECT Region, SUM(Sales) as total FROM superstore_sales GROUP BY Region","df"),
    ("ORDER BY DESC",         "SELECT Customer, Sales FROM superstore_sales ORDER BY Sales DESC",          "df"),
    ("HAVING clause",         "SELECT Region, SUM(Sales) as s FROM superstore_sales GROUP BY Region HAVING SUM(Sales) > 0", "df"),
    ("JOIN customers+orders", "SELECT o.OrderID, c.CustomerName FROM orders o JOIN customers c ON o.CustomerID = c.CustomerID", "df"),
    ("Date filter stock",     "SELECT * FROM stock_market WHERE Date > '2026-03-01'",                     "df"),
    ("Top N products",        "SELECT Product, Sales FROM superstore_sales ORDER BY Sales DESC LIMIT 3",  "df"),
    ("AVG aggregation",       "SELECT Category, AVG(Profit) as avg_p FROM superstore_sales GROUP BY Category", "df"),
    ("Financial filter",      "SELECT * FROM financial_transactions WHERE Amount > 100",                  "df"),
    ("Empty SQL",             "",                                                                          "none"),
    ("Block DROP",            "DROP TABLE superstore_sales",                                               "block"),
    ("Block INSERT",          "INSERT INTO superstore_sales VALUES (1)",                                   "block"),
    ("Block UPDATE",          "UPDATE superstore_sales SET Sales=0",                                       "block"),
    ("Block DELETE",          "DELETE FROM superstore_sales",                                              "block"),
    ("Block comment",         "SELECT * FROM superstore_sales -- bad",                                     "block"),
    ("Block multi-stmt",      "SELECT 1; SELECT 2",                                                        "block"),
    ("Block EXEC",            "EXEC xp_cmdshell('dir')",                                                   "block"),
    ("Block TRUNCATE",        "TRUNCATE TABLE superstore_sales",                                           "block"),
]

for label, sql, expect in sql_tests:
    try:
        result = SQLService.execute_sql_query(sql, data_ctx)
        if expect == "df":
            if isinstance(result, pd.DataFrame):
                record("P2", label, PASS, "rows=" + str(len(result)))
            elif isinstance(result, str):
                record("P2", label, FAIL, result[:90])
                record_bug("P2", "SQL Execution", "HIGH", label + " => " + result[:60], "services/sql_service.py", "Check table registration")
            else:
                record("P2", label, WARN, "type=" + str(type(result)))
        elif expect == "block":
            if isinstance(result, str) and ("rejected" in result.lower() or "blocked" in result.lower() or chr(9888) in result):
                record("P2", label, PASS, "Blocked correctly")
            elif isinstance(result, pd.DataFrame):
                record("P2", label, FAIL, "SECURITY BYPASS - dangerous SQL executed!")
                record_bug("P2", "SQL Security", "CRITICAL", label + " not blocked", "services/sql_service.py", "Fix blocklist")
            else:
                record("P2", label, WARN, "Unexpected: " + str(result)[:60])
        elif expect == "none":
            record("P2", label, PASS if result is None else WARN, "None returned: " + str(result is None))
    except Exception as ex:
        record("P2", label, FAIL, str(ex)[:90])

# ═══════════════════════ PHASE 3: Anomaly Detection ═══════════════════════
print("\n=== PHASE 3: Anomaly Detection ===")
from services.anomaly_service import AnomalyService

for ds_name, res in datasets_raw.items():
    df = res["df"]
    for method in ["Isolation Forest", "Z-score", "IQR"]:
        try:
            updated_df, anomalies_df = AnomalyService.detect_anomalies(df, method)
            cols_ok = all(c in updated_df.columns for c in ["Anomaly", "AnomalyScore", "Explanation"])
            record("P3", ds_name + " [" + method + "]",
                   PASS if cols_ok else FAIL,
                   "anomalies=" + str(len(anomalies_df)) + " cols_ok=" + str(cols_ok))
            if not cols_ok:
                record_bug("P3", "Anomaly", "MEDIUM", "Missing output columns for " + ds_name, "services/anomaly_service.py", "Ensure all 3 columns always present")
        except Exception as ex:
            record("P3", ds_name + " [" + method + "]", FAIL, str(ex)[:90])
            record_bug("P3", "Anomaly", "HIGH", str(ex)[:80], "services/anomaly_service.py", "Fix exception")

# ═══════════════════════ PHASE 4: Forecasting ═══════════════════════
print("\n=== PHASE 4: Forecasting ===")
from services.forecast_service import ForecastService

for ds_name, res in datasets_raw.items():
    df = res["df"]
    try:
        date_cols    = ForecastService.detect_datetime_columns(df)
        numeric_cols = ForecastService.detect_numeric_columns(df, date_cols)
        record("P4", ds_name + " date detect",    PASS if date_cols else WARN,    "date_cols=" + str(date_cols))
        record("P4", ds_name + " numeric detect", PASS if numeric_cols else WARN, "numeric_cols=" + str(numeric_cols))
    except Exception as ex:
        record("P4", ds_name + " detect", FAIL, str(ex)[:90])

for ds_name, date_col, target_col, horizon in [
    ("stock_market.csv", "Date", "Close", "Next 30 days"),
    ("superstore_sales.csv", "OrderDate", "Sales", "Next 30 days"),
    ("financial_transactions.csv", "Date", "Amount", "Next 30 days"),
]:
    try:
        df = datasets_raw[ds_name]["df"].copy()
        df[date_col] = pd.to_datetime(df[date_col])
        r = ForecastService.generate_forecast(df=df, date_col=date_col, target_col=target_col, horizon_str=horizon, agg_func="sum")
        if isinstance(r, dict) and r.get("error"):
            record("P4", ds_name + " forecast", FAIL, str(r["error"])[:90])
            record_bug("P4", "Forecast", "HIGH", str(r["error"])[:80], "services/forecast_service.py", "Fix pipeline")
        else:
            req_keys = ["forecast_df", "model_name", "historical_summary", "forecast_summary"]
            missing_k = [k for k in req_keys if k not in r]
            record("P4", ds_name + " forecast", WARN if missing_k else PASS,
                   "model=" + str(r.get("model_name")) + " missing=" + str(missing_k))
    except Exception as ex:
        record("P4", ds_name + " forecast", FAIL, str(ex)[:90])
        record_bug("P4", "Forecast Generation", "HIGH", str(ex)[:80], "services/forecast_service.py", "Fix")

# ═══════════════════════ PHASE 5: Data Quality ═══════════════════════
print("\n=== PHASE 5: Data Quality ===")
from services.quality_service import QualityService

for ds_name, res in datasets_raw.items():
    df = res["df"]
    try:
        report = QualityService.run_audit(df)
        req = ["score", "missing_total", "duplicates"]
        missing = [k for k in req if k not in report]
        record("P5", ds_name + " quality", WARN if missing else PASS,
               "score=" + str(report.get("score", "?")) + " missing_keys=" + str(missing))
        if missing:
            record_bug("P5", "Data Quality", "MEDIUM", "Missing report keys: " + str(missing), "services/quality_service.py", "Add missing keys")
    except Exception as ex:
        record("P5", ds_name + " quality", FAIL, str(ex)[:90])
        record_bug("P5", "Data Quality", "HIGH", str(ex)[:80], "services/quality_service.py", "Fix service")

# ═══════════════════════ PHASE 6: Evaluation Service ═══════════════════════
print("\n=== PHASE 6: Evaluation Service ===")
from services.evaluation_service import EvaluationService

try:
    EvaluationService.log_interaction(
        interaction_id="test_id_123",
        prompt="test prompt",
        generated_sql="SELECT * FROM test",
        executed_sql="SELECT * FROM test",
        generated_pandas="df.head()",
        confidence=0.85,
        execution_time=1.23,
        success=True,
        failure_reason=""
    )
    record("P6", "log_interaction", PASS, "OK")
except Exception as ex:
    record("P6", "log_interaction", FAIL, str(ex)[:80])
    record_bug("P6", "Evaluation", "HIGH", str(ex), "services/evaluation_service.py", "Fix log method")

try:
    metrics = EvaluationService.get_metrics()
    record("P6", "get_metrics", PASS if isinstance(metrics, dict) else FAIL, "type=" + str(type(metrics)))
except Exception as ex:
    record("P6", "get_metrics", FAIL, str(ex)[:80])

try:
    evals = EvaluationService.get_evaluations()
    record("P6", "get_evaluations", PASS if isinstance(evals, list) else FAIL, "type=" + str(type(evals)))
except Exception as ex:
    record("P6", "get_evaluations", FAIL, str(ex)[:80])

# ═══════════════════════ PHASE 7: Recommendations ═══════════════════════
print("\n=== PHASE 7: Recommendation Service ===")
from services.recommendation_service import RecommendationService

try:
    ss_df = datasets_raw["superstore_sales.csv"]["df"].copy()
    res_analysis = RecommendationService.run_analysis(ss_df)
    metrics = res_analysis.get("metrics", {})
    req = ["top_customers", "top_products", "anomalies_count", "quality_score"]
    missing = [k for k in req if k not in metrics]
    record("P7", "run_analysis", WARN if missing else PASS,
           "keys=" + str(list(metrics.keys())) + " missing=" + str(missing))
    if missing:
        record_bug("P7", "Recommendations", "MEDIUM", "Missing keys: " + str(missing), "services/recommendation_service.py", "Add missing keys")
except Exception as ex:
    record("P7", "run_analysis", FAIL, str(ex)[:90])
    record_bug("P7", "Recommendations", "HIGH", str(ex)[:80], "services/recommendation_service.py", "Fix")

# ═══════════════════════ PHASE 8: Config & Security ═══════════════════════
print("\n=== PHASE 8: Config & Security ===")
import config

blocked = getattr(config, "BLOCKED_SQL_KEYWORDS", [])
for kw in ["DROP", "DELETE", "INSERT", "UPDATE", "CREATE", "ALTER", "EXEC", "TRUNCATE", "GRANT", "REVOKE"]:
    present = kw in blocked
    record("P8", "Block " + kw, PASS if present else FAIL,
           "In blocklist" if present else "MISSING from BLOCKED_SQL_KEYWORDS")
    if not present:
        record_bug("P8", "SQL Security", "HIGH", kw + " not in BLOCKED_SQL_KEYWORDS", "config.py", "Add " + kw)

api_key = getattr(config, "GEMINI_API_KEY", None)
record("P8", "API key present", PASS if api_key else FAIL, "Set" if api_key else "MISSING")

model_name = getattr(config, "GEMINI_MODEL_NAME", None)
record("P8", "Model name configured", PASS if model_name else FAIL, str(model_name))

# ═══════════════════════ PHASE 9: Gemini Error Handling & Retries Simulation ═══════════════════════
print("\n=== PHASE 9: Gemini Error Handling & Retries Simulation ===")
from services.ai_service import AIService
from google.genai.errors import APIError

def test_gemini_error_simulation():
    # 1. Simulate No API Key
    orig_key = config.GEMINI_API_KEY
    config.GEMINI_API_KEY = ""
    res = AIService.generate_content("hello")
    has_key_err = "AI configuration error" in res and "missing API key" in res
    record("P9", "Simulate No API Key", PASS if has_key_err else FAIL, "Response: " + res[:80])
    config.GEMINI_API_KEY = orig_key

    # 2. Simulate 429 Quota Exceeded
    # Mock get_client to raise APIError with code 429
    # Quick utility to verify retry count
    failures_count = 0
    def mock_generate_content(*args, **kwargs):
        nonlocal failures_count
        failures_count += 1
        raise APIError(code=429, response_json={
            "error": {
                "code": 429,
                "message": "Quota exceeded",
                "status": "RESOURCE_EXHAUSTED",
                "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "0.1s"}]
            }
        })
    
    client_mock = mock.MagicMock()
    client_mock.models.generate_content = mock_generate_content

    with mock.patch.object(AIService, 'get_client', return_value=client_mock):
        # Temporarily mock time.sleep to run quickly
        with mock.patch('time.sleep', return_value=None):
            res_429 = AIService.generate_content("hello")
            has_quota_err = "AI quota exceeded" in res_429 and "✓ SQL" in res_429
            record("P9", "Simulate 429 Quota Exceeded Response", PASS if has_quota_err else FAIL, "Response: " + res_429[:80])
            record("P9", "Simulate 429 Retry Count (3 attempts)", PASS if failures_count == 3 else FAIL, "Attempts: " + str(failures_count))

    # 3. Simulate 503 Server Error / Temporary Unavailable
    failures_count_503 = 0
    def mock_generate_content_503(*args, **kwargs):
        nonlocal failures_count_503
        failures_count_503 += 1
        raise APIError(code=503, response_json={"error": {"code": 503, "message": "Service Unavailable"}})

    client_mock_503 = mock.MagicMock()
    client_mock_503.models.generate_content = mock_generate_content_503

    with mock.patch.object(AIService, 'get_client', return_value=client_mock_503):
        with mock.patch('time.sleep', return_value=None):
            res_503 = AIService.generate_content("hello")
            has_503_err = "AI service temporarily unavailable" in res_503
            record("P9", "Simulate 503 Service Unavailable Response", PASS if has_503_err else FAIL, "Response: " + res_503[:80])
            record("P9", "Simulate 503 Retry Count (3 attempts)", PASS if failures_count_503 == 3 else FAIL, "Attempts: " + str(failures_count_503))

    # 4. Simulate Network Timeout
    failures_count_timeout = 0
    def mock_generate_content_timeout(*args, **kwargs):
        nonlocal failures_count_timeout
        failures_count_timeout += 1
        raise Exception("Connection timed out waiting for server")

    client_mock_timeout = mock.MagicMock()
    client_mock_timeout.models.generate_content = mock_generate_content_timeout

    with mock.patch.object(AIService, 'get_client', return_value=client_mock_timeout):
        with mock.patch('time.sleep', return_value=None):
            res_timeout = AIService.generate_content("hello")
            has_timeout_err = "AI service temporarily unavailable" in res_timeout
            record("P9", "Simulate Timeout/Network Response", PASS if has_timeout_err else FAIL, "Response: " + res_timeout[:80])

test_gemini_error_simulation()

# ═══════════════════════ SUMMARY ═══════════════════════
print("\n" + "="*65)
print("FINAL TEST SUMMARY")
print("="*65)
total = len(all_results)
passed  = sum(1 for _, _, s, _ in all_results if s == PASS)
failed  = sum(1 for _, _, s, _ in all_results if s == FAIL)
warned  = sum(1 for _, _, s, _ in all_results if s == WARN)
score = int(100 * passed / total) if total else 0

print("Total tests:  " + str(total))
print("  Passed: " + str(passed))
print("  Failed: " + str(failed))
print("  Warned: " + str(warned))
print("Score:    " + str(score) + "/100")
print("\nBugs found: " + str(len(bugs)))
for i, b in enumerate(bugs, 1):
    print(f"  Bug #{i} [{b['severity']}] {b['phase']}/{b['feature']}: {b['desc'][:70]}")
    print(f"    File: {b['file']} | Fix: {b['fix'][:60]}")
