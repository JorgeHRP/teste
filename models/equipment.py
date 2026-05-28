from pydantic import BaseModel
from typing import Optional
from enum import Enum


class EquipmentStatus(str, Enum):
    # Herda de str para serialização automática em JSON
    telemetry_with_alert = "telemetryWithAlert"
    telemetry_no_alert = "telemetryNoAlert"
    no_telemetry = "noTelemetry"


class AlertInfo(BaseModel):
    title: str
    description: str
    timeAgo: str


class ErrorCode(BaseModel):
    spn: str
    fmi: str
    sourceAddress: str
    description: str


class EquipmentModel(BaseModel):
    # Identificação
    id: str
    brand: str
    model: str
    category: str
    serialNumber: str
    imageUrl: str

    # Estado / Telemetria
    status: EquipmentStatus
    hasTelemetry: bool
    hours: float
    fuelLevel: float
    defLevel: float
    lastCommunication: str           # ISO 8601
    telemetryUrl: Optional[str]
    operatorManualUrl: Optional[str]

    # Localização
    location: str
    latitude: Optional[float]
    longitude: Optional[float]

    # Manutenção
    nextRevisionDays: Optional[int]
    warrantyDays: Optional[int]

    # Consumos
    tankCapacityLiters: Optional[float]
    avgFuelConsumption: Optional[float]
    avgAdBlueConsumption: Optional[float]
    weeklyAvgConsumption: Optional[float]
    peakConsumption: Optional[float]

    # Alertas
    activeAlert: Optional[AlertInfo]
    errorCodes: list[ErrorCode] = []


class EquipmentListItem(BaseModel):
    """Versão resumida para listagem."""
    id: str
    brand: str
    model: str
    category: str
    serialNumber: str
    imageUrl: str
    status: EquipmentStatus
    hasTelemetry: bool
    hours: float
    fuelLevel: float
    defLevel: float
    location: str
    activeAlert: Optional[AlertInfo]


class EquipmentListResponse(BaseModel):
    items: list[EquipmentListItem]
    total: int


# ----- Modelos internos da BD (máquinas da Moviter/Rocim) -----

class MachineRecord(BaseModel):
    """Registo da tabela machines no Supabase."""
    id: int
    chassis: str
    num_maquina: str
    designacao: str
    cod_cliente: str
    nome_cliente: str
    localidade: str
    marca: str
    familia: str
    cod_marca: str
    cod_modelo: str
    modelo: Optional[str]
    email: Optional[str]
    telefone1: Optional[str]
    synced_at: Optional[str]
