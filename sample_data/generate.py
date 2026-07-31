import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_sample_data():
    """Generates a realistic sales dataset."""
    dates = [datetime(2025, 1, 1) + timedelta(days=x) for x in range(100)]
    data = {
        'Date': dates,
        'Customer': [f'Cust_{i}' for i in range(100)],
        'Product': ['A', 'B', 'C'] * 33 + ['A'],
        'Category': ['Tech', 'Home', 'Office'] * 33 + ['Tech'],
        'Region': ['North', 'South', 'East', 'West'] * 25,
        'Sales': np.random.randint(100, 1000, 100),
        'Profit': np.random.randint(10, 200, 100),
        'Quantity': np.random.randint(1, 10, 100),
        'Discount': np.random.rand(100) * 0.2
    }
    return pd.DataFrame(data)

df = generate_sample_data()
df.to_csv('sample_data/sales_data.csv', index=False)
