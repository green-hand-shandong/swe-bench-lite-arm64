#!/bin/bash
# Boot an OSWorld ARM64 VM with a fresh overlay on top of the read-only base.
# Usage: boot-vm.sh [overlay-path]
set -e
BASE=/data2/gxw/osworld-arm-vm/ubuntu-22.04-arm64.img
OVERLAY=${1:-/data2/gxw/osworld-arm-vm/overlay.qcow2}
cd /data2/gxw/osworld-arm-vm
# stop any existing VM
if [ -f qemu.pid ]; then kill $(cat qemu.pid) 2>/dev/null || true; sleep 2; fi
pkill -9 -f "qemu-system-aarch64.*osworld" 2>/dev/null || true
sleep 1
rm -f "$OVERLAY"
qemu-img create -f qcow2 -b "$BASE" -F qcow2 "$OVERLAY" > /dev/null
nohup qemu-system-aarch64 \
  -machine virt,gic-version=max -cpu host \
  -smp 8 -m 8G \
  -enable-kvm \
  -drive file=efi_code.fd,format=raw,if=pflash,unit=0,readonly=on \
  -drive file=efi_vars.fd,format=raw,if=pflash,unit=1,readonly=on \
  -drive file="$OVERLAY",format=qcow2,if=none,id=hd0 \
  -device virtio-blk-pci,drive=hd0,bootindex=0 \
  -drive file=seed.img,format=raw,if=none,id=sd1,readonly=on \
  -device virtio-blk-pci,drive=sd1,bootindex=1 \
  -netdev user,id=net0,hostfwd=tcp::12222-:22,hostfwd=tcp::15000-:5000,hostfwd=tcp::18006-:8006,hostfwd=tcp::19222-:9222,hostfwd=tcp::18080-:8080 \
  -device virtio-net-pci,netdev=net0 \
  -device virtio-gpu-pci \
  -display none \
  -serial file:serial.log \
  -monitor unix:monitor.sock,server,nowait \
  -pidfile qemu.pid \
  > qemu.log 2>&1 &
echo "VM booting with overlay $OVERLAY (pid $!)"
