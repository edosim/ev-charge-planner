from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import mount_app

def test_serves_index_html(tmp_path):
    text_html = "<h1>EV Charge Planner</h1>"
    # mock dist path
    (tmp_path / "index.html").write_text(text_html)
    test_app = FastAPI()

    mount_app(test_app, tmp_path)

    response = TestClient(test_app).get("/")

    assert response.status_code == 200
    assert response.text == text_html
