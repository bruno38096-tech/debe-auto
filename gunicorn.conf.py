"""Gunicorn startup hooks for DEBE."""

import os
import runpy

# Gunicorn loads this file before importing app:app. Explicitly execute the
# search-resilience layer so cloud search fallbacks are active in every worker.
runpy.run_path(os.path.join(os.getcwd(), 'sitecustomize.py'), run_name='_debe_search_resilience')
