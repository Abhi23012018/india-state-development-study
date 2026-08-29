# Notebooks

Run the production modules first, then use notebooks only for exploration. The
canonical, reviewable analysis lives in `src/`; this prevents hidden notebook
state from becoming part of the data pipeline.

Suggested start:

```python
import pandas as pd
from src.analytics import correlation_matrices, fit_income_ols

states = pd.read_csv("../data/processed/india_state_development.csv")
correlation_matrices(states)["pearson"]
fit_income_ols(states).summary()
```

