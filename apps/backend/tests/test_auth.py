def signup(client, email: str, merchant_name: str = "Acme"):
    return client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "correct horse battery", "merchant_name": merchant_name},
    )


def test_signup_creates_user_and_merchant(client):
    response = signup(client, "owner@example.com", "Acme Store")

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "owner@example.com"
    assert body["merchant"]["name"] == "Acme Store"
    assert body["user"]["id"]
    assert body["merchant"]["id"]


def test_login_sets_http_only_session_and_me_returns_merchant(client):
    signup(client, "owner@example.com", "Acme Store")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery"},
    )

    assert response.status_code == 200
    assert response.headers["set-cookie"].startswith("voic_session=")
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/api/v1/auth/me").json()["merchant"]["name"] == "Acme Store"


def test_invalid_credentials_are_rejected(client):
    signup(client, "owner@example.com")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "wrong password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_each_authenticated_user_is_limited_to_their_merchant(client):
    signup(client, "first@example.com", "First Merchant")
    signup(client, "second@example.com", "Second Merchant")

    client.post(
        "/api/v1/auth/login",
        json={"email": "first@example.com", "password": "correct horse battery"},
    )
    first_identity = client.get("/api/v1/auth/me").json()

    client.post(
        "/api/v1/auth/login",
        json={"email": "second@example.com", "password": "correct horse battery"},
    )
    second_identity = client.get("/api/v1/auth/me").json()

    assert first_identity["merchant"]["name"] == "First Merchant"
    assert second_identity["merchant"]["name"] == "Second Merchant"
    assert first_identity["merchant"]["id"] != second_identity["merchant"]["id"]


def test_authenticated_user_cannot_read_another_merchants_resource(client):
    signup(client, "first@example.com", "First Merchant")
    second_signup = signup(client, "second@example.com", "Second Merchant")
    second_merchant_id = second_signup.json()["merchant"]["id"]

    client.post(
        "/api/v1/auth/login",
        json={"email": "first@example.com", "password": "correct horse battery"},
    )

    response = client.get(f"/api/v1/auth/merchants/{second_merchant_id}")

    assert response.status_code == 404
