# Auth Service (Prototype)

This prototype provides a JWT token endpoint and a role-protected test route.

Run locally:

```powershell
pip install -r services/auth/requirements.txt
python services/auth/app.py
```

Use `POST /v1/token` with JSON `{"email": "alice@example.com", "password": "password"}` to receive a token.
