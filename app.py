import argparse
import mimetypes
import fastapi
import gradio as gr
import uvicorn
from fastapi import HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
)
from fastapi.templating import Jinja2Templates
from importlib_resources import files
from starlette.responses import RedirectResponse, StreamingResponse

from __init__ import app
from config import settings
from loggers import AppLogger
from routers import (
    db_router,
    ui_router,
    chatbot_router,
    ingest_router,
    safe_join,
    strip_url,
)

parser = argparse.ArgumentParser()
parser.add_argument("--host", default=settings.HOST, type=str)
parser.add_argument("--port", default=settings.PORT, type=int)
args = parser.parse_args()
logger = AppLogger().get_logger()
templates = Jinja2Templates(directory="templates")
STATIC_PATH_LIB = files("gradio").joinpath("templates", "frontend", "static").as_posix()  # type: ignore
BUILD_PATH_LIB = files("gradio").joinpath("templates", "frontend", "assets").as_posix()  # type: ignore


@app.on_event("startup")
async def startup_event():
    app.log_in = True
    logger.info("Starting up...")
    logger.info(f"Host: {args.host}")
    logger.info(f"Port: {args.port}")
    if args.host == "0.0.0.0":
        logger.info(f"Access URL: http://localhost:{args.port}")
    else:
        logger.info(f"Access URL: http://{args.host}:{args.port}")

    # Mount Gradio apps early so /chat/ and /ingest/ work directly
    try:
        gr.mount_gradio_app(app, chatbot_router, "/chat/")
    except Exception:
        pass
    try:
        gr.mount_gradio_app(app, ingest_router, "/ingest/")
    except Exception:
        pass


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down...")


@app.head("/", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
def main(request: fastapi.Request):
    return RedirectResponse("/show-app")


@app.get("/show-app")
async def show():
    gr.mount_gradio_app(app, chatbot_router, "/chat/")
    return RedirectResponse("/chat/")


@app.get("/show-ingest")
async def ingest_page():
    gr.mount_gradio_app(app, ingest_router, "/ingest/")
    return RedirectResponse("/ingest/")


@app.get("/config")
def get_config(request: fastapi.Request):
    root_path = (
        request.scope.get("root_path") or request.headers.get("X-Direct-Url") or ""
    )
    config = app.get_blocks().config
    config["root"] = strip_url(root_path)
    return config


@app.get("/static/{path:path}")
def static_resource(path: str):
    static_file = safe_join(STATIC_PATH_LIB, path)
    return FileResponse(static_file)


@app.get("/assets/{path:path}")
def build_resource(path: str):
    build_file = safe_join(BUILD_PATH_LIB, path)
    return FileResponse(build_file)


@app.get("/favicon.ico")
async def favicon():
    return static_resource("img/logo.svg")


@app.get("/theme.css", response_class=PlainTextResponse)
def theme_css():
    return PlainTextResponse(
        gr.themes.Default()._get_theme_css(), media_type="text/css"
    )


app.include_router(router=ui_router)
app.include_router(router=db_router)


if __name__ == "__main__":
    uvicorn.run(app=app, host=args.host, port=args.port)
