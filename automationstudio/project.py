from __future__ import annotations



import contextlib

from .core import *


class ProjectManager:
    """Persistência V19: mapas em um único banco SQLite.

    O diretório recebido é o diretório de dados escolhido pelo usuário. Os
    mapas continuam podendo ser importados/exportados como JSON, mas o uso
    normal não cria uma coleção de arquivos JSON.
    """
    def __init__(self, project_dir: str | Path) -> None:
        self.project_dir = Path(project_dir).expanduser().resolve()
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.project_dir / "AutomationStudio.db"
        self.maps: dict[str, AutomationMap] = {}
        # Automações que estão no banco mas não puderam ser lidas na última carga ("nome: motivo").
        self.load_errors: list[str] = []
        self._init_db()
        self._migrate_legacy_json()

    @contextlib.contextmanager
    def _connect(self):
        """Abre o banco, confirma (ou desfaz) a transação e SEMPRE fecha a conexão."""
        con = sqlite3.connect(str(self.db_path), timeout=5)
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA foreign_keys=ON")
            with con:
                yield con
        finally:
            con.close()

    def _init_db(self):
        with self._connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS maps (name TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            con.commit()

    def _path_for(self, name: str) -> Path:
        safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()
        return self.project_dir / f"{safe_name or 'mapa'}.json"

    def save_map(self, automation_map: AutomationMap) -> Path:
        # Corrige IDs duplicados antes de qualquer persistência. Isso torna a
        # migração transparente mesmo para mapas que foram alterados em memória.
        automation_map.repair_duplicate_command_ids()
        payload = map_to_json(automation_map)
        with self._connect() as con:
            con.execute("INSERT INTO maps(name,payload,updated_at) VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(name) DO UPDATE SET payload=excluded.payload, updated_at=CURRENT_TIMESTAMP", (automation_map.name, payload))
            con.commit()
        self.maps[automation_map.name] = automation_map
        return self.db_path

    def load_map(self, path: str | Path) -> AutomationMap:
        p = Path(path)
        if p.suffix.lower() == '.json':
            automation_map = map_from_json(p.read_text(encoding='utf-8'))
        else:
            with self._connect() as con:
                row = con.execute("SELECT payload FROM maps WHERE name=?", (p.stem,)).fetchone()
            if not row:
                raise FileNotFoundError(str(path))
            automation_map = map_from_json(row[0])
        self.maps[automation_map.name] = automation_map
        return automation_map

    def load_all(self) -> list[AutomationMap]:
        self.maps.clear()
        self.load_errors = []
        with self._connect() as con:
            rows = con.execute("SELECT name,payload FROM maps ORDER BY name COLLATE NOCASE").fetchall()
        for name, payload in rows:
            try:
                automation_map = map_from_json(payload)
                self.maps[automation_map.name] = automation_map
            except Exception as exc:
                # Nunca descartar em silêncio: o registro continua no banco e o problema fica registrado e visível.
                reason = f"{type(exc).__name__}: {exc}"
                self.load_errors.append(f"{name}: {reason}")
                _append_runtime_log(f"MAPA NAO CARREGADO nome={name!r} erro={reason}")
        return list(self.maps.values())

    def delete_map(self, name: str) -> bool:
        with self._connect() as con:
            cur = con.execute("DELETE FROM maps WHERE name=?", (name,))
            con.commit()
        self.maps.pop(name, None)
        return cur.rowcount > 0

    def export_map(self, name: str, destination: str | Path) -> Path:
        automation_map = self.maps[name]
        automation_map.repair_duplicate_command_ids()
        dest = Path(destination)
        dest.write_text(map_to_json(automation_map), encoding='utf-8')
        return dest

    def import_map(self, source: str | Path) -> AutomationMap:
        automation_map = map_from_json(Path(source).read_text(encoding='utf-8'))
        self.save_map(automation_map)
        return automation_map

    def validate_all(self) -> list[str]:
        errors: list[str] = []
        hotkeys: dict[str, list[str]] = {}
        for automation_map in self.maps.values():
            errors.extend(automation_map.validate())
            if automation_map.hotkey:
                hotkeys.setdefault(automation_map.hotkey, []).append(automation_map.name)
        for hotkey, map_names in hotkeys.items():
            if len(map_names) > 1:
                errors.append(f"Atalho '{hotkey}' está duplicado entre os mapas: {', '.join(map_names)}.")
        return errors

    def _migrate_legacy_json(self) -> None:
        """Importa mapas V18 uma única vez, sem apagar os JSON originais."""
        with self._connect() as con:
            count = con.execute("SELECT COUNT(*) FROM maps").fetchone()[0]
        if count:
            return
        for path in sorted(self.project_dir.glob('*.json')):
            if path.name in ('settings.json',) or path.name.endswith('.recording_backup.json'):
                continue
            try:
                self.save_map(map_from_json(path.read_text(encoding='utf-8')))
            except Exception:
                continue

class AppSettings:
    """Configurações V19 armazenadas no mesmo SQLite dos mapas."""
    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / 'AutomationStudio.db'
        self._data: dict[str, Any] = {}
        self._init_db()
        self.load()

    @contextlib.contextmanager
    def _connect(self):
        """Abre o banco, confirma (ou desfaz) a transação e SEMPRE fecha a conexão."""
        con = sqlite3.connect(str(self.db_path), timeout=5)
        try:
            con.execute("PRAGMA journal_mode=WAL")
            with con:
                yield con
        finally:
            con.close()

    def _init_db(self):
        with self._connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            con.commit()

    def load(self) -> None:
        with self._connect() as con:
            rows = con.execute('SELECT key,value FROM settings').fetchall()
        self._data = {}
        for key, value in rows:
            try: self._data[key] = json.loads(value)
            except Exception: self._data[key] = value
        # Migra configurações V18 se ainda existirem.
        legacy = self.data_dir / 'settings.json'
        if not rows and legacy.exists():
            try:
                self._data = json.loads(legacy.read_text(encoding='utf-8'))
                self.save()
                legacy.rename(legacy.with_suffix('.json.migrado'))
            except Exception:
                self._data = {}

    def save(self) -> None:
        with self._connect() as con:
            for key, value in self._data.items():
                con.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, json.dumps(value, ensure_ascii=False)))
            con.commit()

    def get_maps_folder(self, default_folder: str | Path) -> Path:
        # V19: este valor representa o diretório de dados completo.
        raw = self._data.get('maps_folder') or self._data.get('data_folder')
        folder = Path(raw) if raw else Path(default_folder)
        try: folder.mkdir(parents=True, exist_ok=True)
        except OSError: folder = Path(default_folder); folder.mkdir(parents=True, exist_ok=True)
        return folder

    def set_maps_folder(self, folder: str | Path) -> None:
        self._data['maps_folder'] = str(Path(folder).resolve())
        self._data['data_folder'] = str(Path(folder).resolve())
        self.save()

    def get_recording_settings(self) -> dict[str, Any]:
        defaults = {'capture_keyboard': True,'capture_mouse_buttons': True,'capture_mouse_move': True,'capture_mouse_scroll': True,'record_key_duration': True,'merge_mouse_moves': True,'mouse_jitter_px': 3,'mouse_sample_interval_ms': 8,'ignored_keys': [],'ignored_mouse_buttons': []}
        saved = self._data.get('recording', {})
        if isinstance(saved, dict): defaults.update(saved)
        return defaults
    def set_recording_settings(self, values: dict[str, Any]) -> None:
        self._data['recording'] = dict(values); self.save()

    def get_control_hotkeys(self) -> dict[str, str]:
        defaults = {'pause': 'F9', 'resume': 'F10', 'emergency': 'F12', 'record_toggle': 'F8', 'record_cancel': 'F11'}
        saved = self._data.get('control_hotkeys', {})
        if isinstance(saved, dict): defaults.update(saved)
        return defaults
    def set_control_hotkeys(self, hotkeys: dict[str, str]) -> None:
        self._data['control_hotkeys'] = {k:v for k,v in hotkeys.items() if v}; self.save()

    def get_map_activation(self) -> dict[str, Any]:
        """Ativação por mapa (25.8): {"migrated": bool, "prefs": {nome do mapa: "sempre" | "desativado"}}.

        Vazio quando nada foi gravado ou quando o valor gravado não é um dicionário (o leitor de `AtivacaoMapas` cuida do
        resto). Devolve uma cópia: quem altera o resultado não altera a configuração. O formato dos mapas não muda."""
        saved = self._data.get('map_activation', {})
        return copy.deepcopy(saved) if isinstance(saved, dict) else {}

    def set_map_activation(self, values: dict[str, Any]) -> None:
        self._data['map_activation'] = copy.deepcopy(values); self.save()

    def get_visual_settings(self) -> dict[str, Any]:
        defaults = {'keyboard_mode':'compact','keyboard_timeout':3.0,'mouse_timeout':3.0,'keyboard_opacity':1.0,'mouse_opacity':1.0,'show_on_minimize':True,'show_keyboard':False,'show_mouse':False,'always_on_top':True,'click_virtual_keyboard':True,'keyboard_geometry':None,'mouse_geometry':None,'theme_mode':'system','accent_dark':'#FFC53D','accent_light':'#2F6FED','light_surface':'#FFFFFF','light_contrast':'#2F343B','virtual_surface_dark':'#4A4F57','virtual_surface_light':'#5A6068','virtual_text_dark':'#FFC53D','virtual_text_light':'#FFC53D','virtual_accent':'#FFC53D','onboarding_seen':False,'main_window_geometry':None,'main_window_state':None,'sidebar_width':360,'workspace_splitter_sizes':None}
        defaults['undo_ram_mb'] = 256
        defaults['text_char_interval'] = 0.01
        defaults['app_stable_ms'] = 1000
        defaults['app_after_open'] = 0.300
        # AS 21.1: espera adaptativa. Zero significa sem limite; a execução
        # termina a espera apenas quando o aplicativo realmente atingir
        # prontidão ou quando o usuário interromper a automação.
        defaults['app_wait_timeout'] = 0.0
        defaults['app_adaptive_learning'] = True
        defaults['app_readiness_history'] = {}
        saved=self._data.get('visual',{})
        if isinstance(saved,dict):
            defaults.update(saved)
            # Migração do padrão anterior (250 ms + 375 ms) para o novo
            # padrão de abertura: 1,0 s de estabilidade + 300 ms de margem.
            # Só altera valores que ainda correspondem exatamente aos defaults
            # antigos; escolhas personalizadas do usuário são preservadas.
            if saved.get('app_stable_ms') == 250 and abs(float(saved.get('app_after_open', -1)) - 0.375) < 1e-9:
                defaults['app_stable_ms'] = 1000
                defaults['app_after_open'] = 0.300
                try:
                    self._data['visual'] = dict(defaults)
                    self.save()
                except Exception:
                    pass
        return defaults
    def set_visual_settings(self, values: dict[str, Any]) -> None:
        self._data['visual']=dict(values); self.save()

