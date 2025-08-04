import os
from pathlib import Path

import modal
import modal.experimental

engine_app = modal.App.lookup("sf3-engine-train", create_if_missing=True)

local_assets_dir = Path(__file__).parent.parent / "assets"
local_engine_dir = local_assets_dir / "engine"

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

minutes = 60


def create_sandbox():
    print("Creating sandbox...")
    engine_port = 50051
    sandbox = modal.Sandbox.create(
        "/bin/diambraEngineServer",
        app=engine_app,
        image=engine_image,
        timeout=24 * 60 * minutes,
        unencrypted_ports=[engine_port],
        verbose=True,
    )
    tunnels = sandbox.tunnels()
    tunnel = tunnels[engine_port]
    host, port = tunnel.tcp_socket
    os.environ["DIAMBRA_ENVS"] = f"{host}:{port}"
    print(f"Created sandbox {sandbox.object_id} at {host}:{port}")
    return sandbox


def create_environment(
    difficulty: int,
    characters: list[str],
    super_arts: list[int],
):
    import diambra.arena as arena
    from diambra.arena import EnvironmentSettingsMultiAgent, Roles, SpaceTypes

    print("Creating DIAMBRA environment...")
    settings = EnvironmentSettingsMultiAgent(
        step_ratio=6,
        role=(Roles.P1, Roles.P2),
        render_mode="rgb_array",
        splash_screen=False,
        grpc_timeout=1 * minutes,
        difficulty=difficulty,
        action_space=(SpaceTypes.DISCRETE, SpaceTypes.DISCRETE),
        characters=characters,
        super_art=super_arts,
    )
    try:
        env = arena.make("sfiii3n", settings)
    except Exception as e:
        print(f"Error creating DIAMBRA environment: {e}")
        return None
    print("DIAMBRA environment created successfully!")
    return env
