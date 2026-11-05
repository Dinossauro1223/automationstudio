from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WaitConditionType(str, Enum):
    NONE = "none"
    PROCESS = "process"
    DELAY = "delay"
    IMAGE = "image"


def _shown(value: Any) -> str:
    """O valor como aparece numa mensagem de erro: o `repr`, cortado em 40 caracteres (400 dígitos não cabem numa linha)."""
    text = repr(value)
    return text if len(text) <= 40 else text[:37] + "..."


def _decimal_hint(value: Any) -> str:
    """O erro de digitação mais provável em português é a vírgula decimal (0,9 em vez de 0.9): a mensagem diz o que fazer."""
    return " Use ponto como separador decimal (0.9, não 0,9)." if isinstance(value, str) and "," in value else ""


@dataclass
class WaitCondition:
    """Condição de sincronização da V24.

    O objeto é intencionalmente independente da UI para que Editor, Timeline
    e executor compartilhem a mesma representação. A V24.4 consolida a primeira etapa com PROCESS
    e DELAY; novas condições podem ser acrescentadas sem remodelar Command.
    """
    type: WaitConditionType = WaitConditionType.NONE
    target: str = ""
    timeout: float = 0.0
    stable_ms: int = 1000
    after: float = 0.0
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.type, WaitConditionType):
            raw = str(self.type).split(".")[-1].lower()
            try:
                self.type = WaitConditionType(raw)
            except ValueError:
                self.type = WaitConditionType.NONE

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.timeout < 0:
            errors.append("Timeout da condição não pode ser negativo.")
        if self.stable_ms < 0:
            errors.append("Estabilidade da condição não pode ser negativa.")
        if self.after < 0:
            errors.append("Atraso posterior da condição não pode ser negativo.")
        if self.type == WaitConditionType.PROCESS and not self.target.strip() and not str(self.parameters.get("command_id", "")).strip():
            errors.append("Condição de processo sem comando de referência definido.")
        if self.type == WaitConditionType.IMAGE:
            path = str(self.parameters.get("image_path", "")).strip()
            if not path:
                errors.append("Condição de imagem sem arquivo definido.")
            # As conversões abaixo são as do executor (input_system, espera por imagem; vision.capture_region para a região).
            # `parameters` vem da leitura sem converter nada: um "0,9" digitado à mão não pode derrubar o início com um
            # ValueError sem contexto, nem passar e falhar no meio da execução. A validação diz qual valor é o problema.
            raw_confidence = self.parameters.get("confidence", 0.95)
            try:
                confidence = float(raw_confidence or 0.95)
            except (TypeError, ValueError, OverflowError):
                errors.append(f"Precisão da imagem precisa ser um número entre 0 e 1 (recebi {_shown(raw_confidence)}).{_decimal_hint(raw_confidence)}")
            else:
                if not 0.0 <= confidence <= 1.0:
                    errors.append("Precisão da imagem deve estar entre 0 e 1.")
            raw_interval = self.parameters.get("interval", 0.5)
            interval = None
            try:
                interval = float(raw_interval or 0.5)
            except (TypeError, ValueError, OverflowError):
                errors.append(f"Intervalo de verificação da imagem precisa ser um número, em segundos (recebi {_shown(raw_interval)}).{_decimal_hint(raw_interval)}")
            search = self.parameters.get("search", False)
            if not isinstance(search, bool):
                errors.append("Modo de busca da imagem inválido.")
            if interval is not None and interval <= 0:
                errors.append("Intervalo de verificação da imagem deve ser maior que zero.")
            region = self.parameters.get("region", {}) or {}
            if not isinstance(region, dict):
                errors.append("Região da imagem inválida.")
            else:
                for key in ("x", "y", "w", "h"):
                    try:
                        value = int(region.get(key, 0))
                    except (TypeError, ValueError, OverflowError):
                        errors.append(f"Região da imagem: '{key}' precisa ser um número inteiro (recebi {_shown(region.get(key))}).")
                        continue
                    if key in ("w", "h") and value < 0:
                        errors.append("Largura/altura da região não podem ser negativas.")
        if self.type == WaitConditionType.DELAY and self.after == 0 and self.timeout == 0:
            errors.append("Condição de atraso precisa de um valor maior que zero.")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "target": self.target,
            "timeout": self.timeout,
            "stable_ms": self.stable_ms,
            "after": self.after,
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "WaitCondition | None":
        if not isinstance(data, dict):
            return None
        return cls(
            type=data.get("type", WaitConditionType.NONE.value),
            target=str(data.get("target", "")),
            timeout=float(data.get("timeout", 0.0)),
            stable_ms=int(data.get("stable_ms", 1000)),
            after=float(data.get("after", 0.0)),
            parameters=dict(data.get("parameters", {}) or {}),
        )
