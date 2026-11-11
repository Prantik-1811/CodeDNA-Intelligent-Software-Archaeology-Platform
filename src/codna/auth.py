"""Authentication helpers for local accounts and OAuth providers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"{base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_value, digest_value = encoded.split("$", 1)
        salt = base64.urlsafe_b64decode(salt_value.encode())
        expected = base64.urlsafe_b64decode(digest_value.encode())
    except (ValueError, UnicodeDecodeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return hmac.compare_digest(actual, expected)


def auth_secret() -> bytes:
    secret = os.getenv("CODNA_AUTH_SECRET")
    if not secret:
        raise RuntimeError("CODNA_AUTH_SECRET must be configured before authentication is enabled.")
    return secret.encode()


def create_oauth_state(provider: str) -> str:
    payload = json.dumps({"provider": provider, "expires": int(time.time()) + 600}, separators=(",", ":"))
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    signature = hmac.new(auth_secret(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def verify_oauth_state(state: str, provider: str) -> bool:
    try:
        encoded, signature = state.split(".", 1)
        expected = hmac.new(auth_secret(), encoded.encode(), hashlib.sha256).hexdigest()
        payload = json.loads(base64.urlsafe_b64decode(f"{encoded}==").decode())
        return (
            hmac.compare_digest(signature, expected)
            and payload["provider"] == provider
            and int(payload["expires"]) >= int(time.time())
        )
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return False


def oauth_config(provider: str) -> dict[str, str]:
    prefix = provider.upper()
    values = {
        "client_id": os.getenv(f"{prefix}_CLIENT_ID", ""),
        "client_secret": os.getenv(f"{prefix}_CLIENT_SECRET", ""),
        "redirect_uri": os.getenv(
            f"{prefix}_REDIRECT_URI",
            f"http://localhost:8001/auth/{provider}/callback",
        ),
    }
    if not values["client_id"] or not values["client_secret"]:
        raise RuntimeError(f"{provider.title()} OAuth is not configured.")
    return values


def oauth_authorization_url(provider: str, state: str) -> str:
    config = oauth_config(provider)
    if provider == "google":
        endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
        }
    else:
        endpoint = "https://github.com/login/oauth/authorize"
        params = {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "scope": "read:user user:email",
            "state": state,
        }
    return f"{endpoint}?{urlencode(params)}"


def exchange_oauth_code(provider: str, code: str) -> dict:
    config = oauth_config(provider)
    if provider == "google":
        token_url = "https://oauth2.googleapis.com/token"
        profile_url = "https://openidconnect.googleapis.com/v1/userinfo"
    else:
        token_url = "https://github.com/login/oauth/access_token"
        profile_url = "https://api.github.com/user"

    token_request = Request(
        token_url,
        data=urlencode({
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code": code,
            "redirect_uri": config["redirect_uri"],
            "grant_type": "authorization_code",
        }).encode(),
        headers={"Accept": "application/json"},
    )
    with urlopen(token_request, timeout=15) as response:
        token_data = json.loads(response.read())
    access_token = token_data.get("access_token")
    if not access_token:
        raise RuntimeError("OAuth provider did not return an access token.")
    profile_request = Request(
        profile_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": "CodeDNA",
        },
    )
    with urlopen(profile_request, timeout=15) as response:
        profile = json.loads(response.read())
    if provider == "github" and not profile.get("email"):
        emails_request = Request(
            "https://api.github.com/user/emails",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "CodeDNA",
            },
        )
        with urlopen(emails_request, timeout=15) as response:
            emails = json.loads(response.read())
        verified = [email for email in emails if email.get("verified") and email.get("email")]
        preferred = next((email for email in verified if email.get("primary")), None)
        if preferred is None and verified:
            preferred = verified[0]
        if preferred:
            profile["email"] = preferred["email"]
    return profile
