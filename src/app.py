import base64
import os
from pathlib import Path

import modal
import modal.experimental

from .llm import LLMServer
from .llm import app as llm_app
from .utils import (
    CHARACTER_MAPPING,
    SPECIAL_MOVES,
    create_messages,
    minutes,
    region,
)
from .yolo import YOLOServer
from .yolo import app as yolo_app

# diambra engine

engine_app = modal.App.lookup("sf3-engine", create_if_missing=True)

engine_image = (
    modal.experimental.raw_registry_image("docker.io/diambra/engine:v2.2.4")
    .env(
        {
            "HOME": "/tmp",
        }
    )
    .entrypoint([])
    # since sandbox is created in app, files will be in Modal container, not locally
    # so we need to add them to the web app image as well
    .add_local_file(
        "/root/assets/sfiii3n.zip",
        "/opt/diambraArena/roms/sfiii3n.zip",
    )
    .add_local_file(
        "/root/assets/credentials",
        "/tmp/.diambra/credentials",
    )
)

# web app

app = modal.App(name="sf3").include(llm_app).include(yolo_app)

local_assets_dir = Path(__file__).parent.parent / "assets"
remote_frontend_dir = "/root/frontend"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "ffmpeg",
    )
    .pip_install("uv")
    .run_commands(
        "uv pip install --system --compile-bytecode diambra-arena==2.2.7 diambra==0.0.20 fastapi[standard]==0.116.1 websockets==15.0.1 numpy==2.3.1",
    )
    .add_local_dir(Path(__file__).parent / "frontend", remote_frontend_dir)
    .add_local_file(
        Path(__file__).parent.parent / "assets" / "favicon.ico",
        "/root/frontend/favicon.ico",
    )
    .add_local_file(
        Path(__file__).parent.parent / "assets" / "logo.svg",
        "/root/frontend/logo.svg",
    )
    .add_local_file(
        local_assets_dir / "sfiii3n.zip",
        "/root/assets/sfiii3n.zip",
    )
    .add_local_file(
        local_assets_dir / "credentials",
        "/root/assets/credentials",
    )
)

max_inputs = 1000


