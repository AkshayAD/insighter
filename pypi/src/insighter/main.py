import argparse
import docker
import os
import requests
import signal
import socket
import sys
import threading
import time
import webbrowser

ENV_VARS = [
    "LOG_LEVEL",
    "ALLOW_HTTP",
    "POSTGRES_USERNAME",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOSTNAME",
    "POSTGRES_PORT",
    "POSTGRES_DATABASE",
    "AI_API_URL",
    "AI_API_USERNAME",
    "AI_API_PASSWORD",
    "JUPYTER_HOST",
    "JUPYTER_PORT",
    "JUPYTER_TOKEN",
    "DISABLE_CUSTOM_OAI_KEY",
]

def check_docker_running():
    client = docker.from_env()
    try:
        client.ping()
        return client
    except docker.errors.APIError:
        print("Error: Docker is not running.", file=sys.stderr)
        sys.exit(1)


def is_container_running(client, container_name):
    try:
        container = client.containers.get(container_name)
        return container.status == "running"
    except docker.errors.NotFound:
        return False


def is_container_existing(client, container_name):
    try:
        client.containers.get(container_name)
        return True
    except docker.errors.NotFound:
        return False


def create_volume_if_not_exists(client, volume_name):
    if volume_name not in [v.name for v in client.volumes.list()]:
        client.volumes.create(name=volume_name)


def handle_existing_container(client, container_name, detach):
    print('Error: Insighter is already running.', file=sys.stderr)
    action = input('Do you want to stop or restart it?\nPress enter to leave it running.\n[stop/restart]: ').strip()

    container = client.containers.get(container_name)

    if action == "stop":
        print('Stopping Insighter...')
        container.stop()
        print('Insighter stopped.')
        sys.exit(0)

    elif action == "restart":
        print('Restarting Insighter...')
        container.restart()
        if not detach:
            attach(container)
        sys.exit(0)

    elif action != "":
        print('Error: invalid action.', file=sys.stderr)
        sys.exit(1)


def is_port_in_use(port):
    """Check if a port is in use by attempting to bind to it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return False
        except OSError:
            return True


def find_free_port(start_port):
    while is_port_in_use(start_port):
        start_port += 1
    return start_port

def start_or_run_container(client, container_name, image, detach):
    if ":" not in image and "/" in image:
        image += ":latest"

    port = find_free_port(3000)

    if "/" in image and "latest" in image or not client.images.list(name=image):
        pull_image(client, image)

    # If the container exists, remove it to allow new port mappings and env variables
    if is_container_existing(client, container_name):
        container = client.containers.get(container_name)
        container.stop()
        container.remove()

    # Define the volumes and environment variables
    volumes = {
        'insighter_psql_data': {'bind': '/var/lib/postgresql/data', 'mode': 'rw'},
        'insighter_jupyter_data': {'bind': '/home/jupyteruser', 'mode': 'rw'},
        'insighter_insighter_data': {'bind': '/home/insighter', 'mode': 'rw'}
    }

    env = {}
    for var in ENV_VARS:
        if var in os.environ:
            env[var] = os.environ[var]

    # Run a new container with the updated ports and environment
    container = client.containers.run(
        image,
        detach=True,
        ports={f"3000/tcp": port},
        name=container_name,
        volumes=volumes,
        environment=env
    )

    api_url = f"http://localhost:{port}/api"
    web_url = f"http://localhost:{port}"

    def check_reachability():
        while True:
            try:
                response = requests.get(f"{api_url}/readyz")
                if response.status_code != 200:
                    time.sleep(1)
                    continue

                response = requests.get(web_url)
                if response.status_code == 200:
                    webbrowser.open(web_url)
                    break
            except requests.ConnectionError:
                pass
            time.sleep(1)

    thread = threading.Thread(target=check_reachability)
    thread.start()

    # Attach to logs so the user can see what's happening
    if not detach:
        attach(container)

    thread.join()

def pull_image(client, image):
    print(f"Downloading image {image}...")
    low_level_client = client.api
    has_some_version = len(client.images.list(name=image)) > 0

    try:
        response = low_level_client.pull(image, stream=True, decode=True)
        last_status = {}
        layer_output = {}

        for line in response:
            layer_id = line.get('id', None)
            status = line.get('status', '')
            progress = line.get('progress', '')

            if layer_id:
                # Update the status for this layer
                last_status[layer_id] = (status, progress)

                # Check if we have printed this layer before and update the line if so
                if layer_id in layer_output:
                    # Move the cursor back up to the line for this layer_id
                    sys.stdout.write(f"\033[{len(last_status) - list(last_status).index(layer_id)}A")
                    # Clear the line
                    sys.stdout.write("\033[K")
                else:
                    # Record the new line position for this layer_id
                    layer_output[layer_id] = sys.stdout.tell()

                # Print the updated status
                print(f"Layer {layer_id}: {status} {progress}")
                # Move the cursor back down to where it started
                sys.stdout.write(f"\033[{len(last_status) - list(last_status).index(layer_id)}B")

        print(f"Successfully pulled image {image}.")
    except Exception as e:
        print(f"Error: {str(e)}")
        if has_some_version:
            print(f"Error: failed to download image {image}. Using cached version.", file=sys.stderr)
        else:
            raise

def attach(container):
    for stdout, stderr in container.attach(stream=True, stdout=True, stderr=True, demux=True):
        if stdout:
            sys.stdout.buffer.write(stdout)
            sys.stdout.flush()
        if stderr:
            sys.stderr.buffer.write(stderr)
            sys.stderr.flush()


def signal_handler(sig, frame, container_name, client):
    print("\nCTRL-C detected. Stopping Insighter...")
    container = client.containers.get(container_name)
    container.stop()
    print("Insighter stopped.")
    sys.exit(0)


def main():
    # Argument parser
    parser = argparse.ArgumentParser(description="Run and manage Insighter.")
    parser.add_argument("-d", "--detach", action="store_true", help="Run Insighter in detached mode")
    parser.add_argument("--image", type=str, default="insightercloud/insighter", help=argparse.SUPPRESS)

    args = parser.parse_args()

    # initialize docker client and check if Docker is running
    client = check_docker_running()

    container_name = "insighter"

    # if container is already running, handle user input
    if is_container_running(client, container_name):
        handle_existing_container(client, container_name, args.detach)
        return

    # check or create necessary volumes
    create_volume_if_not_exists(client, "insighter_psql_data")
    create_volume_if_not_exists(client, "insighter_jupyter_data")
    create_volume_if_not_exists(client, "insighter_insighter_data")

    # Register signal handler for CTRL-C
    signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, container_name, client))

    # start or run the container
    start_or_run_container(client, container_name, args.image, args.detach)

if __name__ == "__main__":
    main()
