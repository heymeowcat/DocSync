from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: str
    GITHUB_REDIRECT_URI: str = "http://localhost:8000/auth/github/callback"
    JWT_SECRET: str
    
    class Config:
        env_file = ".env"

settings = Settings()