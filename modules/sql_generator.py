from services.sql_service import SQLService

def sanitize_table_name(filename):
    """
    Sanitizes a filename into a standard SQL table identifier.
    """
    return (
        filename.replace(".csv", "")
        .replace(" ", "_")
        .replace("-", "_")
    )


def execute_sql_query(sql, data_context):
    """
    Public wrapper preserving original execute_sql_query interface.
    Delegates to centralized SQLService.
    """
    return SQLService.execute_sql_query(sql, data_context)