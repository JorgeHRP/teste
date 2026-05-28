from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import Optional

from app.models.equipment import EquipmentModel, EquipmentListResponse
from app.adapters.equipment_adapter import to_list_item
from app.services import orchestrator, machines_db
from app.core.security import get_current_user
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/equipment", tags=["Equipment"])


@router.get("", response_model=EquipmentListResponse)
async def list_equipment(
    cod_cliente: str = Query(..., description="Código do cliente — ex: 101096"),
    x_jd_token: Optional[str] = Header(None, description="Access token John Deere (se aplicável)"),
):
    """
    Lista todos os equipamentos de um cliente com dados de telemetria.
    Cada item inclui estado, horas, combustível, DEF e alerta activo.
    """
    try:
        equipment_list = await orchestrator.get_equipment_list_for_client(
            cod_cliente, jd_access_token=x_jd_token
        )
        items = [to_list_item(eq) for eq in equipment_list]
        return EquipmentListResponse(items=items, total=len(items))
    except Exception as e:
        logger.error(f"Erro ao listar equipamentos para {cod_cliente}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mine", response_model=EquipmentListResponse)
async def list_my_equipment(
    current_user: dict = Depends(get_current_user),
    x_jd_token: Optional[str] = Header(None),
):
    """Lista as máquinas do utilizador autenticado."""
    cod_cliente = current_user["cod_cliente"]
    try:
        equipment_list = await orchestrator.get_equipment_list_for_client(
            cod_cliente, jd_access_token=x_jd_token
        )
        items = [to_list_item(eq) for eq in equipment_list]
        return EquipmentListResponse(items=items, total=len(items))
    except Exception as e:
        logger.error(f"Erro ao listar equipamentos para {cod_cliente}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{equipment_id}", response_model=EquipmentModel)
async def get_equipment_detail(
    equipment_id: str,
    x_jd_token: Optional[str] = Header(None, description="Access token John Deere (se aplicável)"),
):
    """
    Detalhe completo de um equipamento incluindo consumos,
    alertas activos, códigos de erro e localização GPS.
    """
    machine = await machines_db.get_machine_by_num(equipment_id)
    if not machine:
        # Tentar pelo chassis
        machine = await machines_db.get_machine_by_chassis(equipment_id)
    if not machine:
        raise HTTPException(status_code=404, detail=f"Equipamento '{equipment_id}' não encontrado.")

    try:
        return await orchestrator.get_equipment(machine, jd_access_token=x_jd_token)
    except Exception as e:
        logger.error(f"Erro ao obter detalhe de {equipment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
