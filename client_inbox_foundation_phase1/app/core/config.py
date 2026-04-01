from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "dev"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    google_cloud_project: str = ""
    google_pubsub_topic: str = ""
    google_pubsub_verification_token: str = ""
    google_service_account_json: str = ""
    google_workspace_user: str = ""
    google_sheet_id: str = ""
    google_sheet_worksheet: str = "InterviewTracker"

    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:5173/auth/callback"
    google_oauth_scopes: str = "openid,email,profile"

    gmail_user_id: str = "me"
    gmail_watch_label_ids: str = "INBOX"
    gmail_watch_label_filter_action: str = "include"

    sqlserver_host: str = "localhost"
    sqlserver_port: int = 1433
    sqlserver_db: str = "InterviewTracker"
    sqlserver_user: str = "sa"
    sqlserver_password: str = ""
    sqlserver_driver: str = "ODBC Driver 18 for SQL Server"

    n8n_base_url: str = "http://localhost:5678"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
