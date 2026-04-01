"""Tests for /api/whitelist/* endpoints."""

from conftest import make_whitelist_entry


class TestGetWhitelist:
    def test_get_empty(self, client, db, auth_cookies):
        resp = client.get("/api/whitelist", cookies=auth_cookies)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_with_entries(self, client, db, auth_cookies):
        make_whitelist_entry(db, company="Acme Corp")
        make_whitelist_entry(db, company="Tech Inc")

        resp = client.get("/api/whitelist", cookies=auth_cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        companies = [e["company_name"] for e in data]
        assert "acme corp" in companies
        assert "tech inc" in companies

    def test_requires_auth(self, client, db):
        resp = client.get("/api/whitelist")
        assert resp.status_code == 401


class TestAddToWhitelist:
    def test_add_entry(self, client, db, auth_cookies):
        resp = client.post(
            "/api/whitelist",
            json={"company_name": "NewCo", "notes": "Verified recruiter"},
            cookies=auth_cookies,
        )
        assert resp.status_code == 200

        # Verify it's in the list
        get_resp = client.get("/api/whitelist", cookies=auth_cookies)
        companies = [e["company_name"] for e in get_resp.json()]
        assert "newco" in companies

    def test_add_sets_added_by(self, client, db, auth_cookies):
        resp = client.post(
            "/api/whitelist",
            json={"company_name": "SomeCo"},
            cookies=auth_cookies,
        )
        assert resp.status_code == 200

        get_resp = client.get("/api/whitelist", cookies=auth_cookies)
        entry = next(e for e in get_resp.json() if "someco" in e["company_name"])
        assert entry["added_by"] == "testadmin"

    def test_requires_auth(self, client, db):
        resp = client.post("/api/whitelist", json={"company_name": "TestCo"})
        assert resp.status_code == 401


class TestRemoveFromWhitelist:
    def test_remove_entry(self, client, db, auth_cookies):
        entry = make_whitelist_entry(db, company="Acme Corp")

        resp = client.delete(f"/api/whitelist/{entry.id}", cookies=auth_cookies)
        assert resp.status_code == 200

        get_resp = client.get("/api/whitelist", cookies=auth_cookies)
        assert get_resp.json() == []

    def test_remove_not_found(self, client, db, auth_cookies):
        resp = client.delete("/api/whitelist/99999", cookies=auth_cookies)
        assert resp.status_code == 404

    def test_requires_auth(self, client, db):
        resp = client.delete("/api/whitelist/1")
        assert resp.status_code == 401
