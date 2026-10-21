"""HTTP layer: thin FastAPI routers, one module per endpoint group.

Routes only translate HTTP to calls into the other layers; they hold no logic.
The API is read-only, so every route is a GET (a test enforces it).
"""
