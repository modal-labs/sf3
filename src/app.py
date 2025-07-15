import base64
import os
import random
from pathlib import Path

import modal
import modal.experimental

minutes = 60

# diambra engine

engine_app = modal.App.lookup("diambra-llm-engine", create_if_missing=True)

engine_image = (
    modal.experimental.raw_registry_image("docker.io/diambra/engine:v2.2.4")
    .env(
        {
            "HOME": "/tmp",
        }
    )
    .entrypoint([])
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

app = modal.App(name="diambra-llm-web")

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
        local_assets_dir / "sfiii3n.zip",
        "/root/assets/sfiii3n.zip",
    )
    .add_local_file(
        local_assets_dir / "credentials",
        "/root/assets/credentials",
    )
)

region = "us-east-1"


@app.cls(
    image=image,
    scaledown_window=15 * minutes,
    timeout=5 * minutes,
    region=region,
)
class GameManager:
    @modal.enter()
    def enter(self):
        self.active_sandboxes = set()

    @modal.exit()
    def exit(self):
        print("Cleaning up all active sandboxes")
        for sandbox_id in list(self.active_sandboxes):
            print(f"Terminating remaining sandbox {sandbox_id}")
        self.active_sandboxes.clear()

    @modal.asgi_app()
    def web(self):
        import asyncio

        import cv2
        import diambra.arena as arena
        import numpy as np
        from diambra.arena import EnvironmentSettingsMultiAgent, Roles, SpaceTypes
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles

        web_app = FastAPI()

        def create_sandbox() -> modal.Sandbox:
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
            self.active_sandboxes.add(sandbox.object_id)
            os.environ["DIAMBRA_ENVS"] = f"{host}:{port}"
            print(f"Created sandbox {sandbox.object_id} at {host}:{port}")
            return sandbox

        @web_app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            print("Client connected")

            # game state

            sandbox = create_sandbox()
            game_running = False
            stop_event = asyncio.Event()
            message_queue = asyncio.Queue()
            player1_action = 0
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
                "status": "idle",
                "scores": [0, 0],
            }
            env = None

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

            safe_state = make_json_safe(game_state)
            await websocket.send_json({"type": "game_state", "data": safe_state})

            # blocking fns

            def create_environment(game_settings):
                settings = EnvironmentSettingsMultiAgent(
                    role=(Roles.P1, Roles.P2),
                    disable_keyboard=False,
                    render_mode="rgb_array",
                    splash_screen=False,
                    grpc_timeout=1 * minutes,
                    difficulty=game_settings.get("difficulty", 8),
                    action_space=(SpaceTypes.DISCRETE, SpaceTypes.DISCRETE),
                    characters=[
                        game_settings.get("player1", {}).get("character", "Ken"),
                        game_settings.get("player2", {}).get("character", "Ken"),
                    ],
                    outfits=[
                        game_settings.get("player1", {}).get("outfit", 1),
                        game_settings.get("player2", {}).get("outfit", 1),
                    ],
                    super_art=[
                        game_settings.get("player1", {}).get("superArt", 1),
                        game_settings.get("player2", {}).get("superArt", 1),
                    ],
                )
                return arena.make("sfiii3n", settings)

            def encode_frame(frame):
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                return base64.b64encode(buffer).decode("utf-8")

            # concurrent loops

            async def process_websocket_messages():
                nonlocal game_running, player1_action, game_settings
                try:
                    while not stop_event.is_set():
                        data = await websocket.receive_json()
                        message_type = data.get("type", "unknown")

                        if message_type == "start_game":
                            if not game_running:
                                received_settings = data.get("data", {})
                                if received_settings:
                                    game_settings.update(received_settings)
                                    print(f"Updated game settings: {game_settings}")
                                game_running = True
                        elif message_type == "player_action":
                            action = data.get("data", {}).get("action", 0)
                            player1_action = action
                except WebSocketDisconnect:
                    print("WebSocket disconnected in message processor")
                    stop_event.set()
                except Exception as e:
                    print(f"Error in message processor: {e}")
                    stop_event.set()

            async def process_outgoing_messages():
                try:
                    while not stop_event.is_set():
                        try:
                            message = await asyncio.wait_for(
                                message_queue.get(), timeout=0.1
                            )
                            await websocket.send_json(message)
                        except asyncio.TimeoutError:
                            continue
                except WebSocketDisconnect:
                    print("WebSocket disconnected in outgoing processor")
                    stop_event.set()
                except Exception as e:
                    print(f"Error in outgoing processor: {e}")
                    stop_event.set()

            async def run_game_loop():
                nonlocal game_running, game_state, env, sandbox

                try:
                    while not stop_event.is_set():
                        await asyncio.sleep(0.0167)  # 60 FPS

                        if not game_running:
                            continue

                        if sandbox is None:
                            sandbox = create_sandbox()

                        print("Creating DIAMBRA environment...")
                        game_state["status"] = "initializing"
                        await message_queue.put(
                            {"type": "game_state", "data": make_json_safe(game_state)}
                        )
                        env = await asyncio.get_event_loop().run_in_executor(
                            None, create_environment, game_settings
                        )
                        print("DIAMBRA environment created successfully!")

                        print("Starting game...")
                        game_state["status"] = "running"
                        await message_queue.put(
                            {"type": "game_state", "data": make_json_safe(game_state)}
                        )
                        (
                            observations,
                            info,
                        ) = await asyncio.get_event_loop().run_in_executor(
                            None, env.reset
                        )

                        # game loop

                        while game_running and not stop_event.is_set():
                            actions = {
                                "agent_0": player1_action,
                                "agent_1": random.randint(0, 17),
                            }

                            (
                                observations,
                                rewards,
                                terminated,
                                truncated,
                                info,
                            ) = await asyncio.get_event_loop().run_in_executor(
                                None, env.step, actions
                            )

                            if (
                                "frame" in observations
                                and observations["frame"] is not None
                            ):
                                frame_b64 = (
                                    await asyncio.get_event_loop().run_in_executor(
                                        None, encode_frame, observations["frame"]
                                    )
                                )
                                await message_queue.put(
                                    {"type": "game_frame", "data": {"frame": frame_b64}}
                                )

                            if terminated or truncated:
                                game_state["status"] = "finished"
                                p1_wins = observations.get("P1", {}).get("wins", [0])[0]
                                p2_wins = observations.get("P2", {}).get("wins", [0])[0]
                                print(f"Game finished - P1: {p1_wins}, P2: {p2_wins}")

                                if p1_wins > p2_wins:
                                    game_state["scores"][0] += 1
                                    winner = "Player 1 (You)"
                                elif p2_wins > p1_wins:
                                    game_state["scores"][1] += 1
                                    winner = "Player 2 (AI)"
                                else:
                                    winner = "Draw"

                                game_state["winner"] = winner
                                await websocket.send_json(
                                    {
                                        "type": "game_state",
                                        "data": make_json_safe(game_state),
                                    }
                                )

                                game_state = {
                                    "status": "idle",
                                    "scores": game_state["scores"],
                                }
                                await websocket.send_json(
                                    {
                                        "type": "game_state",
                                        "data": make_json_safe(game_state),
                                    }
                                )

                                try:
                                    await asyncio.get_event_loop().run_in_executor(
                                        None, env.close
                                    )
                                    env = None
                                except Exception as e:
                                    print(f"Error closing environment after game: {e}")
                                    env = None

                                if sandbox:
                                    try:
                                        print(
                                            f"Terminating sandbox {sandbox.object_id}"
                                        )
                                        self.active_sandboxes.discard(sandbox.object_id)
                                        sandbox.terminate()
                                        sandbox = None
                                    except Exception as e:
                                        print(
                                            f"Error terminating sandbox after game: {e}"
                                        )
                                        sandbox = None

                                game_running = False
                except WebSocketDisconnect:
                    print("WebSocket disconnected in game loop")
                    stop_event.set()
                except Exception as e:
                    print(f"Error in game loop: {e}")
                    stop_event.set()

            tasks = [
                asyncio.create_task(run_game_loop()),
                asyncio.create_task(process_websocket_messages()),
                asyncio.create_task(process_outgoing_messages()),
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
                    await websocket.send_json(
                        {"type": "game_state", "data": make_json_safe(game_state)}
                    )
                except Exception:
                    print("Could not send error message")
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                print("Cleaning up resources...")
                if env:
                    try:
                        await asyncio.get_event_loop().run_in_executor(None, env.close)
                    except Exception as e:
                        print(f"Error closing environment: {e}")
                if sandbox:
                    try:
                        print(f"Terminating sandbox {sandbox.object_id}")
                        self.active_sandboxes.discard(sandbox.object_id)
                        sandbox.terminate()
                    except Exception as e:
                        print(f"Error terminating sandbox: {e}")

        @web_app.get("/")
        async def index():
            return FileResponse(f"{remote_frontend_dir}/index.html")

        web_app.mount("/", StaticFiles(directory=remote_frontend_dir), name="static")

        return web_app
