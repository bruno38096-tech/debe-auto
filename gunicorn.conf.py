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
        from debe_runtime_fast import dynamic_research as _dynamic_research, search_web
        def logged_research(model,engine,year,fuel):
            result=_dynamic_research(model,engine,year,fuel)
            print('DEBE research:', model, engine, 'results=',result.get('search_results'), 'relevant=',result.get('relevant_sources'), 'evidence=',len(result.get('evidence') or []), flush=True)
            return result
        debe_app.dynamic_research = logged_research
        debe_app.search = search_web
        print('DEBE runtime: fast generic research engine active', flush=True)
    except Exception as e:
        print('DEBE runtime worker patch failed:', e, flush=True)
