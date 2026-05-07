import asyncio
import base64
import os
from fractions import Fraction
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import modal

from .env import EnvironmentConfig, create_environment
from .serve.gemma4_31b import Gemma4Server
from .serve.gemma4_31b import app as gemma4_app
from .serve.ministral3_14b import Ministral3Server
from .serve.ministral3_14b import app as ministral3_app
from .serve.nemotron3nano_30ba3b_fp8 import Nemotron3NanoServer
from .serve.nemotron3nano_30ba3b_fp8 import app as nemotron3nano_app
from .serve.qwen35_35ba3b_fp8 import Qwen35Server
from .serve.qwen35_35ba3b_fp8 import app as qwen35_app
from .serve.qwen36_35ba3b_fp8 import Qwen36Server
from .serve.qwen36_35ba3b_fp8 import app as qwen36_app
from .serve.yolo import YOLOServer
from .serve.yolo import app as yolo_app
from .utils import (
    CHARACTER_TO_ID,
    COMBOS,
    SPECIAL_MOVES,
    GameInfo,
    PlayerState,
    create_messages,
    minutes,
    region,
)

# Modal setup

# web app
app = (
    modal.App(name="sf3")
    .include(gemma4_app)
    .include(ministral3_app)
    .include(nemotron3nano_app)
    .include(qwen35_app)
    .include(qwen36_app)
    .include(yolo_app)
)

PARTICIPANT_SPECS = {
    "human": {"label": "YOU", "server_cls": None, "uses_frames": False},
    "qwen35_35ba3b_fp8": {
        "label": "QWEN3.5-35B",
        "server_cls": Qwen35Server,
        "uses_frames": True,
    },
    "qwen36_35ba3b_fp8": {
        "label": "QWEN3.6-35B",
        "server_cls": Qwen36Server,
        "uses_frames": True,
    },
    "gemma4_31b": {
        "label": "GEMMA4-31B",
        "server_cls": Gemma4Server,
        "uses_frames": True,
    },
    "ministral3_14b": {
        "label": "MINISTRAL3-14B",
        "server_cls": Ministral3Server,
        "uses_frames": True,
    },
    "nemotron3nano_30ba3b_fp8": {
        "label": "NEMOTRON3-NANO-30B",
        "server_cls": Nemotron3NanoServer,
        "uses_frames": False,
    },
}

PARTICIPANT_LABELS = {
    participant: spec["label"] for participant, spec in PARTICIPANT_SPECS.items()
}
DEFAULT_PLAYER1_PARTICIPANT = "human"
DEFAULT_PLAYER2_PARTICIPANT = "qwen35_35ba3b_fp8"

local_assets_dir = Path(__file__).parent.parent / "assets"
local_engine_dir = local_assets_dir / "engine"

remote_frontend_dir = "/root/frontend"
remote_icons_dir = "/root/icons"
remote_logos_dir = "/root/logos"
remote_outfits_dir = "/root/outfits"
remote_portraits_dir = "/root/portraits"
remote_sounds_dir = "/root/sounds"

static_image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install(
        "fastapi[standard]==0.116.1",
    )
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

gameplay_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "ffmpeg",
        "libturbojpeg-dev",
    )
    .env(
        {
            "SDL_VIDEODRIVER": "dummy",
            "SDL_AUDIODRIVER": "dummy",
            "XDG_RUNTIME_DIR": "/tmp",
        }
    )
    .uv_pip_install(
        "aiortc",
        "av",
        "fastapi[standard]==0.116.1",
        "MAMEToolkit==1.1.0",
        "numpy==2.3.1",
        "PyTurboJPEG==1.8.2",
        "websockets==15.0.1",
    )
    .add_local_file(
        local_engine_dir / "sfiii3n.zip",
        "/root/sfiii3n.zip",
    )
)

endpoint_timeout = 24 * 60 * minutes


