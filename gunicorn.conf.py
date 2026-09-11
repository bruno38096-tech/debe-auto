"""Gunicorn hooks for DEBE beta runtime."""

def on_starting(server):
    try:
        from debe_runtime import patch_index
        from debe_ui_patch_v2 import patch_market_ui
        patch_index('index.html')
        patch_market_ui('index.html')
        print('DEBE runtime: score guide and market groups injected', flush=True)
    except Exception as e:
        print('DEBE runtime startup patch failed:', e, flush=True)


def post_worker_init(worker):
    try:
        import app as debe_app
        import debe_runtime_fast as fast
        from debe_search_providers import make_search
        from debe_research_v2 import make_research
        from debe_market_v2 import make_view

        cloud_search = make_search(fast.search_web)
        generic_research = make_research(cloud_search)

        def logged_research(model,engine,year,fuel):
            result=generic_research(model,engine,year,fuel)
            print('DEBE research:', model, engine,
                  'results=',result.get('search_results'),
                  'positive=',result.get('positive_results'),
                  'relevant=',result.get('relevant_sources'),
                  'positive_relevant=',result.get('positive_sources'),
                  'evidence=',len(result.get('evidence') or []),
                  'strengths=',len(result.get('strength_evidence') or []), flush=True)
            return result

        debe_app.dynamic_research = logged_research
        debe_app.search = cloud_search
        # Replace the existing Flask view without changing the public endpoint.
        debe_app.app.view_functions['comparables'] = make_view(debe_app)
        print('DEBE runtime: generic research + dual market engine active', flush=True)
    except Exception as e:
        print('DEBE runtime worker patch failed:', e, flush=True)
