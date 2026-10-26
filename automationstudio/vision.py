from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import time

from PySide6.QtGui import QGuiApplication, QImage

try:
    import cv2
    import numpy as np
    _OPENCV_AVAILABLE=True
except Exception:
    cv2=None
    np=None
    _OPENCV_AVAILABLE=False


class ImageWaitError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImageMatchResult:
    found: bool
    similarity: float
    elapsed: float


def _image_pixels(image: QImage) -> tuple[bytes, int, int, int]:
    img=image.convertToFormat(QImage.Format.Format_RGB888)
    return bytes(img.bits()), img.width(), img.height(), img.bytesPerLine()


def compare_images(template: QImage, current: QImage) -> float:
    """Compara duas imagens RGB do mesmo tamanho em memória.

    Retorna 1.0 para imagens idênticas e 0.0 para máxima diferença média.
    A comparação é deliberadamente simples e determinística para a primeira
    etapa da V25; não depende de OpenCV, OCR ou arquivos temporários.
    """
    t=template.convertToFormat(QImage.Format.Format_RGB888)
    c=current.convertToFormat(QImage.Format.Format_RGB888)
    if t.size() != c.size() or t.isNull() or c.isNull():
        return 0.0
    tb,_,_,tstride=_image_pixels(t)
    cb,_,_,cstride=_image_pixels(c)
    if not tb or not cb:
        return 0.0
    total=0
    samples=0
    # Subamostragem adaptativa: suficiente para filtrar rapidamente, sem
    # transformar cada verificação em uma operação pesada para a CPU.
    step=max(1, int(math.sqrt((t.width()*t.height())/250000)))
    for y in range(0,t.height(),step):
        to=y*tstride; co=y*cstride
        for x in range(0,t.width(),step):
            i=to+x*3
            j=co+x*3
            total += abs(tb[i]-cb[j]) + abs(tb[i+1]-cb[j+1]) + abs(tb[i+2]-cb[j+2])
            samples += 3
    return max(0.0, min(1.0, 1.0 - (total/(samples*255.0)))) if samples else 0.0


def capture_region(region: dict | None = None, default_size: tuple[int,int] | None = None) -> QImage:
    app=QGuiApplication.instance()
    if app is None:
        raise ImageWaitError("A captura de tela exige uma aplicação Qt em execução.")
    screen=app.primaryScreen()
    if screen is None:
        raise ImageWaitError("Nenhuma tela disponível para captura.")
    r=region or {}
    x=int(r.get("x",0)); y=int(r.get("y",0)); w=int(r.get("w",0)); h=int(r.get("h",0))
    if w > 0 and h > 0:
        image=screen.grabWindow(0,x,y,w,h)
    elif default_size and default_size[0] > 0 and default_size[1] > 0:
        image=screen.grabWindow(0,x,y,int(default_size[0]),int(default_size[1]))
    else:
        # Sem região explícita, usar a tela inteira. Esta modalidade é útil
        # somente quando a imagem de referência tiver o mesmo tamanho da tela.
        image=screen.grabWindow(0)
    if image.isNull():
        raise ImageWaitError("Não foi possível capturar a tela.")
    return image.toImage()



def _qimage_array(image: QImage):
    if not _OPENCV_AVAILABLE:
        return None
    img=image.convertToFormat(QImage.Format.Format_RGB888)
    raw=bytes(img.bits())
    arr=np.frombuffer(raw, dtype=np.uint8).reshape((img.height(), img.bytesPerLine()))
    return arr[:, :img.width()*3].reshape((img.height(), img.width(), 3))


def template_match(template: QImage, current: QImage, confidence: float) -> float:
    if not _OPENCV_AVAILABLE:
        return compare_images(template, current)
    ta=_qimage_array(template); ca=_qimage_array(current)
    if ta is None or ca is None or ta.shape[0] > ca.shape[0] or ta.shape[1] > ca.shape[1]:
        return 0.0
    result=cv2.matchTemplate(ca, ta, cv2.TM_CCOEFF_NORMED)
    score=float(np.nanmax(result)) if result.size else 0.0
    return max(0.0, min(1.0, score))

def wait_for_image(path: str, *, confidence: float = 0.95, interval: float = 0.5,
                   timeout: float = 0.0, region: dict | None = None,
                   stop_event=None, search: bool = False) -> ImageMatchResult:
    file_path=Path(path).expanduser()
    if not file_path.is_file():
        raise ImageWaitError(f"Imagem não encontrada: {file_path}")
    template=QImage(str(file_path))
    if template.isNull():
        raise ImageWaitError(f"Não foi possível abrir a imagem: {file_path}")
    start=time.monotonic()
    while True:
        if stop_event is not None and stop_event.is_set():
            return ImageMatchResult(False,0.0,time.monotonic()-start)
        capture_size=None if search else (template.width(), template.height())
        current=capture_region(region, default_size=capture_size)
        score=template_match(template,current,confidence) if search else compare_images(template,current)
        if score >= confidence:
            return ImageMatchResult(True,score,time.monotonic()-start)
        elapsed=time.monotonic()-start
        if timeout > 0 and elapsed >= timeout:
            return ImageMatchResult(False,score,elapsed)
        sleep_for=max(0.05,float(interval))
        if stop_event is None:
            time.sleep(sleep_for)
        else:
            stop_event.wait(sleep_for)
