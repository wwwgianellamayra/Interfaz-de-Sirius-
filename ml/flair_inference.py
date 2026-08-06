from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import numpy as np
import segmentation_models_pytorch as smp
import torch
from PIL import Image

MODEL_SIZE = 512
MEAN = np.array([105.08, 110.87, 101.82], dtype=np.float32)
STD = np.array([52.17, 45.38, 44.00], dtype=np.float32)
GREEN_COLOR = np.array([125, 255, 175], dtype=np.float32)
URBAN_COLOR = np.array([255, 150, 150], dtype=np.float32)
OVERLAY_ALPHA = 0.38

# Índices internos (base 0) del checkpoint FLAIR.
# Verde: coniferous, deciduous, brushwood, vineyard,
# herbaceous vegetation, agricultural land.
GREEN_INDICES = {5, 6, 7, 8, 9, 10}
# Urbano: building + impervious surface.
URBAN_INDICES = {0, 2}


@dataclass(frozen=True)
class SegmentationResult:
    green_percentage: float
    urban_percentage: float
    other_percentage: float
    mask_path: Path
    overlay_path: Path


class FlairSegmenter:
    """Carga FLAIR una sola vez y procesa imágenes RGB."""

    def __init__(self, weights_path: Path) -> None:
        self.weights_path = Path(weights_path)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model: torch.nn.Module | None = None
        self._lock = Lock()

    def _create_model(self) -> torch.nn.Module:
        return smp.DeepLabV3(
            encoder_name="resnet34",
            encoder_weights=None,
            in_channels=3,
            classes=19,
        )

    @staticmethod
    def _extract_state_dict(checkpoint: object) -> dict[str, torch.Tensor]:
        if isinstance(checkpoint, dict):
            for key in ("state_dict", "model_state_dict", "model"):
                candidate = checkpoint.get(key)
                if isinstance(candidate, dict):
                    checkpoint = candidate
                    break

        if not isinstance(checkpoint, dict):
            raise TypeError("El archivo de pesos no contiene un state_dict reconocible.")

        cleaned: dict[str, torch.Tensor] = {}
        prefixes = ("seg_model.", "model.", "module.", "net.")

        for key, value in checkpoint.items():
            if key.startswith("criterion."):
                continue

            cleaned_key = key
            changed = True
            while changed:
                changed = False
                for prefix in prefixes:
                    if cleaned_key.startswith(prefix):
                        cleaned_key = cleaned_key[len(prefix):]
                        changed = True
                        break
            cleaned[cleaned_key] = value
        return cleaned

    def load(self) -> None:
        if self._model is not None:
            return
        if not self.weights_path.is_file():
            raise FileNotFoundError(
                f"No se encontró el modelo FLAIR en: {self.weights_path}"
            )

        with self._lock:
            if self._model is not None:
                return
            model = self._create_model()
            checkpoint = torch.load(
                self.weights_path,
                map_location=self.device,
                weights_only=False,
            )
            state_dict = self._extract_state_dict(checkpoint)
            model.load_state_dict(state_dict, strict=True)
            model.to(self.device)
            model.eval()
            self._model = model

    def analyze(self, image_path: Path, output_dir: Path) -> SegmentationResult:
        self.load()
        assert self._model is not None

        original = Image.open(image_path).convert("RGB")
        resized = original.resize((MODEL_SIZE, MODEL_SIZE), Image.Resampling.BILINEAR)
        image_array = np.asarray(resized, dtype=np.float32)
        normalized = (image_array - MEAN) / STD
        tensor = torch.from_numpy(normalized.transpose(2, 0, 1)).unsqueeze(0)
        tensor = tensor.to(self.device)

        with self._lock, torch.inference_mode():
            logits = self._model(tensor)
            if isinstance(logits, dict):
                logits = logits["out"]
            prediction = torch.argmax(logits, dim=1).squeeze(0).cpu().numpy()

        green_mask = np.isin(prediction, list(GREEN_INDICES))
        urban_mask = np.isin(prediction, list(URBAN_INDICES))
        other_mask = ~(green_mask | urban_mask)
        total = prediction.size

        green = float(green_mask.sum() * 100.0 / total)
        urban = float(urban_mask.sum() * 100.0 / total)
        other = float(other_mask.sum() * 100.0 / total)

        output_dir.mkdir(parents=True, exist_ok=True)
        stem = image_path.stem
        mask_path = output_dir / f"{stem}_mask.png"
        overlay_path = output_dir / f"{stem}_overlay.png"

        overlay = image_array.copy()
        overlay[green_mask] = (
            image_array[green_mask] * (1.0 - OVERLAY_ALPHA)
            + GREEN_COLOR * OVERLAY_ALPHA
        )
        overlay[urban_mask] = (
            image_array[urban_mask] * (1.0 - OVERLAY_ALPHA)
            + URBAN_COLOR * OVERLAY_ALPHA
        )
        overlay = np.clip(overlay, 0, 255).astype(np.uint8)

        color_mask = np.zeros((MODEL_SIZE, MODEL_SIZE, 3), dtype=np.uint8)
        color_mask[green_mask] = GREEN_COLOR.astype(np.uint8)
        color_mask[urban_mask] = URBAN_COLOR.astype(np.uint8)

        Image.fromarray(color_mask).save(mask_path)
        Image.fromarray(overlay).save(overlay_path)

        return SegmentationResult(
            green_percentage=green,
            urban_percentage=urban,
            other_percentage=other,
            mask_path=mask_path,
            overlay_path=overlay_path,
        )
