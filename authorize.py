# authorize.py — run once to mint the refresh token
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)   # opens your browser to click "Allow"

with open("authorized_user.json", "w") as f:
    f.write(creds.to_json())

print("\n=== SUCCESS ===")
print("Saved authorized_user.json — this contains your refresh token.")
print("Keep it secret. Next: load it into GitHub secrets.")
