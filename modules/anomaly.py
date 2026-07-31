from services.anomaly_service import AnomalyService

def detect_anomalies(df):
    """
    Public wrapper preserving original detect_anomalies interface.
    Delegates to AnomalyService.
    """
    return AnomalyService.detect_anomalies(df)
