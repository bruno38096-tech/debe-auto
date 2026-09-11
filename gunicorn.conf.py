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
        import threading
        import app as debe_app
        import debe_runtime_fast as fast
        from debe_search_providers import make_search
        from debe_research_v2 import make_research

        cloud_search = make_search(fast.search_web)
        generic_research = make_research(cloud_search)

        def logged_research(model,engine,year,fuel):
            result=generic_research(model,engine,year,fuel)
            print('DEBE research:', model, engine, 'results=',result.get('search_results'), 'relevant=',result.get('relevant_sources'), 'evidence=',len(result.get('evidence') or []), flush=True)
            return result

        debe_app.dynamic_research = logged_research
        debe_app.search = cloud_search
        print('DEBE runtime: generic research v2 active', flush=True)

        def selftest():
            try:
                result=generic_research('Audi A4','2.0 TDI 170cv','2006','Diesel')
                print('DEBE research selftest: results=',result.get('search_results'),'relevant=',result.get('relevant_sources'),'evidence=',result.get('evidence'),'issues=',result.get('issues'),flush=True)
            except Exception as e:
                print('DEBE research selftest failed:',repr(e),flush=True)
        threading.Thread(target=selftest,daemon=True).start()
    except Exception as e:
        print('DEBE runtime worker patch failed:', e, flush=True)
