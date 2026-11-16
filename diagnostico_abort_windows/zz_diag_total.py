"""TEMPORÁRIO (ramo zz-diag), tudo em um só plugin para perturbar o mínimo:
1) guarda a captura do pytest (stdout e stderr) em logs/zz_captura_<pid>_<n>.txt, que sobram depois de um abort;
2) no Windows, instala um tratador de SIGABRT que grava a PILHA NATIVA (módulo+deslocamento e o símbolo exportado mais
   próximo, via dbghelp) em logs/zz_pilha_nativa.txt e depois entrega o sinal a quem estava antes (o faulthandler);
3) AS_DIAG_EMPURRAO=N segura N listas vivas (desloca de N alocações o ponto em que o coletor de lixo roda)."""
import os
import sys
import tempfile

os.makedirs("logs", exist_ok=True)
with open(os.path.join("logs", "zz_pids.txt"), "a", encoding="utf-8") as _f:
    _f.write(f"{os.getpid()} {' '.join(sys.argv[:8])}\n")

_SEGURAR = [[] for _ in range(int(os.environ.get("AS_DIAG_EMPURRAO", "0") or 0))]

_original = tempfile.TemporaryFile
_n = [0]


def _arquivo(*args, **kwargs):
    try:
        chamador = sys._getframe(1).f_globals.get("__name__", "")
    except Exception:  # noqa: BLE001
        chamador = ""
    if chamador != "_pytest.capture":
        return _original(*args, **kwargs)
    _n[0] += 1
    return open(os.path.join("logs", f"zz_captura_{os.getpid()}_{_n[0]}.txt"), "w+b", buffering=0)


tempfile.TemporaryFile = _arquivo
try:
    import _pytest.capture as _cap
    if hasattr(_cap, "TemporaryFile"):
        _cap.TemporaryFile = _arquivo
except Exception:  # noqa: BLE001
    pass


def _instalar_pilha_nativa():
    if sys.platform != "win32" or os.environ.get("AS_DIAG_PILHA", "1") != "1":
        return
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32")
    dbg = ctypes.WinDLL("dbghelp")
    ucrt = ctypes.CDLL("ucrtbase")
    arquivo = os.path.join("logs", "zz_pilha_nativa.txt")

    class SYMBOL_INFO(ctypes.Structure):
        _fields_ = [("SizeOfStruct", ctypes.c_ulong), ("TypeIndex", ctypes.c_ulong), ("Reserved", ctypes.c_uint64 * 2),
                    ("Index", ctypes.c_ulong), ("Size", ctypes.c_ulong), ("ModBase", ctypes.c_uint64),
                    ("Flags", ctypes.c_ulong), ("Value", ctypes.c_uint64), ("Address", ctypes.c_uint64),
                    ("Register", ctypes.c_ulong), ("Scope", ctypes.c_ulong), ("Tag", ctypes.c_ulong),
                    ("NameLen", ctypes.c_ulong), ("MaxNameLen", ctypes.c_ulong), ("Name", ctypes.c_char * 1)]

    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.RtlCaptureStackBackTrace.restype = ctypes.c_ushort
    k32.RtlCaptureStackBackTrace.argtypes = [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p]
    k32.GetModuleHandleExW.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.HMODULE)]
    k32.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    dbg.SymInitialize.argtypes = [wintypes.HANDLE, ctypes.c_char_p, wintypes.BOOL]
    dbg.SymSetOptions.argtypes = [wintypes.DWORD]
    dbg.SymFromAddr.argtypes = [wintypes.HANDLE, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64), ctypes.c_void_p]
    processo = k32.GetCurrentProcess()
    dbg.SymSetOptions(0x2 | 0x4 | 0x40)          # UNDNAME | DEFERRED_LOADS | LOAD_ANYTHING
    dbg.SymInitialize(processo, None, True)

    TIPO = ctypes.CFUNCTYPE(None, ctypes.c_int)

    def tratador(sinal):
        try:
            try:
                dbg.SymRefreshModuleList(processo)
            except Exception:  # noqa: BLE001
                pass
            quadros = (ctypes.c_void_p * 64)()
            total = k32.RtlCaptureStackBackTrace(0, 64, quadros, None)
            linhas = [f"PILHA NATIVA no SIGABRT (pid {os.getpid()}, {total} quadros):"]
            buf = ctypes.create_string_buffer(ctypes.sizeof(SYMBOL_INFO) + 512)
            for i in range(total):
                endereco = quadros[i] or 0
                modulo, deslocamento = "?", 0
                try:
                    hmod = wintypes.HMODULE()
                    if k32.GetModuleHandleExW(0x4 | 0x2, ctypes.c_void_p(endereco), ctypes.byref(hmod)):
                        nome = ctypes.create_unicode_buffer(520)
                        k32.GetModuleFileNameW(hmod, nome, 520)
                        modulo = os.path.basename(nome.value)
                        deslocamento = endereco - (hmod.value or 0)
                except Exception as exc:  # noqa: BLE001
                    modulo = f"? ({exc!r})"
                simbolo = ""
                try:
                    sym = SYMBOL_INFO.from_buffer(buf)
                    sym.SizeOfStruct = ctypes.sizeof(SYMBOL_INFO)
                    sym.MaxNameLen = 511
                    desloc = ctypes.c_uint64(0)
                    if dbg.SymFromAddr(processo, endereco, ctypes.byref(desloc), ctypes.addressof(sym)):
                        simbolo = ctypes.string_at(ctypes.addressof(sym) + SYMBOL_INFO.Name.offset).decode("utf-8", "replace") + f"+0x{desloc.value:x}"
                except Exception as exc:  # noqa: BLE001
                    simbolo = f"(sem símbolo: {exc!r})"
                linhas.append(f"  #{i:02d} {modulo}+0x{deslocamento:x}  {simbolo}")
            with open(arquivo, "a", encoding="utf-8") as saida:
                saida.write("\n".join(linhas) + "\n")
                saida.flush()
        except BaseException as exc:  # noqa: BLE001
            try:
                with open(arquivo, "a", encoding="utf-8") as saida:
                    saida.write(f"falha ao gravar a pilha nativa: {exc!r}\n")
            except BaseException:  # noqa: BLE001
                pass
        anterior = _anterior[0]
        if anterior:
            try:
                TIPO(anterior)(sinal)
            except BaseException:  # noqa: BLE001
                pass

    _anterior = [None]
    _cb = TIPO(tratador)
    _instalar_pilha_nativa.guardar = _cb          # precisa viver tanto quanto o processo
    ucrt.signal.restype = ctypes.c_void_p
    ucrt.signal.argtypes = [ctypes.c_int, ctypes.c_void_p]
    _anterior[0] = ucrt.signal(22, ctypes.cast(_cb, ctypes.c_void_p))     # 22 = SIGABRT


try:
    _instalar_pilha_nativa()
except BaseException as _exc:  # noqa: BLE001
    with open(os.path.join("logs", "zz_pilha_nativa.txt"), "a", encoding="utf-8") as _f:
        _f.write(f"não instalei o tratador: {_exc!r}\n")
