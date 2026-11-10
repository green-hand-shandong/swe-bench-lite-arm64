"""No-op VM manager for the QEMU provider: the VM lifecycle is managed
externally (qemu-system-aarch64 started by the operator), so registration is
a no-op."""
from desktop_env.providers.base import VMManager


class QEMUVMManger(VMManager):
    def initialize_registry(self, **kwargs):
        pass

    def add_vm(self, vm_path, **kwargs):
        pass

    def delete_vm(self, vm_path, **kwargs):
        pass

    def occupy_vm(self, vm_path, pid, **kwargs):
        pass

    def list_free_vms(self, **kwargs):
        return []

    def check_and_clean(self, **kwargs):
        pass

    def get_vm_path(self, **kwargs):
        return None
