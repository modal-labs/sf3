import os
from pathlib import Path

import modal
import modal.experimental

from .llm import LLMServer
from .llm import app as llm_app
from .utils import (
    CHARACTER_TO_ID,
    COMBOS,
    SPECIAL_MOVES,
    GameInfo,
    PlayerState,
    create_messages,
    gb,
    minutes,
    region,
)
from .yolo import YOLOServer
from .yolo import app as yolo_app

# Modal setup

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
        "/root/sfiii3n.zip",
        "/opt/diambraArena/roms/sfiii3n.zip",
    )
    .add_local_file(
        "/root/credentials",
        "/tmp/.diambra/credentials",
    )
)

# web app
app = modal.App(name="sf3").include(llm_app).include(yolo_app)

local_assets_dir = Path(__file__).parent.parent / "assets"
local_engine_dir = local_assets_dir / "engine"

remote_frontend_dir = "/root/frontend"
remote_icons_dir = "/root/icons"
remote_logos_dir = "/root/logos"
remote_outfits_dir = "/root/outfits"
remote_portraits_dir = "/root/portraits"
remote_sounds_dir = "/root/sounds"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "ffmpeg",
    )
    .uv_pip_install(
        "diambra==0.0.20",
        "diambra-arena==2.2.7",
        "fastapi[standard]==0.116.1",
        "numpy==2.3.1",
        "websockets==15.0.1",
    )
    # engine
    .add_local_file(
        local_engine_dir / "sfiii3n.zip",
        "/root/sfiii3n.zip",
    )
    .add_local_file(
        local_engine_dir / "credentials",
        "/root/credentials",
    )
    # frontend
    .add_local_dir(Path(__file__).parent / "frontend", remote_frontend_dir)
    .add_local_dir(
        local_assets_dir / "icons",
        remote_icons_dir,
    )
    .add_local_dir(
        local_assets_dir / "logos",
        remote_logos_dir,
    )
    .add_local_dir(
        local_assets_dir / "outfits",
        remote_outfits_dir,
    )
    .add_local_dir(
        local_assets_dir / "portraits",
        remote_portraits_dir,
    )
    .add_local_dir(
        local_assets_dir / "sounds",
        remote_sounds_dir,
    )
)

# inference

max_inputs = 1
cpu = 2
memory = 2 * gb


