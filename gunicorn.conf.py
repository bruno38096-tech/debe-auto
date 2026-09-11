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

        cloud_search = make_search(fast.search_web)
        fast.search_web = cloud_search

        def logged_research(model,engine,year,fuel):
            result=fast.dynamic_research(model,engine,year,fuel)
            print('DEBE research:', model, engine, 'results=',result.get('search_results'), 'relevant=',result.get('relevant_sources'), 'evidence=',len(result.get('evidence') or []), flush=True)
            return result

        debe_app.dynamic_research = logged_research
        debe_app.search = cloud_search
        print('DEBE runtime: cloud-friendly generic research engine active', flush=True)

        def selftest():
            try:
                rows=cloud_search('Audi A4 2.0 TDI 170 common problems oil pump injectors DPF',8)
                print('DEBE search selftest: results=',len(rows),'sample=',[(r.get('title','')[:55],r.get('url','')[:80]) for r in rows[:3]],flush=True)
            except Exception as e:
                print('DEBE search selftest failed:',repr(e),flush=True)
        threading.Thread(target=selftest,daemon=True).start()
    except Exception as e:
        print('DEBE runtime worker patch failed:', e, flush=True)