def normalize_participant(participant: str, *, allow_human: bool) -> str:
    if participant not in PARTICIPANT_LABELS:
        return (
            DEFAULT_PLAYER1_PARTICIPANT if allow_human else DEFAULT_PLAYER2_PARTICIPANT
        )
    if participant == "human" and not allow_human:
        return DEFAULT_PLAYER2_PARTICIPANT
    return participant


def normalize_game_participants(game_settings: dict) -> tuple[str, str]:
    player1_participant = normalize_participant(
        game_settings.get("player1Participant", DEFAULT_PLAYER1_PARTICIPANT),
        allow_human=True,
    )
    player2_participant = normalize_participant(
        game_settings.get("player2Participant", DEFAULT_PLAYER2_PARTICIPANT),
        allow_human=False,
    )
    game_settings["player1Participant"] = player1_participant
    game_settings["player2Participant"] = player2_participant
    return player1_participant, player2_participant


def participant_uses_frames(participant: str) -> bool:
    return bool(PARTICIPANT_SPECS.get(participant, {}).get("uses_frames", False))


def participants_require_yolo(
    player1_participant: str, player2_participant: str
) -> bool:
    return (
        player1_participant != "human"
        and not participant_uses_frames(player1_participant)
    ) or (
        player2_participant != "human"
        and not participant_uses_frames(player2_participant)
    )