@app.cls(
    image=image,
    cpu=cpu,
    memory=memory,
    region=region,
    scaledown_window=60 * minutes,
    timeout=24 * 60 * minutes,
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

    async def create_llm(self):  # async to avoid blocking event loop
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

    @modal.asgi_app(custom_domains=["sf3.modal.dev"])
    def app(self):
        import asyncio
        import json
        import traceback

        import cv2
        import diambra.arena as arena
        import numpy as np
        from diambra.arena import EnvironmentSettingsMultiAgent, Roles, SpaceTypes
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles

        web_app = FastAPI()

        # helper fns

        async def create_sandbox() -> modal.Sandbox:
            print("Creating sandbox...")
            engine_port = 50051
            sandbox = modal.Sandbox.create(
                "/bin/diambraEngineServer",
                app=engine_app,
                image=engine_image,
                timeout=60 * minutes,
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

        class NumpyJSONEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                if hasattr(obj, "__dict__"):
                    return vars(obj)
                return super().default(obj)

        def make_json_safe(obj):
            return json.loads(json.dumps(obj, cls=NumpyJSONEncoder))

        def create_initial_game_state():
            return {
                "status": "initializing",
                "scores": [0, 0],
                "winner": "",
                "error": "",
            }

        # manages game state and communication

        class GameSession:
            def __init__(self, websocket: WebSocket):
                self.websocket = websocket

                # game state

                self.env = None
                self.sandbox = None
                self.game_running = False
                self.game_settings = {
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
                    "humanVsLlm": True,
                    "gamepadConnected": False,
                    "difficulty": "expert",
                }
                self.game_state = create_initial_game_state()

                # per frame state

                self.observation = None
                self.info = None

                # transition state

                self.in_transition = False
                self.transition_start_time = None
                self.transition_duration = 3.0  # seconds, matches frontend
                self.pending_game_end = False
                self.game_end_data = None

                # game duration state

                self.player1_next_buttons = []
                self.player2_next_buttons = []
                self.next_buttons_limit = (
                    20  # simply for memory, roughly length of longest combo
                )
                self.player1_current_action = 0
                self.actions = {"agent_0": 0, "agent_1": 0}

                self.prev_player1_state = None
                self.prev_player2_state = None
                self.prev_game_info = None

                self.player1_recent_move_names = []
                self.player2_recent_move_names = []
                self.recent_move_limit = 8  # memory + min for good move variety

                # communication

                self.outbound_message_queue = asyncio.Queue()
                self.stop_event = asyncio.Event()

            async def send_game_state(self):
                await self.outbound_message_queue.put(
                    {"type": "game_state", "data": make_json_safe(self.game_state)}
                )

            async def handle_player_action(self, action_data):
                if self.observation is None:
                    return

                if not self.game_settings["humanVsLlm"]:
                    return

                action = action_data["action"]

                # super art

                if action == 18:
                    super_art_name = action_data.get("super_art")
                    if not super_art_name:
                        return

                    p1_obs = self.observation["P1"]
                    p1_character = CHARACTER_TO_ID[
                        self.game_settings["player1"]["character"]
                    ]
                    p1_direction = "left" if p1_obs["side"] == 0 else "right"

                    if (
                        p1_character in SPECIAL_MOVES
                        and super_art_name in SPECIAL_MOVES[p1_character]
                    ):
                        self.player1_next_buttons.extend(
                            SPECIAL_MOVES[p1_character][super_art_name][p1_direction]
                        )

                # combo

                elif action == 19:
                    combo_name = action_data["combo"]

                    p1_obs = self.observation["P1"]
                    p1_character = CHARACTER_TO_ID[
                        self.game_settings["player1"]["character"]
                    ]
                    p1_direction = "left" if p1_obs["side"] == 0 else "right"

                    if p1_character in COMBOS and combo_name in COMBOS[p1_character]:
                        self.player1_next_buttons.extend(
                            COMBOS[p1_character][combo_name][p1_direction]
                        )

                # normal move

                else:
                    if action <= 8:  # directional, so don't queue
                        self.player1_current_action = action
                    else:  # attack moves (9-17), so queue
                        self.player1_next_buttons.append(action)

            async def cleanup_environment(self):
                print("Cleaning up environment...")
                if self.env:
                    try:
                        self.env.close()
                    except Exception:
                        print("Warning: could not close environment")
                    finally:
                        self.env = None

            async def prepare_for_next_game(self):
                await self.cleanup_environment()

                if self.sandbox:
                    print(f"Terminating sandbox {self.sandbox.object_id}")
                    self.sandbox.terminate()
                    self.sandbox = await create_sandbox()

                self.game_running = False
                self.game_state = create_initial_game_state()
                self.observation = None
                self.info = None
                self.player1_next_buttons = []
                self.player2_next_buttons = []
                self.player1_recent_move_names = []
                self.player2_recent_move_names = []
                self.player1_current_action = 0
                self.actions = {"agent_0": 0, "agent_1": 0}
                self.in_transition = False
                self.transition_start_time = None
                self.pending_game_end = False
                self.game_end_data = None

            async def cleanup(self):
                print("Cleaning up resources...")
                await self.cleanup_environment()
                if self.sandbox:
                    print(f"Terminating sandbox {self.sandbox.object_id}")
                    self.sandbox.terminate()
                    self.sandbox = None

        # routes

        @web_app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            print("Client connected")

            session = GameSession(websocket)

            _, _, session.sandbox = await asyncio.gather(
                self.create_llm(),
                self.create_yolo(),
                create_sandbox(),
            )

            async def process_inbound_messages():
                try:
                    while not session.stop_event.is_set():
                        data = await websocket.receive_json()
                        message_type = data.get("type", "unknown")

                        if message_type == "start_game":
                            print(f"Received start_game message: {data}")
                            if not session.game_running:
                                received_settings = data.get("data", {})
                                if received_settings:
                                    session.game_settings.update(received_settings)
                                session.game_running = True
                        elif message_type == "player_action":
                            await session.handle_player_action(data["data"])
                        elif message_type == "gamepad_status":
                            session.game_settings["gamepadConnected"] = data.get(
                                "data", {}
                            ).get("connected", False)

                except WebSocketDisconnect:
                    print("WebSocket disconnected in message processor")
                    session.stop_event.set()
                except Exception:
                    print(f"Error in message processor: {traceback.format_exc()}")
                    session.stop_event.set()

            async def process_outbound_messages():
                try:
                    while not session.stop_event.is_set():
                        message = await session.outbound_message_queue.get()
                        print(f"Sending game state: {message}")
                        await websocket.send_json(message)

                except WebSocketDisconnect:
                    print("WebSocket disconnected in outgoing processor")
                    session.stop_event.set()
                except Exception:
                    print(f"Error in outgoing processor: {traceback.format_exc()}")
                    session.stop_event.set()

            async def run_robot_background():
                try:
                    while not session.stop_event.is_set():
                        await asyncio.sleep(0.001)

                        if (
                            not session.game_running
                            or session.observation is None
                            or session.in_transition
                        ):
                            continue

                        if (
                            "timer" not in session.observation
                            or session.observation["timer"] is None
                        ):  # in case env was just reset
                            continue

                        # store values to avoid race condition
                        # TODO: remove since condition above should be enough
                        timer = session.observation["timer"][0]
                        frame = session.observation["frame"]

                        obs_p1 = session.observation["P1"]
                        obs_p2 = session.observation["P2"]

                        p1_settings = session.game_settings["player1"]
                        p2_settings = session.game_settings["player2"]

                        p1_character = p1_settings["character"]
                        p2_character = p2_settings["character"]

                        (
                            boxes,
                            class_ids,
                        ) = await self.yolo.detect_characters.remote.aio(
                            [
                                CHARACTER_TO_ID[p1_character],
                                CHARACTER_TO_ID[p2_character],
                            ],
                            frame,
                        )

                        game_info = GameInfo(
                            timer=timer,
                            boxes=boxes,
                            class_ids=class_ids,
                        )

                        player1 = PlayerState(
                            character=p1_character,
                            super_art=p1_settings["superArt"],
                            wins=obs_p1["wins"][0],
                            side=obs_p1["side"],
                            stunned=obs_p1["stunned"],
                            stun_bar=obs_p1["stun_bar"][0],
                            health=obs_p1["health"][0],
                            super_count=obs_p1["super_count"][0],
                            super_bar=obs_p1["super_bar"][0],
                        )

                        player2 = PlayerState(
                            character=p2_character,
                            super_art=p2_settings["superArt"],
                            wins=obs_p2["wins"][0],
                            side=obs_p2["side"],
                            stunned=obs_p2["stunned"],
                            stun_bar=obs_p2["stun_bar"][0],
                            health=obs_p2["health"][0],
                            super_count=obs_p2["super_count"][0],
                            super_bar=obs_p2["super_bar"][0],
                        )

                        if not session.game_settings["humanVsLlm"]:
                            messages_p1, available_moves_p1 = create_messages(
                                game_info,
                                player2,
                                player1,
                                session.prev_game_info,
                                session.prev_player2_state,
                                session.prev_player1_state,
                                session.player1_recent_move_names,
                                session.game_settings["difficulty"],
                            )

                            moves_p1, move_name_p1 = await self.llm.chat.remote.aio(
                                messages_p1,
                                p1_character,
                                p1_settings["superArt"],
                                obs_p1["super_count"][0],
                                obs_p1["side"],
                                available_moves_p1,
                            )
                            session.player1_next_buttons.extend(moves_p1)
                            session.player1_recent_move_names.append(move_name_p1)

                            if (
                                len(session.player1_next_buttons)
                                > session.next_buttons_limit
                            ):
                                session.player1_next_buttons.pop(0)

                            if (
                                len(session.player1_recent_move_names)
                                > session.recent_move_limit
                            ):
                                session.player1_recent_move_names.pop(0)

                        messages, available_moves = create_messages(
                            game_info,
                            player1,
                            player2,
                            session.prev_game_info,
                            session.prev_player1_state,
                            session.prev_player2_state,
                            session.player2_recent_move_names,
                            session.game_settings["difficulty"],
                        )

                        moves, move_name = await self.llm.chat.remote.aio(
                            messages,
                            p2_character,
                            p2_settings["superArt"],
                            obs_p2["super_count"][0],
                            obs_p2["side"],
                            available_moves,
                        )
                        session.player2_next_buttons.extend(moves)
                        session.player2_recent_move_names.append(move_name)

                        if (
                            len(session.player2_next_buttons)
                            > session.next_buttons_limit
                        ):
                            session.player2_next_buttons.pop(0)

                        if (
                            len(session.player2_recent_move_names)
                            > session.recent_move_limit
                        ):
                            session.player2_recent_move_names.pop(0)

                        session.prev_game_info = game_info
                        session.prev_player1_state = player1
                        session.prev_player2_state = player2

                except WebSocketDisconnect:
                    print("WebSocket disconnected in robot background")
                    session.stop_event.set()
                except Exception:
                    print(f"Error in robot background: {traceback.format_exc()}")
                    session.stop_event.set()

            async def run_game_loop():
                try:
                    while not session.stop_event.is_set():
                        if not session.game_running:
                            await asyncio.sleep(0.001)
                            continue

                        print("Creating DIAMBRA environment...")
                        p1_settings = session.game_settings["player1"]
                        p2_settings = session.game_settings["player2"]

                        disable_keyboard = not session.game_settings["humanVsLlm"]
                        disable_joystick = not session.game_settings["gamepadConnected"]

                        settings = EnvironmentSettingsMultiAgent(
                            step_ratio=1,
                            role=(Roles.P1, Roles.P2),
                            disable_keyboard=disable_keyboard,
                            disable_joystick=disable_joystick,
                            render_mode="rgb_array",
                            splash_screen=False,
                            grpc_timeout=30,
                            action_space=(SpaceTypes.DISCRETE, SpaceTypes.DISCRETE),
                            characters=[
                                p1_settings["character"],
                                p2_settings["character"],
                            ],
                            outfits=[
                                p1_settings["outfit"],
                                p2_settings["outfit"],
                            ],
                            super_art=[
                                p1_settings["superArt"],
                                p2_settings["superArt"],
                            ],
                        )
                        try:
                            session.env = await asyncio.wait_for(
                                asyncio.to_thread(arena.make, "sfiii3n", settings),
                                timeout=30,
                            )
                        except Exception as e:
                            print(f"Error creating DIAMBRA environment: {e}")
                            session.game_state["status"] = "error"
                            session.game_state["error"] = str(e)
                            await session.send_game_state()
                            await session.prepare_for_next_game()
                            await session.send_game_state()
                            continue
                        print("DIAMBRA environment created successfully!")

                        session.game_state["status"] = "running"
                        await session.send_game_state()

                        try:
                            session.observation, session.info = session.env.reset()
                        except Exception as e:
                            print(f"Error during env.reset: {e}")
                            session.game_state["status"] = "error"
                            session.game_state["error"] = str(e)
                            await session.send_game_state()
                            await session.prepare_for_next_game()
                            await session.send_game_state()
                            continue

                        # according to https://docs.diambra.ai/envs/games/
                        # SF3 runs at 164 FPS natively, but we want 60 FPS output
                        target_fps = 60.0
                        frame_interval = 1.0 / target_fps
                        next_frame_time = asyncio.get_event_loop().time()

                        # game loop

                        while session.game_running and not session.stop_event.is_set():
                            current_time = asyncio.get_event_loop().time()
                            sleep_time = next_frame_time - current_time
                            if sleep_time > 0:
                                await asyncio.sleep(sleep_time)
                            else:
                                await asyncio.sleep(0)
                            next_frame_time += frame_interval

                            if session.in_transition:
                                elapsed = (
                                    asyncio.get_event_loop().time()
                                    - session.transition_start_time
                                )
                                if elapsed >= session.transition_duration:
                                    session.in_transition = False
                                    session.transition_start_time = None
                            else:
                                session.actions = {
                                    "agent_0": session.player1_next_buttons.pop(0)
                                    if session.player1_next_buttons
                                    else (
                                        session.player1_current_action
                                        if session.game_settings["humanVsLlm"]
                                        else 0
                                    ),
                                    "agent_1": session.player2_next_buttons.pop(0)
                                    if session.player2_next_buttons
                                    else 0,
                                }

                                try:
                                    (
                                        session.observation,
                                        reward,
                                        terminated,
                                        truncated,
                                        session.info,
                                    ) = session.env.step(session.actions)
                                except Exception as e:
                                    print(f"Error during env.step: {e}")
                                    session.game_state["status"] = "error"
                                    session.game_state["error"] = str(e)
                                    await session.send_game_state()
                                    await session.prepare_for_next_game()
                                    await session.send_game_state()
                                    continue

                                if session.info.get("game_done", False):
                                    session.in_transition = True
                                    session.transition_start_time = (
                                        asyncio.get_event_loop().time()
                                    )
                                    session.pending_game_end = True
                                    session.game_end_data = {
                                        "terminated": terminated,
                                        "truncated": truncated,
                                    }
                                    await session.outbound_message_queue.put(
                                        {
                                            "type": "transition",
                                            "data": {"transition_type": "game"},
                                        }
                                    )
                                elif session.info.get("round_done", False):
                                    session.in_transition = True
                                    session.transition_start_time = (
                                        asyncio.get_event_loop().time()
                                    )
                                    await session.outbound_message_queue.put(
                                        {
                                            "type": "transition",
                                            "data": {"transition_type": "round"},
                                        }
                                    )

                            if not session.in_transition:
                                frame = session.observation.get("frame")
                                if frame is not None:
                                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                                    _, buffer = cv2.imencode(
                                        ".jpg",
                                        frame,
                                        [cv2.IMWRITE_JPEG_QUALITY, 85],
                                    )
                                    await websocket.send_bytes(buffer.tobytes())

                            if not session.in_transition and (
                                (terminated or truncated) or session.pending_game_end
                            ):
                                if session.pending_game_end:
                                    terminated = session.game_end_data.get(
                                        "terminated", False
                                    )
                                    truncated = session.game_end_data.get(
                                        "truncated", False
                                    )
                                    session.pending_game_end = False
                                    session.game_end_data = None

                                if terminated or truncated:
                                    p1_wins = session.observation["P1"]["wins"][0]
                                    p2_wins = session.observation["P2"]["wins"][0]
                                    print(
                                        f"Game finished - P1: {p1_wins}, P2: {p2_wins}"
                                    )

                                    if session.game_settings["humanVsLlm"]:
                                        if p1_wins > p2_wins:
                                            session.game_state["scores"][0] += 1
                                            winner = "YOU"
                                        elif p2_wins > p1_wins:
                                            session.game_state["scores"][1] += 1
                                            winner = "LLM"
                                        else:
                                            winner = "Draw"
                                    else:
                                        if p1_wins > p2_wins:
                                            session.game_state["scores"][0] += 1
                                            winner = "LLM 1"
                                        elif p2_wins > p1_wins:
                                            session.game_state["scores"][1] += 1
                                            winner = "LLM 2"
                                        else:
                                            winner = "Draw"

                                    session.game_state["status"] = "finished"
                                    session.game_state["winner"] = winner
                                    await session.send_game_state()

                                    await session.prepare_for_next_game()
                                    await session.send_game_state()

                except WebSocketDisconnect:
                    print("WebSocket disconnected in game loop")
                    session.stop_event.set()
                except Exception:
                    print(f"Error in game loop: {traceback.format_exc()}")
                    session.stop_event.set()

            await session.send_game_state()

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
                session.stop_event.set()
                session.game_running = False
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                print(f"WebSocket error: {e}")
                session.stop_event.set()
                session.game_running = False
                session.game_state["status"] = "error"
                session.game_state["error"] = str(e)
                try:
                    await session.send_game_state()
                except Exception:
                    print("Warning: could not send error message")
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                await session.cleanup()

        @web_app.get("/")
        async def index():
            return FileResponse(f"{remote_frontend_dir}/index.html")

        @web_app.get("/icons/{icon}.png")
        async def icon_png(icon: str):
            return FileResponse(f"{remote_icons_dir}/{icon}.png")

        @web_app.get("/icons/{icon}.svg")
        async def icon_svg(icon: str):
            return FileResponse(f"{remote_icons_dir}/{icon}.svg")

        @web_app.get("/capcom.svg")
        async def capcom_logo():
            return FileResponse(f"{remote_logos_dir}/capcom.svg")

        @web_app.get("/favicon.ico")
        async def favicon():
            return FileResponse(f"{remote_logos_dir}/favicon.ico")

        @web_app.get("/modal.svg")
        async def modal_logo():
            return FileResponse(f"{remote_logos_dir}/modal.svg")

        @web_app.get("/outfits/{character}/{outfit}.png")
        async def outfit(character: str, outfit: int):
            return FileResponse(f"{remote_outfits_dir}/{character}/{outfit}.png")

        @web_app.get("/portraits/{character}.png")
        async def portrait(character: str):
            return FileResponse(f"{remote_portraits_dir}/{character}.png")

        @web_app.get("/sounds/{sound}.mp3")
        async def sound(sound: str):
            return FileResponse(f"{remote_sounds_dir}/{sound}.mp3")

        @web_app.get("/sounds/gameplay/{sound}.mp3")
        async def gameplay_sound(sound: str):
            return FileResponse(f"{remote_sounds_dir}/gameplay/{sound}.mp3")

        @web_app.get("/api/extra-moves")
        async def get_extra_moves():
            return make_json_safe({"combos": COMBOS, "special_moves": SPECIAL_MOVES})

        web_app.mount("/", StaticFiles(directory=remote_frontend_dir), name="static")

        return web_app
