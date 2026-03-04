import json

from app.integrations.gmail import start_gmail_watch


if __name__ == "__main__":
    response = start_gmail_watch()
    print(json.dumps(response, indent=2))