@app.cls(
    image=gameplay_image,
    region=region,
    min_containers=1,
    buffer_containers=1,
    secrets=[modal.Secret.from_dotenv(Path(__file__).parent.parent)],
    timeout=endpoint_timeout,
)
@modal.concurrent(
    max_inputs=3,
    target_inputs=2,
)
class Web:
    @modal.enter()
    def enter(
        self,
    ):
        self.participant_servers = {}
        self.participant_boot_tasks = {}
        self.yolo = None
        self.yolo_boot_task = None

    async def create_participant_server(self, participant: str):
        server_cls = PARTICIPANT_SPECS.get(participant, {}).get("server_cls")
        if server_cls is None:
            raise ValueError(f"Unsupported participant: {participant}")

        server = self.participant_servers.get(participant)
        if server is not None:
            return server

        boot_task = self.participant_boot_tasks.get(participant)
        if boot_task is None:

            async def boot():
                label = PARTICIPANT_LABELS.get(participant, participant)
                print(f"Creating {label}...")
                server = server_cls()
                await server.boot.remote.aio()
                self.participant_servers[participant] = server
                print(f"{label} created")
                return server

            boot_task = asyncio.create_task(boot())
            self.participant_boot_tasks[participant] = boot_task

        try:
            return await boot_task
        finally:
            if boot_task.done():
                self.participant_boot_tasks.pop(participant, None)

    async def create_yolo(self):
        if self.yolo is None:
            if self.yolo_boot_task is None:

                async def boot():
                    print("Creating YOLO...")
                    yolo = YOLOServer()
                    await yolo.boot.remote.aio()
                    self.yolo = yolo
                    print("YOLO created")
                    return yolo

                self.yolo_boot_task = asyncio.create_task(boot())

            try:
                return await self.yolo_boot_task
            finally:
                if self.yolo_boot_task and self.yolo_boot_task.done():
                    self.yolo_boot_task = None
        return self.yolo

    @modal.asgi_app(label="gameplay")
    def app(self):
        import json
        import traceback

        import numpy as np
        from aiortc import (
            RTCConfiguration,
            RTCIceServer,
            RTCPeerConnection,
            RTCSessionDescription,
            VideoStreamTrack,
        )
        from aiortc.sdp import candidate_from_sdp
        from av import VideoFrame
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.middleware.gzip import GZipMiddleware
        from fastapi.responses import JSONResponse
        from starlette.websockets import WebSocketState
        from turbojpeg import TJPF_RGB, TJSAMP_420, TurboJPEG

        web_app = FastAPI()
        web_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        web_app.add_middleware(GZipMiddleware, minimum_size=1024)

        # helper fns

        def build_ice_servers() -> list[dict]:
            username = os.environ.get("TURN_USERNAME")
            credential = os.environ.get("TURN_CREDENTIAL")
            if not username or not credential:
                return [{"urls": "stun:stun.l.google.com:19302"}]

            creds = {"username": username, "credential": credential}
            return [
                {"urls": "stun:stun.relay.metered.ca:80"},
                {"urls": "turn:standard.relay.metered.ca:80"} | creds,
                {"urls": "turn:standard.relay.metered.ca:80?transport=tcp"} | creds,
                {"urls": "turn:standard.relay.metered.ca:443"} | creds,
                {"urls": "turns:standard.relay.metered.ca:443?transport=tcp"} | creds,
            ]

        def build_turn_servers() -> dict:
            return {
                "type": "turn_servers",
                "ice_servers": build_ice_servers(),
            }

        def build_rtc_configuration() -> RTCConfiguration:
            ice_servers = []
            for server in build_ice_servers():
                ice_servers.append(
                    RTCIceServer(
                        urls=server["urls"],
                        username=server.get("username"),
                        credential=server.get("credential"),
                    )
                )
            return RTCConfiguration(iceServers=ice_servers)

        class GameVideoTrack(VideoStreamTrack):
            def __init__(self, target_fps: float = 60.0):
                super().__init__()
                self.target_fps = target_fps
                self.latest_frame = None
                self._start_time = None
                self._timestamp = 0
                self._timeline_needs_realign = False

            def set_frame(self, frame):
                self.latest_frame = frame

            def reset(self):
                if self.latest_frame is not None:
                    self.latest_frame = np.zeros_like(self.latest_frame)
                self._timeline_needs_realign = True
                self._start_time = None

            async def recv(self) -> VideoFrame:
                while self.latest_frame is None:
                    await asyncio.sleep(1 / self.target_fps)

                loop = asyncio.get_event_loop()
                timestamp_step = int((1 / self.target_fps) * 90000)
                if self._start_time is None or self._timeline_needs_realign:
                    if self._timestamp:
                        self._timestamp += timestamp_step
                    self._start_time = loop.time() - (self._timestamp / 90000)
                    self._timeline_needs_realign = False
                else:
                    self._timestamp += timestamp_step
                    deadline = self._start_time + (self._timestamp / 90000)
                    delay = deadline - loop.time()
                    if delay > 0:
                        await asyncio.sleep(delay)

                output = VideoFrame.from_ndarray(self.latest_frame, format="rgb24")
                output.pts = self._timestamp
                output.time_base = Fraction(1, 90000)
                return output

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
            def __init__(self):
                # game state

                self.env = None
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
                    "player1Participant": DEFAULT_PLAYER1_PARTICIPANT,
                    "player2Participant": DEFAULT_PLAYER2_PARTICIPANT,
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

            async def handle_inbound_message(self, data):
                message_type = data.get("type", "unknown")

                if message_type == "start_game":
                    if not self.game_running:
                        received_settings = data.get("data", {})
                        if received_settings:
                            self.game_settings.update(received_settings)
                        self.game_running = True
                elif message_type == "player_action":
                    await self.handle_player_action(data["data"])
                elif message_type == "gamepad_status":
                    self.game_settings["gamepadConnected"] = data.get("data", {}).get(
                        "connected", False
                    )

            async def handle_player_action(self, action_data):
                if self.observation is None:
                    return

                player1_participant, _ = normalize_game_participants(self.game_settings)
                if player1_participant != "human":
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
                if self.env:
                    try:
                        self.env.close()
                    except Exception:
                        print("Warning: could not close environment")
                    finally:
                        self.env = None

            async def prepare_for_next_game(self):
                await self.cleanup_environment()

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

            async def cleanup(self):
                await self.cleanup_environment()

        # routes

        @web_app.websocket("/ws/{peer_id}")
        async def websocket_endpoint(websocket: WebSocket, peer_id: str):
            await websocket.accept()

            session = GameSession()
            jpeg_enc = TurboJPEG()
            frame_cache = {"frame": None, "jpeg_bytes": None, "data_url": None}
            video_track = GameVideoTrack()
            control_channel = None
            control_channel_ready = asyncio.Event()
            pc = RTCPeerConnection(configuration=build_rtc_configuration())

            def get_frame_jpeg_bytes(frame: np.ndarray) -> bytes:
                if frame_cache["frame"] is not frame:
                    frame_cache["frame"] = frame
                    frame_cache["jpeg_bytes"] = jpeg_enc.encode(
                        np.ascontiguousarray(frame),
                        quality=85,
                        pixel_format=TJPF_RGB,
                        jpeg_subsample=TJSAMP_420,
                    )
                    frame_cache["data_url"] = None
                return frame_cache["jpeg_bytes"]

            def get_frame_data_url(frame: np.ndarray) -> str:
                if frame_cache["data_url"] is None:
                    frame_cache["data_url"] = (
                        "data:image/jpeg;base64,"
                        + base64.b64encode(get_frame_jpeg_bytes(frame)).decode("utf-8")
                    )
                return frame_cache["data_url"]

            async def prefetch_required_servers(
                player1_participant: str, player2_participant: str
            ) -> None:
                tasks = []
                if participants_require_yolo(player1_participant, player2_participant):
                    tasks.append(self.create_yolo())
                tasks.extend(
                    self.create_participant_server(participant)
                    for participant in {player1_participant, player2_participant}
                    if participant != "human"
                )
                if tasks:
                    await asyncio.gather(*tasks)

            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                state = pc.connectionState
                if state in {"closed", "failed", "disconnected"}:
                    session.stop_event.set()

            @pc.on("icecandidate")
            async def on_icecandidate(candidate):
                try:
                    if candidate is None:
                        return
                    if websocket.client_state == WebSocketState.DISCONNECTED:
                        return
                    await websocket.send_json(
                        {
                            "type": "ice_candidate",
                            "candidate": {
                                "candidate_sdp": candidate.to_sdp(),
                                "sdpMid": candidate.sdpMid,
                                "sdpMLineIndex": candidate.sdpMLineIndex,
                            },
                        }
                    )
                except Exception:
                    print(f"Error sending ICE candidate: {traceback.format_exc()}")

            @pc.on("datachannel")
            def on_datachannel(channel):
                nonlocal control_channel

                if channel.label != "game_control":
                    return
                control_channel = channel

                @channel.on("open")
                def on_channel_open():
                    control_channel_ready.set()

                if channel.readyState == "open":
                    control_channel_ready.set()

                @channel.on("close")
                def on_channel_close():
                    control_channel_ready.clear()
                    session.stop_event.set()

                @channel.on("message")
                def on_channel_message(message):
                    async def process_message():
                        try:
                            if isinstance(message, bytes):
                                payload = json.loads(message.decode("utf-8"))
                            else:
                                payload = json.loads(message)
                            await session.handle_inbound_message(payload)
                        except Exception:
                            print(
                                f"Error processing datachannel msg: {traceback.format_exc()}"
                            )

                    asyncio.create_task(process_message())

            async def process_signaling_messages():
                try:
                    while not session.stop_event.is_set():
                        if websocket.client_state == WebSocketState.DISCONNECTED:
                            break
                        receive_task = asyncio.create_task(websocket.receive_json())
                        stop_task = asyncio.create_task(session.stop_event.wait())
                        done, pending = await asyncio.wait(
                            {receive_task, stop_task},
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        for task in pending:
                            task.cancel()
                        if pending:
                            await asyncio.gather(*pending, return_exceptions=True)
                        if stop_task in done:
                            break
                        data = receive_task.result()
                        message_type = data.get("type", "unknown")

                        if message_type == "offer":
                            offer_sdp = data.get("sdp", "")
                            if "m=video" in offer_sdp and not any(
                                sender.track is video_track
                                for sender in pc.getSenders()
                            ):
                                pc.addTrack(video_track)

                            await pc.setRemoteDescription(
                                RTCSessionDescription(
                                    sdp=data["sdp"],
                                    type=data["type"],
                                )
                            )
                            answer = await pc.createAnswer()
                            await pc.setLocalDescription(answer)
                            await websocket.send_json(
                                {
                                    "type": "answer",
                                    "sdp": pc.localDescription.sdp,
                                    "peer_id": "server",
                                }
                            )
                            continue

                        if message_type == "ice_candidate":
                            candidate = data.get("candidate")
                            if candidate and candidate.get("candidate_sdp"):
                                ice_candidate = candidate_from_sdp(
                                    candidate["candidate_sdp"]
                                )
                                ice_candidate.sdpMid = candidate.get("sdpMid")
                                ice_candidate.sdpMLineIndex = candidate.get(
                                    "sdpMLineIndex"
                                )
                                await pc.addIceCandidate(ice_candidate)
                            continue

                        if message_type == "get_turn_servers":
                            await websocket.send_json(build_turn_servers())
                            continue
                except WebSocketDisconnect:
                    session.stop_event.set()
                except Exception:
                    print(f"Error in signaling processor: {traceback.format_exc()}")
                    session.stop_event.set()

            async def process_outbound_messages():
                try:
                    while not session.stop_event.is_set():
                        get_message_task = asyncio.create_task(
                            session.outbound_message_queue.get()
                        )
                        stop_task = asyncio.create_task(session.stop_event.wait())
                        done, pending = await asyncio.wait(
                            {get_message_task, stop_task},
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        for task in pending:
                            task.cancel()
                        if pending:
                            await asyncio.gather(*pending, return_exceptions=True)
                        if stop_task in done:
                            break
                        message = get_message_task.result()
                        while not session.stop_event.is_set():
                            if control_channel and control_channel.readyState == "open":
                                control_channel.send(json.dumps(message))
                                break

                            channel_ready_task = asyncio.create_task(
                                control_channel_ready.wait()
                            )
                            stop_task = asyncio.create_task(session.stop_event.wait())
                            done, pending = await asyncio.wait(
                                {channel_ready_task, stop_task},
                                return_when=asyncio.FIRST_COMPLETED,
                            )
                            for task in pending:
                                task.cancel()
                            if pending:
                                await asyncio.gather(
                                    *pending,
                                    return_exceptions=True,
                                )
                            if stop_task in done:
                                break
                except Exception:
                    print(f"Error in outgoing processor: {traceback.format_exc()}")
                    session.stop_event.set()

            async def keepalive():
                try:
                    while not session.stop_event.is_set():
                        await session.outbound_message_queue.put(
                            {"type": "heartbeat", "data": {}}
                        )
                        await asyncio.sleep(15)
                except Exception:
                    print(f"Error in keepalive: {traceback.format_exc()}")
                    session.stop_event.set()

            async def prefetch_servers():
                try:
                    player1_participant, player2_participant = (
                        normalize_game_participants(session.game_settings)
                    )
                    await prefetch_required_servers(
                        player1_participant, player2_participant
                    )
                    await session.send_game_state()
                except Exception as e:
                    print(f"Error creating model servers: {traceback.format_exc()}")
                    session.game_state["status"] = "error"
                    session.game_state["error"] = str(e)
                    await session.send_game_state()
                    session.stop_event.set()

            async def prepare_for_next_game():
                video_track.reset()
                await session.prepare_for_next_game()

            async def get_participant_move(
                participant: str,
                controlled_player: PlayerState,
                controlled_settings: dict,
                controlled_obs: dict,
                opponent_player: PlayerState,
                prev_controlled_player: PlayerState | None,
                prev_opponent_player: PlayerState | None,
                recent_moves,
                game_info: GameInfo,
                frames: list[str] | None,
            ) -> tuple[list[int], str]:
                messages, available_moves = create_messages(
                    game_info,
                    opponent_player,
                    controlled_player,
                    session.prev_game_info,
                    prev_opponent_player,
                    prev_controlled_player,
                    recent_moves,
                    session.game_settings["difficulty"],
                    frames=frames,
                )

                server = await self.create_participant_server(participant)
                return await server.chat.remote.aio(
                    messages,
                    controlled_settings["character"],
                    controlled_settings["superArt"],
                    controlled_obs["super_count"][0],
                    controlled_obs["side"],
                    available_moves,
                )

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

                        timer = session.observation["timer"][0]
                        frame = session.observation["frame"]

                        obs_p1 = session.observation["P1"]
                        obs_p2 = session.observation["P2"]

                        p1_settings = session.game_settings["player1"]
                        p2_settings = session.game_settings["player2"]

                        p1_character = p1_settings["character"]
                        p2_character = p2_settings["character"]

                        player1_participant, player2_participant = (
                            normalize_game_participants(session.game_settings)
                        )
                        if (
                            player1_participant == "human"
                            and player2_participant == "human"
                        ):
                            continue

                        if participants_require_yolo(
                            player1_participant, player2_participant
                        ):
                            yolo = await self.create_yolo()
                            (
                                boxes,
                                class_ids,
                            ) = await yolo.detect_characters.remote.aio(
                                [
                                    CHARACTER_TO_ID[p1_character],
                                    CHARACTER_TO_ID[p2_character],
                                ],
                                frame,
                            )
                        else:
                            boxes, class_ids = [], []

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

                        need_llm_frame = participant_uses_frames(
                            player1_participant
                        ) or participant_uses_frames(player2_participant)
                        frame_data_url = (
                            get_frame_data_url(frame) if need_llm_frame else None
                        )

                        if player1_participant != "human":
                            p1_frames = (
                                [frame_data_url]
                                if participant_uses_frames(player1_participant)
                                else None
                            )
                            moves_p1, move_name_p1 = await get_participant_move(
                                player1_participant,
                                player1,
                                p1_settings,
                                obs_p1,
                                player2,
                                session.prev_player1_state,
                                session.prev_player2_state,
                                session.player1_recent_move_names,
                                game_info,
                                p1_frames,
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

                        p2_frames = (
                            [frame_data_url]
                            if participant_uses_frames(player2_participant)
                            else None
                        )
                        moves, move_name = await get_participant_move(
                            player2_participant,
                            player2,
                            p2_settings,
                            obs_p2,
                            player1,
                            session.prev_player2_state,
                            session.prev_player1_state,
                            session.player2_recent_move_names,
                            game_info,
                            p2_frames,
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

                        p1_settings = session.game_settings["player1"]
                        p2_settings = session.game_settings["player2"]
                        player1_participant, player2_participant = (
                            normalize_game_participants(session.game_settings)
                        )

                        disable_keyboard = player1_participant != "human"
                        disable_joystick = not session.game_settings["gamepadConnected"]

                        env_config = EnvironmentConfig(
                            characters=(
                                p1_settings["character"],
                                p2_settings["character"],
                            ),
                            outfits=(
                                p1_settings["outfit"],
                                p2_settings["outfit"],
                            ),
                            super_arts=(
                                p1_settings["superArt"],
                                p2_settings["superArt"],
                            ),
                            step_ratio=1,
                            disable_keyboard=disable_keyboard,
                            disable_joystick=disable_joystick,
                            render_mode="rgb_array",
                        )
                        try:
                            session.env = await asyncio.wait_for(
                                asyncio.to_thread(create_environment, env_config),
                                timeout=30,
                            )
                        except Exception as e:
                            print(f"Error creating local environment: {e}")
                            session.game_state["status"] = "error"
                            session.game_state["error"] = str(e)
                            await session.send_game_state()
                            await prepare_for_next_game()
                            await session.send_game_state()
                            continue

                        session.game_state["status"] = "warming"
                        await session.send_game_state()
                        try:
                            await prefetch_required_servers(
                                player1_participant, player2_participant
                            )
                        except Exception as e:
                            print(f"Model/YOLO prefetch failed: {e}")
                            session.game_state["status"] = "error"
                            session.game_state["error"] = str(e)
                            await session.send_game_state()
                            await prepare_for_next_game()
                            await session.send_game_state()
                            continue

                        try:
                            (
                                session.observation,
                                session.info,
                            ) = await asyncio.to_thread(session.env.reset)
                        except Exception as e:
                            print(f"Error during env.reset: {e}")
                            session.game_state["status"] = "error"
                            session.game_state["error"] = str(e)
                            await session.send_game_state()
                            await prepare_for_next_game()
                            await session.send_game_state()
                            continue

                        initial_frame = session.observation.get("frame")
                        if initial_frame is not None:
                            video_track.set_frame(np.ascontiguousarray(initial_frame))

                        session.game_state["status"] = "running"
                        await session.send_game_state()

                        # SF3 runs faster than our target output rate.
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
                                        if player1_participant == "human"
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
                                    ) = await asyncio.to_thread(
                                        session.env.step, session.actions
                                    )
                                except Exception as e:
                                    print(f"Error during env.step: {e}")
                                    session.game_state["status"] = "error"
                                    session.game_state["error"] = str(e)
                                    await session.send_game_state()
                                    await prepare_for_next_game()
                                    await session.send_game_state()
                                    continue

                                if session.info.get("game_done", False):
                                    if terminated or truncated:
                                        p1_wins = session.observation["P1"]["wins"][0]
                                        p2_wins = session.observation["P2"]["wins"][0]

                                        if p1_wins > p2_wins:
                                            session.game_state["scores"][0] += 1
                                            winner = PARTICIPANT_LABELS.get(
                                                player1_participant,
                                                player1_participant,
                                            )
                                            if (
                                                player1_participant
                                                == player2_participant
                                            ):
                                                winner = f"{winner} (P1)"
                                        elif p2_wins > p1_wins:
                                            session.game_state["scores"][1] += 1
                                            winner = PARTICIPANT_LABELS.get(
                                                player2_participant,
                                                player2_participant,
                                            )
                                            if (
                                                player2_participant
                                                == player1_participant
                                            ):
                                                winner = f"{winner} (P2)"
                                        else:
                                            winner = "Draw"

                                        session.game_state["status"] = "finished"
                                        session.game_state["winner"] = winner
                                        await session.send_game_state()

                                        await prepare_for_next_game()
                                        await session.send_game_state()
                                        continue
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
                                    video_track.set_frame(np.ascontiguousarray(frame))

                except Exception:
                    print(f"Error in game loop: {traceback.format_exc()}")
                    session.stop_event.set()

            tasks = [
                asyncio.create_task(process_signaling_messages()),
                asyncio.create_task(process_outbound_messages()),
                asyncio.create_task(keepalive()),
                asyncio.create_task(prefetch_servers()),
                asyncio.create_task(run_robot_background()),
                asyncio.create_task(run_game_loop()),
            ]

            try:
                await asyncio.gather(*tasks)
            except WebSocketDisconnect:
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
                await pc.close()
                await session.cleanup()

        @web_app.websocket("/ws")
        async def websocket_missing_peer_id(websocket: WebSocket):
            await websocket.close(code=1008)

        @web_app.get("/warm/default-participant")
        async def warm_default_participant():
            await self.create_participant_server(DEFAULT_PLAYER2_PARTICIPANT)
            return JSONResponse({"ok": True})

        @web_app.get("/api/extra-moves")
        async def get_extra_moves():
            return JSONResponse(
                make_json_safe({"combos": COMBOS, "special_moves": SPECIAL_MOVES}),
                headers={"Cache-Control": "public, max-age=300"},
            )

        return web_app


def get_configured_gameplay_base_url() -> str:
    override = os.environ.get("SF3_GAMEPLAY_BASE_URL", "").strip()
    if override:
        return override.rstrip("/")
    return ""


def derive_gameplay_base_url(static_base_url: str) -> str:
    static_base_url = static_base_url.rstrip("/")
    if not static_base_url:
        return ""

    try:
        parsed = urlsplit(static_base_url)
    except ValueError:
        return ""

    netloc = parsed.netloc
    for static_suffix, gameplay_suffix in (
        ("--sf3-dev.modal.run", "--gameplay-dev.modal.run"),
        ("--sf3.modal.run", "--gameplay.modal.run"),
    ):
        if netloc.endswith(static_suffix):
            return urlunsplit(
                (
                    parsed.scheme,
                    netloc[: -len(static_suffix)] + gameplay_suffix,
                    "",
                    "",
                    "",
                )
            )

    return ""


@app.function(
    image=static_image,
    region=region,
    scaledown_window=5 * minutes,
    min_containers=1,
    buffer_containers=2,
    timeout=endpoint_timeout,
)
@modal.concurrent(max_inputs=96, target_inputs=64)
@modal.asgi_app(label="sf3")
def sf3():
    import json

    from fastapi import FastAPI, Request, WebSocket
    from fastapi.responses import FileResponse, Response
    from fastapi.staticfiles import StaticFiles

    web_app = FastAPI()
    no_cache_header = "no-store, max-age=0"
    no_cache_suffixes = (".html", ".js", ".css")
    frontend_root = Path(remote_frontend_dir).resolve()

    def is_no_cache_path(path: str) -> bool:
        return (
            path == "/"
            or path == "/runtime-config.js"
            or path.endswith(no_cache_suffixes)
        )

    @web_app.middleware("http")
    async def add_static_cache_headers(request: Request, call_next):
        response = await call_next(request)
        if is_no_cache_path(request.url.path):
            response.headers["Cache-Control"] = no_cache_header
        return response

    @web_app.get("/runtime-config.js")
    async def runtime_config(request: Request):
        gameplay_base_url = (
            get_configured_gameplay_base_url()
            or derive_gameplay_base_url(str(request.base_url))
        )
        body = (
            "window.__SF3_CONFIG__ = "
            + json.dumps({"gameplayBaseUrl": gameplay_base_url})
            + ";"
        )
        return Response(
            body,
            media_type="application/javascript",
            headers={"Cache-Control": no_cache_header},
        )

    @web_app.websocket("/ws")
    async def wrong_websocket_host(websocket: WebSocket):
        await websocket.close(code=1013, reason="Connect to gameplay host")

    @web_app.websocket("/ws/{path:path}")
    async def wrong_websocket_host_path(websocket: WebSocket, path: str):
        await websocket.close(code=1013, reason="Connect to gameplay host")

    @web_app.get("/capcom.svg")
    async def capcom_logo():
        return FileResponse(f"{remote_logos_dir}/capcom.svg")

    @web_app.get("/favicon.ico")
    async def favicon():
        return FileResponse(f"{remote_logos_dir}/favicon.ico")

    @web_app.get("/modal.svg")
    async def modal_logo():
        return FileResponse(f"{remote_logos_dir}/modal.svg")

    web_app.mount("/icons", StaticFiles(directory=remote_icons_dir), name="icons")
    web_app.mount("/outfits", StaticFiles(directory=remote_outfits_dir), name="outfits")
    web_app.mount(
        "/portraits", StaticFiles(directory=remote_portraits_dir), name="portraits"
    )
    web_app.mount("/sounds", StaticFiles(directory=remote_sounds_dir), name="sounds")

    def frontend_file_response(frontend_path: str):
        path = (frontend_root / frontend_path).resolve()
        if not path.is_relative_to(frontend_root):
            return Response(status_code=404)
        if not path.is_file():
            return Response(status_code=404)
        cache_header = (
            no_cache_header
            if path.suffix.lower() in no_cache_suffixes
            else "public, max-age=31536000, immutable"
        )
        return FileResponse(path, headers={"Cache-Control": cache_header})

    @web_app.get("/")
    async def index():
        return frontend_file_response("index.html")

    @web_app.get("/{frontend_path:path}")
    async def frontend_file(frontend_path: str):
        return frontend_file_response(frontend_path)

    return web_app