class MapHistory:
    """Histórico por mapa com orçamento configurável de RAM.

    O usuário define nas configurações quanto de memória RAM pode ser usada
    pelos snapshots de Undo/Redo. O limite é global para o histórico do
    aplicativo; quando excedido, os snapshots mais antigos são descartados.
    O estado atual nunca é descartado.
    """
    DEFAULT_RAM_MB = 256
    MIN_RAM_MB = 16
    MAX_RAM_MB = 8192
    def __init__(self, ram_mb: int = DEFAULT_RAM_MB):
        self.ram_mb = max(self.MIN_RAM_MB, min(self.MAX_RAM_MB, int(ram_mb)))
        self._undo: dict[str, list[tuple[dict[str, Any], int, str]]] = {}
        self._redo: dict[str, list[tuple[dict[str, Any], int, str]]] = {}
        self._last: dict[str, dict[str, Any]] = {}
        self._last_bytes: dict[str, int] = {}
        self._last_label: dict[str, str] = {}
        self._restoring = False

    @property
    def budget_bytes(self) -> int:
        return self.ram_mb * 1024 * 1024

    def set_ram_mb(self, value: int) -> None:
        self.ram_mb = max(self.MIN_RAM_MB, min(self.MAX_RAM_MB, int(value)))
        self._trim()

    @staticmethod
    def _size(snap: dict[str, Any]) -> int:
        try:
            return len(json.dumps(snap, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        except Exception:
            return 4096

    def _total_bytes(self) -> int:
        return sum(size for stack in self._undo.values() for _, size, _ in stack) + sum(size for stack in self._redo.values() for _, size, _ in stack)

    def _trim(self) -> None:
        while self._total_bytes() > self.budget_bytes:
            candidates=[]
            for kind, store in (("undo",self._undo),("redo",self._redo)):
                for name, stack in store.items():
                    if stack:
                        candidates.append((stack[0][1], kind, name))
            if not candidates: break
            _, kind, name = min(candidates, key=lambda x:x[0])
            getattr(self, "_" + kind)[name].pop(0)

    def remember(self, m: AutomationMap, label: str = "Alteração") -> None:
        """Registra uma transação concluída do mapa."""
        if self._restoring: return
        snap = copy.deepcopy(m.to_dict())
        previous = self._last.get(m.name)
        clean_label = str(label or "Alteração").strip() or "Alteração"
        if previous is not None and previous != snap:
            size = self._size(previous)
            stack = self._undo.setdefault(m.name, [])
            stack.append((previous, size, clean_label))
            self._redo.setdefault(m.name, []).clear()
            self._trim()
        self._last[m.name] = snap
        self._last_bytes[m.name] = self._size(snap)
        self._last_label[m.name] = clean_label

    def commit(self, m: AutomationMap, label: str = "Alteração") -> None:
        """API explícita para confirmar uma transação da V23."""
        self.remember(m, label)

    def last_label(self, m: AutomationMap | None) -> str:
        """Mantém compatibilidade com a API V22; retorna a última transação."""
        return self._last_label.get(m.name, "Alteração") if m else "Alteração"

    def undo_label(self, m: AutomationMap | None) -> str:
        if not m:
            return "Alteração"
        stack = self._undo.get(m.name, [])
        return stack[-1][2] if stack else "Alteração"

    def redo_label(self, m: AutomationMap | None) -> str:
        if not m:
            return "Alteração"
        stack = self._redo.get(m.name, [])
        return stack[-1][2] if stack else "Alteração"

    def prime(self, m: AutomationMap) -> None:
        self._last[m.name]=copy.deepcopy(m.to_dict())
        self._last_bytes[m.name]=self._size(self._last[m.name])
        self._last_label[m.name]="Alteração"
        self._undo.setdefault(m.name, []).clear(); self._redo.setdefault(m.name, []).clear()

    def _pop(self, src, dst, m):
        stack=src.setdefault(m.name, [])
        if not stack: return None
        current=copy.deepcopy(m.to_dict()); snap,size,label=stack.pop(); dst.setdefault(m.name, []).append((current,self._size(current), label or "Alteração"))
        self._restoring=True
        try:
            restored=AutomationMap.from_dict(copy.deepcopy(snap))
            m.name=restored.name; m.description=restored.description; m.hotkey=restored.hotkey
            m.commands=restored.commands; m.groups=restored.groups; m.repeat_count=restored.repeat_count
            m.repeat_interval=restored.repeat_interval; m.speed=restored.speed; m.conflict_behavior=restored.conflict_behavior
            m.next_map=restored.next_map; m.confirm_delete_commands=restored.confirm_delete_commands
            self._last[m.name]=copy.deepcopy(m.to_dict())
            self._last_label[m.name]=label or "Alteração"
        finally: self._restoring=False
        self._trim()
        return m

    def undo(self,m): return self._pop(self._undo,self._redo,m)
    def redo(self,m): return self._pop(self._redo,self._undo,m)
    def can_undo(self,m): return bool(m and self._undo.get(m.name))
    def can_redo(self,m): return bool(m and self._redo.get(m.name))
    def usage_bytes(self) -> int: return self._total_bytes()
    def usage_text(self) -> str:
        used=self.usage_bytes()/1024/1024
        return f"{used:.1f} MB / {self.ram_mb} MB"

    def depth(self, m: AutomationMap | None) -> tuple[int,int]:
        if not m:
            return (0,0)
        return (len(self._undo.get(m.name,[])), len(self._redo.get(m.name,[])))


# Modular export contract: this project intentionally shares private helpers
# between UI modules via import *. Export them explicitly so runtime names
# such as _PYNPUT_AVAILABLE and _default_backend are not lost.
__all__ = [name for name in globals() if not name.startswith("__")]
