from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI

def inject_locale_header(app: FastAPI):
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        # 1. Generate the base schema
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            servers=[{"url": app.root_path or "/"}],  # ← advertise your base path
        )

        # 2. Re‑key every path to include the root_path prefix
        prefix = (app.root_path or "").rstrip("/") or ""
        new_paths = {}
        for raw_path, path_item in openapi_schema["paths"].items():
            new_paths[f"{prefix}{raw_path}"] = path_item
        openapi_schema["paths"] = new_paths

        # 3. Inject the `accept-language` header param as before
        for path_item in openapi_schema["paths"].values():
            for method in path_item.values():
                params = method.get("parameters", [])
                if not any(p.get("name") == "accept-language" for p in params):
                    params.append({
                        "name": "accept-language",
                        "in": "header",
                        "required": False,
                        "schema": {"title": "Locale", "type": "string", "default": "en"}
                    })
                method["parameters"] = params

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
