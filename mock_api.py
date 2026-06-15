"""
mock_api.py
 
Minimalni lokalni API za testiranje HTTP Runnera.
Namerno ima loše ponašanje da fuzzer može da detektuje anomalije.
 
Pokretanje:
    uvicorn mock_api:app --reload --port 8080
"""
 
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
 
app = FastAPI(title="Mock Bookstore API")
 
 
# ---------------------------------------------------------------------------
# /books
# ---------------------------------------------------------------------------
 
@app.get("/books")
def list_books(limit: int = 10, genre: str = None):
    return [
        {"id": 1, "title": "Clean Code", "author": "Robert Martin"},
        {"id": 2, "title": "The Pragmatic Programmer", "author": "Hunt & Thomas"},
    ]
 
 
@app.post("/books")
async def create_book(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})
 
    # Namerno loše ponašanje — ako title nije string, server crasha (500)
    title = body.get("title")
    if isinstance(title, list):
        # Simuliramo server crash na neočekivanom tipu
        raise Exception("Unexpected type caused server error")
 
    # Namerno loše ponašanje — prihvata prazan title bez validacije (contract mismatch)
    return JSONResponse(status_code=201, content={"id": 3, "title": title})
 
 
# ---------------------------------------------------------------------------
# /books/{bookId}
# ---------------------------------------------------------------------------
 
@app.get("/books/{bookId}")
def get_book(bookId: str):
    # Namerno — prihvata bookId kao string, ne validira tip
    if bookId == "1":
        return {"id": 1, "title": "Clean Code", "author": "Robert Martin"}
    return JSONResponse(status_code=404, content={"error": "Not found"})
 
 
@app.put("/books/{bookId}")
async def update_book(bookId: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})
 
    return JSONResponse(status_code=200, content={"id": bookId, **body})
 
 
@app.delete("/books/{bookId}")
def delete_book(bookId: str):
    from starlette.responses import Response
    return Response(status_code=204)
 
# ---------------------------------------------------------------------------
# /users
# ---------------------------------------------------------------------------
 
@app.post("/users")
async def register_user(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})
 
    # Namerno loše — ne validira required polja, prihvata sve
    username = body.get("username", "")
    return JSONResponse(status_code=201, content={"username": username})
 