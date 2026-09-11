"""Gunicorn hooks for DEBE beta runtime."""

def on_starting(server):
    try:
        from debe_runtime import patch_index
        patch_index('index.html')
        print('DEBE runtime: score guide injected', flush=True)
    except Exception as e:
        print('DEBE runtime startup patch failed:', e, flush=True)


def post_worker_init(worker):
    try:
        import app as debe_app
        from debe_runtime import dynamic_research, search_web
        debe_app.dynamic_research = dynamic_research
        debe_app.search = search_web
        print('DEBE runtime: generic research engine active', flush=True)
    except Exception as e:
        print('DEBE runtime worker patch failed:', e, flush=True)
