import asyncio
import json

import aiohttp
import torch

from src.utils import (
    get_available_instructions_for_character,
    parse_move,
)


async def compute_reward_async(
    data_source: str, solution_str: str, ground_truth: str, extra_info: dict
) -> float:
    print("Parsing move...")

    messages = extra_info["messages"]
    character = extra_info["character"]
    super_art = extra_info["super_art"]
    super_count = extra_info["super_count"]
    side = extra_info["side"]

    available_instructions = get_available_instructions_for_character(
        character, super_art, super_count
    )

    try:
        move_name = solution_str.split("</think>")[1].strip()
        move_sequence = parse_move(character, move_name, side)
        if move_sequence is None:
            raise ValueError(f"Invalid move: {move_name}")
        if move_name not in available_instructions:
            raise ValueError(f"Move {move_name} not in available instructions")
    except Exception as e:
        print(f"Error parsing move: {e}")
        return 0.0
    print(f"Move parsed: {move_name}")

    url = "https://modal-labs-examples--sf3-rm-rmserver-chat.modal.run"
    headers = {"Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:

        async def fetch_score(session, data):
            async with session.post(url, data=data, headers=headers) as resp:
                return await resp.json()

        tasks = []
        for instruction in available_instructions:
            temp_messages = messages.copy()
            temp_messages.append(
                {
                    "role": "assistant",
                    "content": instruction,
                }
            )
            data = json.dumps(temp_messages)

            tasks.append(fetch_score(session, data))

        scores = await asyncio.gather(*tasks)

    move_name_idx = available_instructions.index(move_name)
    pred_score = scores[move_name_idx]

    scores_tensor = torch.tensor(scores)
    mask = torch.arange(len(scores_tensor)) != move_name_idx
    diffs = pred_score - scores_tensor[mask]
    preferences = torch.sigmoid(diffs)

    return preferences.mean().item()


def compute_reward(
    data_source: str, solution_str: str, ground_truth: str, extra_info: dict
) -> float:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            compute_reward_async(data_source, solution_str, ground_truth, extra_info)
        )
    finally:
        loop.close()
