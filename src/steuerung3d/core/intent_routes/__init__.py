"""Intent routing helpers.

These modules keep core/intent_handler_impl.py small by grouping intent
application logic by domain (control, safety, params, motion, ...).

All handlers are *structural* refactors of the previous match/case logic.
"""
