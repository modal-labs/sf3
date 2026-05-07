from __future__ import annotations

from typing import Sequence

from .utils import parse_move


def resolve_move_with_fallback(
    character: str,
    move_name: str,
    side: int,
) -> tuple[list[int], str]:
    move_sequence = parse_move(character, move_name, side)
    if move_sequence is not None:
        return move_sequence, move_name
    return [0], "No-Move"


def postprocess_character_detections(
    predictions,
    character_ids: Sequence[int],
    confidence_threshold: float,
    input_width: int,
    input_height: int,
    img_width: int,
    img_height: int,
) -> tuple[list[list[float]], list[int]]:
    import numpy as np

    if predictions.size == 0:
        return [[0.0, 0.0, 0.0, 0.0] for _ in character_ids], [
            -1 for _ in character_ids
        ]

    scores = predictions[:, 4]
    class_ids = predictions[:, 5].astype(int)

    confidence_mask = scores >= confidence_threshold
    predictions = predictions[confidence_mask]
    scores = scores[confidence_mask]
    class_ids = class_ids[confidence_mask]

    character_mask = np.isin(class_ids, character_ids)
    filtered_predictions = predictions[character_mask]
    filtered_scores = scores[character_mask]
    filtered_class_ids = class_ids[character_mask]

    final_predictions = []
    final_class_ids = []
    for char_id in character_ids:
        char_mask = filtered_class_ids == char_id
        if np.any(char_mask):
            char_predictions = filtered_predictions[char_mask]
            char_scores = filtered_scores[char_mask]
            best_idx = int(np.argmax(char_scores))
            final_predictions.append(char_predictions[best_idx])
            final_class_ids.append(char_id)
        else:
            final_predictions.append(np.array([0, 0, 0, 0, 0, -1], dtype=np.float32))
            final_class_ids.append(-1)

    final_predictions_np = np.array(final_predictions)
    boxes = final_predictions_np[:, :4]
    input_shape = np.array([input_width, input_height, input_width, input_height])
    boxes = np.divide(boxes, input_shape, dtype=np.float32)
    boxes *= np.array([img_width, img_height, img_width, img_height])

    boxes[:, 0] = np.clip(boxes[:, 0], 0, img_width)
    boxes[:, 1] = np.clip(boxes[:, 1], 0, img_height)
    boxes[:, 2] = np.clip(boxes[:, 2], 0, img_width)
    boxes[:, 3] = np.clip(boxes[:, 3], 0, img_height)

    return boxes.tolist(), final_class_ids
