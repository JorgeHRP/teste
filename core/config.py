from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    SECRET_KEY: str = ""

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Hitachi — HCME Dealer API Hub
    HITACHI_BASE_URL: str = "https://etjhejwe3i.execute-api.eu-central-1.amazonaws.com/prd"
    HITACHI_CLIENT_ID: str = ""
    HITACHI_CLIENT_SECRET: str = ""
    HITACHI_TOKEN_URL: str = "https://hcme-api-prd.auth.eu-central-1.amazoncognito.com/oauth2/token"

    # John Deere
    JOHN_DEERE_BASE_URL: str = "https://sandboxapi.deere.com/platform"
    JOHN_DEERE_CLIENT_ID: str = ""
    JOHN_DEERE_CLIENT_SECRET: str = ""
    JOHN_DEERE_REDIRECT_URI: str = ""
    JOHN_DEERE_AUTH_URL: str = "https://signin.johndeere.com/oauth2/aus78tnlaysMCy95o346/v1/authorize"
    JOHN_DEERE_TOKEN_URL: str = "https://signin.johndeere.com/oauth2/aus78tnlaysMCy95o346/v1/token"
    JOHN_DEERE_SCOPES: str = "eq1 offline_access"

    # Trackunit
    TRACKUNIT_BASE_URL: str = "https://iris.trackunit.com/api"
    TRACKUNIT_API_TOKEN: str = ""

    # Proemion
    PROEMION_BASE_URL: str = "https://dataplatform.proemion.com"
    PROEMION_USERNAME: str = ""
    PROEMION_PASSWORD: str = ""
    PROEMION_MACHINE_SERVICE_PATH: str = "/ws-proemion-admin2/2009/09/14/MachineService"
    PROEMION_ADMIN_SERVICE_PATH: str = "/ws-proemion-admin2/2009/07/16/AdminMachineService"
    PROEMION_RUNTIME_SERVICE_PATH: str = "/ws-proemion-admin2/2009/07/16/RuntimeEntitiesService"
    PROEMION_MANAGEMENT_SERVICE_PATH: str = "/ws-proemion-management/2015/11/20/ManagementService"
    PROEMION_DATA_SERVICE_PATH: str = "/ws-proemion-data/DataService"

    # Cache
    REDIS_URL: str = ""
    CACHE_TTL_SECONDS: int = 300

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
