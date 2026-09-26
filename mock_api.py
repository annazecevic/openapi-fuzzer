# Minimalni lokalni Bookstore API za demonstraciju i testiranje fuzzera.
# Namerno sadrži bagove (označene kao BUG-XX, isti ID-jevi kao u
# ground_truth/known_bugs.yaml) da bi fuzzer imao šta da otkrije. Knjige se
# čuvaju u memoriji, pa POST /books vraća stvaran id koji dependency graph
# zatim koristi za GET/PUT/DELETE /books/{bookId}.
#
# Pokretanje:
#     uvicorn mock_api:app --reload --port 8080

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Mock Bookstore API")

# Skladište knjiga u memoriji (id → knjiga) i sledeći slobodan id
_books = {
    1: {"id": 1, "title": "Clean Code", "author": "Robert Martin"},
    2: {"id": 2, "title": "The Pragmatic Programmer", "author": "Hunt & Thomas"},
}
_next_id = 3


# Vraća sve knjige; limit i genre se primaju ali se ne koriste
@app.get("/books")
def list_books(limit: int = 10, genre: str = None):
    return list(_books.values())


# Kreira knjigu i vraća je sa novim id-jem (201) — bez validacije tela
@app.post("/books")
async def create_book(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    title = body.get("title")
    # BUG-01: Server puca (500) ako je title lista umesto stringa
    if isinstance(title, list):
        # Simuliramo server crash na neočekivanom tipu
        raise Exception("Unexpected type caused server error")

    # BUG-02: Prihvata zahtev bez obaveznog title polja, vraca 201
    # BUG-03: Prihvata zahtev bez obaveznog author polja, vraca 201
    global _next_id
    new_book = {"id": _next_id, "title": title, "author": body.get("author")}
    _books[_next_id] = new_book
    _next_id += 1
    return JSONResponse(status_code=201, content=new_book)


# ---------------------------------------------------------------------------
# /books/{bookId}
# ---------------------------------------------------------------------------

# Vraća knjigu po id-ju; bookId se prima kao string, pa neispravan id (npr.
# "abc") daje 404 umesto 400
@app.get("/books/{bookId}")
def get_book(bookId: str):
    try:
        key = int(bookId)
    except ValueError:
        return JSONResponse(status_code=404, content={"error": "Not found"})

    if key in _books:
        return _books[key]
    return JSONResponse(status_code=404, content={"error": "Not found"})


# "Ažurira" knjigu — samo vraća primljeno telo, ništa ne proverava niti čuva
@app.put("/books/{bookId}")
async def update_book(bookId: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    # BUG-04: Prihvata bilo koje telo bez obaveznih polja, vraca 200
    # BUG-05: Prihvata bilo koji bookId, ukljucujuci nepostojeci, vraca 200 umesto 404
    return JSONResponse(status_code=200, content={"id": bookId, **body})


# Uvek vraća 204, bez obzira da li knjiga postoji; ništa se ne briše
@app.delete("/books/{bookId}")
def delete_book(bookId: str):
    from starlette.responses import Response
    return Response(status_code=204)



# Registruje korisnika (201) — vraća samo username, bez validacije tela
@app.post("/users")
async def register_user(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    username = body.get("username", "")
    # BUG-06: Prihvata zahtev bez obaveznog email polja, vraca 201
    # BUG-07: Prihvata zahtev bez obaveznog password polja, vraca 201
    return JSONResponse(status_code=201, content={"username": username})

