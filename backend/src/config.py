from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    '''
        Dictates where to get the environment vars and 
            exports the settings to be used throughout the project
    '''
    DB_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        # from_attributes=True
    )


Config = Settings()