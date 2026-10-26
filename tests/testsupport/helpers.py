"""Funções auxiliares comuns às suítes."""
from __future__ import annotations

import gzip
import json
import pathlib
import threading

from automationstudio.core import AutomationMap, Command, InputType

DATA = pathlib.Path(__file__).resolve().parents[1] / "data"


def run_to_end(engine, automation_map, timeout: float = 10.0):
    """Executa o mapa e espera o fim natural ou um erro. Devolve (terminou, erros)."""
    done, errors = threading.Event(), []
    engine.on_finished.append(done.set)
    engine.on_error.append(lambda exc: (errors.append(exc), done.set()))
    engine.run(automation_map)
    return done.wait(timeout), errors


def key(target: str, start: float, duration: float = 0.1, **kwargs) -> Command:
    return Command(type=InputType.KEY, target=target, start=start, duration=duration, **kwargs)


def make_map(commands, name: str = "Teste", **kwargs) -> AutomationMap:
    kwargs.setdefault("repeat_count", 1)
    return AutomationMap(name=name, commands=list(commands), **kwargs)


def events_of(backend) -> list[tuple]:
    """Eventos do MockInputBackend como (tempo, ação, alvo)."""
    return [tuple(e) for e in backend.events]


def load_legacy_maps() -> dict[str, str]:
    """Os 3 mapas reais (formato v1, como estavam no banco) usados nos testes de compatibilidade."""
    with gzip.open(DATA / "legacy_maps.json.gz", "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def join_engine(engine, timeout: float = 10.0) -> None:
    """Espera a thread do motor terminar (fim natural, erro ou parada). Falha se ela não terminar."""
    thread = engine._thread
    if thread is not None:
        thread.join(timeout)
        assert not thread.is_alive(), "a thread do motor não terminou no prazo"


def pressed_balance(backend) -> dict[str, int]:
    """Teclas e botões que sobraram pressionados no backend: {alvo: downs - ups}, só os diferentes de zero."""
    count: dict[str, int] = {}
    for _t, action, target in backend.events:
        if action in ("key_down", "mouse_down"):
            count[f"{action[:-5]}:{target}"] = count.get(f"{action[:-5]}:{target}", 0) + 1
        elif action in ("key_up", "mouse_up"):
            count[f"{action[:-3]}:{target}"] = count.get(f"{action[:-3]}:{target}", 0) - 1
    return {k: v for k, v in count.items() if v != 0}


def record_states(state_manager) -> list[tuple]:
    """Registra as transições de estado como (anterior, novo), em ordem."""
    seen: list[tuple] = []
    state_manager.on_change(lambda previous, new: seen.append((previous, new)))
    return seen


# ----------------------------------------------------------------------------------------- banco SQLite cru
def legacy_database(directory, maps: dict[str, str] | None = None):
    """Cria `AutomationStudio.db` na pasta com o esquema que as versões anteriores gravavam e devolve o caminho.

    `maps` é {nome: payload JSON}; sem argumento usa os 3 mapas reais das fixtures. Não passa pelo ProjectManager:
    é assim que um banco "de verdade" de outra versão chega ao programa.
    """
    import sqlite3
    pasta = pathlib.Path(directory)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / "AutomationStudio.db"
    con = sqlite3.connect(str(caminho))
    try:
        con.execute("CREATE TABLE IF NOT EXISTS maps (name TEXT PRIMARY KEY, payload TEXT NOT NULL, "
                    "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        for nome, payload in (load_legacy_maps() if maps is None else maps).items():
            con.execute("INSERT INTO maps(name,payload) VALUES(?,?)", (nome, payload))
        con.commit()
    finally:
        con.close()
    return caminho


def insert_raw_map(db_path, name: str, payload: str) -> None:
    """Insere uma linha na tabela `maps` sem validar nada (para simular registros quebrados ou estranhos)."""
    import sqlite3
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("INSERT INTO maps(name,payload) VALUES(?,?)", (name, payload))
        con.commit()
    finally:
        con.close()


def raw_rows(db_path, table: str = "maps") -> list[tuple]:
    """Linhas cruas de uma tabela do banco, em ordem de chave (nome/chave): maps -> (name, payload); settings -> (key, value)."""
    import sqlite3
    colunas = {"maps": "name,payload", "settings": "key,value"}[table]
    con = sqlite3.connect(str(db_path))
    try:
        return con.execute(f"SELECT {colunas} FROM {table} ORDER BY 1").fetchall()
    finally:
        con.close()


def raw_exec(db_path, sql: str, params: tuple = ()) -> None:
    """Executa um comando SQL direto no banco (apagar linha, trocar valor, etc.) e confirma."""
    import sqlite3
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(sql, params)
        con.commit()
    finally:
        con.close()
