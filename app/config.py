from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = Field("sqlite:///./db/pharma_delivery.db", alias="DATABASE_URL")

    # JWT
    secret_key: str = Field(..., alias="SECRET_KEY")
    algorithm: str = Field("HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(1440, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # File Uploads
    upload_folder: str = Field("uploads", alias="UPLOAD_FOLDER")
    max_file_size: int = Field(10 * 1024 * 1024, alias="MAX_FILE_SIZE")
    pdf_folder: str = Field("pdfs", alias="PDF_FOLDER")

    # CORS
    cors_origins: str = Field("*", alias="CORS_ORIGINS")

    # Super Admin Config
    super_admin_email: str = Field("superadmin@example.com", alias="SUPER_ADMIN_EMAIL")
    super_admin_password: str = Field("superadmin123", alias="SUPER_ADMIN_PASSWORD")

    debug: bool = Field(False, alias="DEBUG")

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()