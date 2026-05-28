class MoviterException(Exception):
    """Base exception do projecto."""
    pass


class ExternalAPIError(MoviterException):
    """Erro ao chamar uma API externa."""
    def __init__(self, provider: str, message: str, status_code: int = None):
        self.provider = provider
        self.status_code = status_code
        super().__init__(f"[{provider}] {message}")


class EquipmentNotFoundError(MoviterException):
    """Equipamento não encontrado."""
    def __init__(self, equipment_id: str):
        super().__init__(f"Equipamento '{equipment_id}' não encontrado.")


class AuthenticationError(MoviterException):
    """Erro de autenticação com API externa."""
    def __init__(self, provider: str):
        super().__init__(f"Falha de autenticação com {provider}.")


class UnsupportedBrandError(MoviterException):
    """Marca sem integração implementada."""
    def __init__(self, brand: str):
        super().__init__(f"Marca '{brand}' não tem integração disponível.")