@app.cls(
    image=image,
    scaledown_window=15 * minutes,
    timeout=5 * minutes,
    region=region,
)
@modal.concurrent(max_inputs=max_inputs)
class Web:
    @modal.enter()
    def enter(
        self,
    ):
        # assign llm and yolo to self so multiple container inputs can share them
        # initially set to None so they don't block page load, amortized by user interacting with settings
        self.llm = None
        self.yolo = None

    async def create_llm(self):
        print("Creating LLM...")
        if self.llm is None:
            self.llm = LLMServer()
            await self.llm.boot.remote.aio()
        print("LLM created")

    async def create_yolo(self):
        print("Creating YOLO...")
        if self.yolo is None:
            self.yolo = YOLOServer()
            await self.yolo.boot.remote.aio()
        print("YOLO created")

    @modal.asgi_app()
    def app(self):
        import asyncio
        import traceback

        import cv2
        import diambra.arena as arena
        import numpy as np
        from diambra.arena import EnvironmentSettingsMultiAgent, Roles, SpaceTypes
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles

        web_app = FastAPI()

        async def create_sandbox() -> (
            modal.Sandbox
        ):  # async to avoid blocking event loop
            print("Creating sandbox...")
            engine_port = 50051
            sandbox = modal.Sandbox.create(
                "/bin/diambraEngineServer",
                app=engine_app,
                image=engine_image,
                timeout=5 * minutes,
                region=region,
                unencrypted_ports=[engine_port],
                verbose=True,
            )
            tunnels = sandbox.tunnels()
            tunnel = tunnels[engine_port]
            host, port = tunnel.tcp_socket
            os.environ["DIAMBRA_ENVS"] = f"{host}:{port}"
            print(f"Created sandbox {sandbox.object_id} at {host}:{port}")
            return sandbox

        def make_json_safe(obj):
            if isinstance(obj, dict):
                return {k: make_json_safe(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_json_safe(v) for v in obj]
            elif isinstance(obj, tuple):
                return tuple(make_json_safe(v) for v in obj)
            elif isinstance(obj, np.ndarray):
                return make_json_safe(obj.tolist())
            elif hasattr(obj, "__dict__"):
                return make_json_safe(vars(obj))
            else:
                return obj

        @web_app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            print("Client connected")

            # game state

            env = None
            game_running = False
            game_settings = {
                "difficulty": 1,
                "player1": {
                    "character": "Ken",
                    "outfit": 1,
                    "superArt": 1,
                },
                "player2": {
                    "character": "Ken",
                    "outfit": 1,
                    "superArt": 1,
                },
            }
            game_state = {
                "status": "initializing",
                "scores": [0, 0],
                "winner": "",
                "error": "",
            }

            # boot up

            _, _, sandbox = await asyncio.gather(
                self.create_llm(),
                self.create_yolo(),
                create_sandbox(),
            )

            # per frame

            observation = None
            info = None
            current_direction = ""
            player1_action = 0
            player2_action = 0

            # game duration

            player1_next_moves = []  # necessary since some actions require multiple moves
            player2_next_moves = []
            actions = {"agent_0": 0, "agent_1": 0}

            outbound_message_queue = asyncio.Queue()
            stop_event = asyncio.Event()

            # concurrent loops

            async def process_inbound_messages():
                nonlocal \
                    stop_event, \
                    game_running, \
                    game_settings, \
                    player1_action, \
                    player1_next_moves, \
                    observation

                try:
                    while not stop_event.is_set():
                        data = await websocket.receive_json()
                        message_type = data.get("type", "unknown")

                        if message_type == "start_game":
                            print(f"Received start_game message: {data}")
                            if not game_running:
                                received_settings = data.get("data", {})
                                if received_settings:
                                    game_settings.update(received_settings)
                                game_running = True
                        elif message_type == "player_action":
                            action = data.get("data", {}).get("action", 0)

                            if action == 18 and observation is not None:
                                p1_character = CHARACTER_MAPPING[
                                    observation["P1"]["character"]
                                ]
                                p1_super_art = game_settings["player1"]["superArt"]
                                p1_side = observation["P1"]["side"]
                                p1_direction = "left" if p1_side == 0 else "right"
                                p1_super_count = observation["P1"]["super_count"][0]

                                best_move_key = str(p1_super_art)
                                max_bars_used = 1

                                for move_key in SPECIAL_MOVES[p1_character].keys():
                                    if isinstance(move_key, str):
                                        bars_required = 1
                                        if move_key.startswith("Max"):
                                            for i in range(1, 4):
                                                if f"(uses {i} bars)" in move_key:
                                                    bars_required = i
                                                    break

                                            if (
                                                p1_super_count >= bars_required
                                                and bars_required > max_bars_used
                                            ):
                                                if move_key.startswith(
                                                    f"Max-{p1_super_art}"
                                                ):
                                                    best_move_key = move_key
                                                    max_bars_used = bars_required
                                                elif not any(
                                                    move_key.startswith(f"Max-{i}")
                                                    for i in [1, 2, 3]
                                                ):
                                                    best_move_key = move_key
                                                    max_bars_used = bars_required

                                player1_next_moves.extend(
                                    SPECIAL_MOVES[p1_character][best_move_key][
                                        p1_direction
                                    ]
                                )
                            else:
                                player1_action = action

                except WebSocketDisconnect:
                    print("WebSocket disconnected in message processor")
                    stop_event.set()

                except Exception:
                    print(f"Error in message processor: {traceback.format_exc()}")
                    stop_event.set()

            async def process_outbound_messages():
                nonlocal stop_event, outbound_message_queue

                try:
                    while not stop_event.is_set():
                        message = await outbound_message_queue.get()
                        print(f"Sending game state: {message}")
                        await websocket.send_json(message)

                except WebSocketDisconnect:
                    print("WebSocket disconnected in outgoing processor")
                    stop_event.set()

                except Exception:
                    print(f"Error in outgoing processor: {traceback.format_exc()}")
                    stop_event.set()

            async def run_robot_background():
                nonlocal \
                    game_running, \
                    observation, \
                    info, \
                    game_settings, \
                    current_direction, \
                    player2_action, \
                    player2_next_moves, \
                    stop_event

                try:
                    while not stop_event.is_set():
                        if not game_running or observation is None:
                            await asyncio.sleep(0.001)
                            continue

                        await asyncio.sleep(0.001)

                        # plan

                        if len(player2_next_moves) == 0:
                            obs_p1 = observation["P1"]
                            obs_p2 = observation["P2"]

                            (
                                boxes,
                                class_ids,
                            ) = await self.yolo.detect_characters.remote.aio(
                                [obs_p1["character"], obs_p2["character"]],
                                observation["frame"],
                            )

                            player2_character = CHARACTER_MAPPING[obs_p2["character"]]
                            player2_side = obs_p2["side"] if obs_p2 else 0

                            messages = create_messages(
                                stage=observation["stage"][0],
                                timer=observation["timer"][0],
                                boxes=boxes,
                                class_ids=class_ids,
                                player1_character=CHARACTER_MAPPING[
                                    obs_p1["character"]
                                ],
                                player1_super_art=game_settings["player1"]["superArt"],
                                player1_wins=obs_p1["wins"][0],
                                player1_side=obs_p1["side"],
                                player1_stunned=obs_p1["stunned"],
                                player1_stun_bar=obs_p1["stun_bar"][0],
                                player1_health=obs_p1["health"][0],
                                player1_super_count=obs_p1["super_count"][0],
                                player1_super_bar=obs_p1["super_bar"][0],
                                player2_character=player2_character,
                                player2_super_art=game_settings["player2"]["superArt"],
                                player2_wins=obs_p2["wins"][0],
                                player2_side=player2_side,
                                player2_stunned=obs_p2["stunned"],
                                player2_stun_bar=obs_p2["stun_bar"][0],
                                player2_health=obs_p2["health"][0],
                                player2_super_count=obs_p2["super_count"][0],
                                player2_super_bar=obs_p2["super_bar"][0],
                            )
                            moves = await self.llm.chat.remote.aio(
                                messages,
                                player2_character,
                                player2_side,
                            )
                            player2_next_moves.extend(moves)

                        # act

                        if len(player2_next_moves) > 0:
                            player2_action = player2_next_moves.pop(0)

                except WebSocketDisconnect:
                    print("WebSocket disconnected in robot background")
                    stop_event.set()

                except Exception:
                    print(f"Error in robot background: {traceback.format_exc()}")
                    stop_event.set()

            async def run_game_loop():
                nonlocal \
                    sandbox, \
                    stop_event, \
                    env, \
                    game_running, \
                    game_settings, \
                    game_state, \
                    observation, \
                    info, \
                    current_direction, \
                    player1_action, \
                    player2_action, \
                    player1_next_moves, \
                    player2_next_moves, \
                    actions, \
                    outbound_message_queue

                try:
                    while not stop_event.is_set():
                        if not game_running:
                            await asyncio.sleep(0.001)
                            continue

                        print("Creating DIAMBRA environment...")
                        settings = EnvironmentSettingsMultiAgent(
                            step_ratio=1,
                            role=(Roles.P1, Roles.P2),
                            disable_keyboard=False,
                            render_mode="rgb_array",
                            splash_screen=False,
                            grpc_timeout=1 * minutes,
                            difficulty=game_settings["difficulty"],
                            action_space=(SpaceTypes.DISCRETE, SpaceTypes.DISCRETE),
                            characters=[
                                game_settings["player1"]["character"],
                                game_settings["player2"]["character"],
                            ],
                            outfits=[
                                game_settings["player1"]["outfit"],
                                game_settings["player2"]["outfit"],
                            ],
                            super_art=[
                                game_settings["player1"]["superArt"],
                                game_settings["player2"]["superArt"],
                            ],
                        )
                        env = arena.make("sfiii3n", settings)
                        print("DIAMBRA environment created successfully!")

                        game_state["status"] = "running"
                        await outbound_message_queue.put(
                            {"type": "game_state", "data": make_json_safe(game_state)}
                        )

                        observation, info = env.reset()

                        # game loop

                        # according to https://docs.diambra.ai/envs/games/
                        # SF3 runs at 164 FPS natively, but we want 60 FPS output
                        target_fps = 60.0
                        frame_interval = 1.0 / target_fps
                        next_frame_time = asyncio.get_event_loop().time()

                        while game_running and not stop_event.is_set():
                            current_time = asyncio.get_event_loop().time()
                            sleep_time = next_frame_time - current_time
                            if sleep_time > 0:
                                await asyncio.sleep(sleep_time)
                            else:
                                await asyncio.sleep(0)
                            next_frame_time += frame_interval

                            if len(player1_next_moves) > 0:
                                player1_action = player1_next_moves.pop(0)

                            actions = {
                                "agent_0": player1_action,
                                "agent_1": player2_action,
                            }

                            (
                                observation,
                                reward,
                                terminated,
                                truncated,
                                info,
                            ) = env.step(actions)

                            if (
                                "frame" in observation
                                and observation["frame"] is not None
                            ):
                                frame = cv2.cvtColor(
                                    observation["frame"], cv2.COLOR_RGB2BGR
                                )
                                _, buffer = cv2.imencode(
                                    ".jpg",
                                    frame,
                                    [
                                        cv2.IMWRITE_JPEG_QUALITY,
                                        60,
                                    ],
                                )
                                frame_b64 = base64.b64encode(buffer).decode("utf-8")
                                await websocket.send_json(
                                    {"type": "game_frame", "data": {"frame": frame_b64}}
                                )  # not using outbound queue for speed + send frame immediately

                            if terminated or truncated:
                                p1_wins = observation["P1"]["wins"][0]
                                p2_wins = observation["P2"]["wins"][0]
                                print(f"Game finished - P1: {p1_wins}, P2: {p2_wins}")

                                if p1_wins > p2_wins:
                                    game_state["scores"][0] += 1
                                    winner = "Player 1 (You)"
                                elif p2_wins > p1_wins:
                                    game_state["scores"][1] += 1
                                    winner = "Player 2 (AI)"
                                else:
                                    winner = "Draw"

                                game_state["status"] = "finished"
                                game_state["winner"] = winner
                                await outbound_message_queue.put(
                                    {
                                        "type": "game_state",
                                        "data": make_json_safe(game_state),
                                    }
                                )

                                # reset game state

                                print(f"Terminating sandbox {sandbox.object_id}")
                                sandbox.terminate()
                                sandbox = await create_sandbox()

                                try:
                                    env.close()
                                except Exception:
                                    print(
                                        "Warning: couldn't close environment after game"
                                    )
                                finally:
                                    env = None

                                game_running = False

                                game_state = {
                                    "status": "initializing",
                                    "scores": [0, 0],
                                    "winner": "",
                                    "error": "",
                                }

                                await outbound_message_queue.put(
                                    {
                                        "type": "game_state",
                                        "data": make_json_safe(game_state),
                                    }
                                )

                                current_direction = ""
                                player1_action = 0
                                player2_action = 0

                                player1_next_moves = []
                                player2_next_moves = []
                                actions = {"agent_0": 0, "agent_1": 0}

                except WebSocketDisconnect:
                    print("WebSocket disconnected in game loop")
                    stop_event.set()

                except Exception:
                    print(f"Error in game loop: {traceback.format_exc()}")
                    stop_event.set()

            await outbound_message_queue.put(
                {"type": "game_state", "data": make_json_safe(game_state)}
            )

            tasks = [
                asyncio.create_task(process_inbound_messages()),
                asyncio.create_task(process_outbound_messages()),
                asyncio.create_task(run_robot_background()),
                asyncio.create_task(run_game_loop()),
            ]
            try:
                await asyncio.gather(*tasks)

            except WebSocketDisconnect:
                print("Client disconnected")
                stop_event.set()
                game_running = False
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

            except Exception as e:
                print(f"WebSocket error: {e}")
                stop_event.set()
                game_running = False
                game_state["status"] = "error"
                game_state["error"] = str(e)
                try:
                    await outbound_message_queue.put(
                        {"type": "game_state", "data": make_json_safe(game_state)}
                    )
                except Exception:
                    print("Warning: could not send error message")
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

            finally:
                print("Cleaning up resources...")
                if env:
                    try:
                        env.close()
                    except Exception:
                        print("Warning: could not close environment")
                    finally:
                        env = None
                if sandbox:
                    print(f"Terminating sandbox {sandbox.object_id}")
                    sandbox.terminate()
                    sandbox = None

        @web_app.get("/")
        async def index():
            return FileResponse(f"{remote_frontend_dir}/index.html")

        @web_app.get("/favicon.ico")
        async def favicon():
            return FileResponse(f"{remote_frontend_dir}/favicon.ico")

        @web_app.get("/logo.svg")
        async def logo():
            return FileResponse(f"{remote_frontend_dir}/logo.svg")

        web_app.mount("/", StaticFiles(directory=remote_frontend_dir), name="static")

        return web_app
