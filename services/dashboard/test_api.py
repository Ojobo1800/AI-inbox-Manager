"""Test API stats endpoint directly."""
import requests

# First login to get session
login_response = requests.post(
    'http://localhost:8000/api/auth/login',
    json={'username': 'admin', 'password': 'admin123'}
)
print(f"Login status: {login_response.status_code}")
cookies = login_response.cookies

# Get stats
stats_response = requests.get(
    'http://localhost:8000/api/stats/summary',
    cookies=cookies
)
print(f"\nStats status: {stats_response.status_code}")
print(f"Stats response:\n{stats_response.json()}")

# Get processing runs
runs_response = requests.get(
    'http://localhost:8000/api/stats/processing-runs?limit=5',
    cookies=cookies
)
print(f"\nRuns status: {runs_response.status_code}")
print(f"Runs response:\n{runs_response.json()}")
