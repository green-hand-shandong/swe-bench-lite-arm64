"""QEMU provider for OSWorld on ARM64 hosts.

Runs a raw QEMU/KVM aarch64 VM. The base image is read-only; each fresh
environment is a qcow2 overlay created by boot-vm.sh. Reverting to a snapshot
means: stop VM, discard overlay, boot again (cold reset ~90s). Saving state is
a no-op because the baseline is fixed (init_state baked into the base image).
"""
import logging
import os
import subprocess
import time

import requests

from desktop_env.providers.base import Provider

logger = logging.getLogger("desktopenv.providers.qemu.QEMUProvider")
logger.setLevel(logging.INFO)

HOST = "localhost"
SERVER_PORT = int(os.environ.get("QEMU_SERVER_PORT", 15000))
CHROMIUM_PORT = int(os.environ.get("QEMU_CHROMIUM_PORT", 19222))
VNC_PORT = int(os.environ.get("QEMU_VNC_PORT", 18006))
VLC_PORT = int(os.environ.get("QEMU_VLC_PORT", 18080))
SSH_PORT = int(os.environ.get("QEMU_SSH_PORT", 12222))
BOOT_SCRIPT = os.environ.get("QEMU_BOOT_SCRIPT", "/data2/gxw/osworld-arm-vm/boot-vm.sh")


class QEMUProvider(Provider):
    def __init__(self, region: str = None):
        super().__init__(region)

    def _wait_server(self, timeout: int = 420):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                requests.get(f"http://{HOST}:{SERVER_PORT}/platform", timeout=5)
                logger.info("QEMU VM guest server is ready")
                return
            except Exception:
                time.sleep(5)
        raise RuntimeError("QEMU VM guest server did not become ready")

    def start_emulator(self, path_to_vm: str, headless: bool, os_type: str = "Ubuntu"):
        # VM is booted externally (boot-vm.sh); just wait for the guest server
        try:
            requests.get(f"http://{HOST}:{SERVER_PORT}/platform", timeout=5)
            logger.info("QEMU VM already running")
        except Exception:
            self._wait_server()

    def get_ip_address(self, path_to_vm: str) -> str:
        return f"{HOST}:{SERVER_PORT}:{CHROMIUM_PORT}:{VNC_PORT}:{VLC_PORT}"

    def save_state(self, path_to_vm: str, snapshot_name: str):
        # baseline is fixed; nothing to save
        pass

    def revert_to_snapshot(self, path_to_vm: str, snapshot_name: str):
        # cold reset: recreate overlay + boot (guest returns to init_state)
        logger.info("cold reset: recreating overlay and booting VM")
        subprocess.run(["bash", BOOT_SCRIPT], check=True, capture_output=True, timeout=120)
        self._wait_server()

    def stop_emulator(self, path_to_vm: str, *args, **kwargs):
        # keep the VM running across tasks; overlay reset handles cleanup
        pass
