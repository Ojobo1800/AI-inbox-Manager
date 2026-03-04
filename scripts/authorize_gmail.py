"""
One-time Gmail OAuth2 authorization script.

Run this ONCE to authorize InboxGenius to access c_interviews@colaberry.com.
It opens a browser, you log in as c_interviews@colaberry.com, grant access,
and the token is saved to config/gmail_token.json for all future use.

Usage:
    python scripts/authorize_gmail.py

Requirements:
    - http://localhost:8080 must be in the authorized redirect URIs
      in Google Cloud Console for the OAuth2 client.
"""

import sys
from pathlib import Path

# Allow importing from project root
sys.path.insert(0, str(Path(__file__).parent.parent / "execution"))

from google_auth_oauthlib.flow import Flow

SCOPES = ["https://mail.google.com/"]
PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / "config" / "gmail_credentials.json"
TOKEN_PATH = PROJECT_ROOT / "config" / "gmail_token.json"
REDIRECT_URI = "http://localhost:8080"


def main():
    print("=" * 60)
    print("InboxGenius — Gmail OAuth2 Authorization")
    print("=" * 60)
    print()

    if not CREDENTIALS_PATH.exists():
        print(f"ERROR: credentials not found at {CREDENTIALS_PATH}")
        sys.exit(1)

    if TOKEN_PATH.exists():
        print(f"Token already exists at {TOKEN_PATH}")
        overwrite = input("Re-authorize? (y/N): ").strip().lower()
        if overwrite != "y":
            print("Keeping existing token.")
            sys.exit(0)

    # Build the flow
    flow = Flow.from_client_secrets_file(
        str(CREDENTIALS_PATH),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    # Generate the authorization URL
    auth_url, _ = flow.authorization_url(
        access_type="offline",   # Get refresh token
        prompt="consent",        # Always show consent to get refresh token
        login_hint="c_interviews@colaberry.com",
    )

    print("Opening browser for authorization...")
    print()
    print("IMPORTANT: Sign in as c_interviews@colaberry.com")
    print()
    print("If the browser doesn't open automatically, visit:")
    print(f"  {auth_url}")
    print()

    import webbrowser
    webbrowser.open(auth_url)

    # Start a local server to capture the redirect
    print("Waiting for authorization (local server on http://localhost:8080)...")
    print()

    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs

    auth_code = None

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            if "code" in params:
                auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                    <html><body style="font-family:sans-serif;text-align:center;padding:50px">
                    <h2 style="color:green">Authorization successful!</h2>
                    <p>InboxGenius is now authorized to access Gmail.</p>
                    <p>You can close this tab.</p>
                    </body></html>
                """)
            elif "error" in params:
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                error = params["error"][0]
                self.wfile.write(f"<html><body><h2>Error: {error}</h2></body></html>".encode())
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # Suppress server logs

    server = HTTPServer(("localhost", 8080), CallbackHandler)
    server.handle_request()  # Wait for exactly one request

    if not auth_code:
        print("ERROR: Authorization failed — no code received.")
        sys.exit(1)

    # Exchange the code for tokens
    print("Exchanging authorization code for tokens...")
    flow.fetch_token(code=auth_code)
    creds = flow.credentials

    if not creds.refresh_token:
        print("WARNING: No refresh token received.")
        print("This may happen if you've authorized before.")
        print("Revoke access at myaccount.google.com/permissions and re-run.")

    # Save token
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    print()
    print("=" * 60)
    print("SUCCESS: Gmail authorized!")
    print("=" * 60)
    print(f"Token saved to: {TOKEN_PATH}")
    print()
    print("The scheduled task will now use OAuth2 to access Gmail.")
    print("No further action needed — token refreshes automatically.")


if __name__ == "__main__":
    main()
