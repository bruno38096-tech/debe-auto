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
        from debe_runtime import dynamic_research as broad_research
        from debe_search_providers import make_search
        from debe_research_v2 import make_research
        from debe_market_v2 import make_view

        cloud_search = make_search(fast.search_web)
        generic_research = make_research(cloud_search)

        def calibrated_score(year, km, vinv=''):
            """Useful 0-100 preliminary score without collapsing older cars at 35."""
            y=debe_app.num(year); k=debe_app.num(km)
            if not y or not k:
                return 68 if len(vinv or '')==17 else 64
            from datetime import datetime
            age=max(0,datetime.now().year-y)
            annual=k/max(1,age or 1)
            age_score=max(25,min(98,100-age*2.4))
            annual_score=max(25,min(98,100-(annual/1000)*2.2))
            mileage_score=max(20,min(98,100-(k/1000)*0.18))
            value=age_score*.35+annual_score*.35+mileage_score*.25+(5 if len(vinv or '')==17 else 0)
            return max(25,min(95,round(value)))

        # The marketplace cards use app.score at request time, so patch it before
        # installing the dual-market endpoint.
        debe_app.score = calibrated_score

        def _is_generic_strength(values):
            text=' '.join(values or []).lower()
            return (not values or 'não foi encontrada evidência positiva' in text
                    or 'não foram encontrados pontos fortes' in text)

        def _filter_era_mismatches(result, year):
            """Do not attach clearly later emissions systems to old cars."""
            try: y=int(str(year or '').strip())
            except Exception: y=0
            if not y or y>=2010:
                return result
            evidence=result.get('evidence') or []
            issues=result.get('issues') or []
            checks=result.get('checks') or []
            keep=[]
            for i,item in enumerate(evidence):
                if (item.get('category') or '').lower().startswith('adblue'):
                    continue
                keep.append(i)
            if len(keep)!=len(evidence):
                result['evidence']=[evidence[i] for i in keep]
                result['issues']=[issues[i] for i in keep if i < len(issues)] or issues
                result['checks']=[checks[i] for i in keep if i < len(checks)] or checks
                result['research_score']=max([x.get('confidence',0) for x in result['evidence']], default=result.get('research_score',30))
            return result

        def logged_research(model,engine,year,fuel):
            result=generic_research(model,engine,year,fuel)

            # V2 deliberately requires very exact year/engine evidence. For older
            # generations, useful sources often describe the whole generation
            # (e.g. 2004-2008) instead of putting the exact year in the title.
            # If that strict pass finds nothing, use the broader reader and keep
            # only evidence that still matches the detected model/engine.
            if not (result.get('evidence') or result.get('strength_evidence')):
                try:
                    fallback=broad_research(model,engine,year,fuel)
                    fallback=_filter_era_mismatches(fallback,year)
                    if fallback.get('evidence'):
                        result['issues']=fallback.get('issues') or result.get('issues')
                        result['checks']=fallback.get('checks') or result.get('checks')
                        result['evidence']=fallback.get('evidence') or []
                        result['research_score']=fallback.get('research_score',result.get('research_score',30))
                        result['research_available']=True
                        result['relevant_sources']=max(result.get('relevant_sources',0),fallback.get('relevant_sources',0))
                        merged=[]
                        for src in (result.get('sources') or [])+(fallback.get('sources') or []):
                            if src.get('url') and not any(x.get('url')==src.get('url') for x in merged):
                                merged.append(src)
                        result['sources']=merged[:8]
                    if _is_generic_strength(result.get('strengths')) and not _is_generic_strength(fallback.get('strengths')):
                        result['strengths']=fallback.get('strengths')[:3]
                        result['research_available']=True
                except Exception as e:
                    print('DEBE broad research fallback failed:', e, flush=True)

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
        print('DEBE runtime: generic research + broad fallback + calibrated score active', flush=True)
    except Exception as e:
        print('DEBE runtime worker patch failed:', e, flush=True)
