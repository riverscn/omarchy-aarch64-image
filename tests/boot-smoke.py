#!/usr/bin/env python3
"""Boot a disposable image snapshot and verify the first-boot setup screens."""

import json
import pathlib
import socket
import subprocess
import sys
import tempfile
import time


def main():
    image = pathlib.Path(sys.argv[1]).resolve(strict=True)
    evidence = pathlib.Path(sys.argv[2]).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    firmware = next((pathlib.Path(p) for p in (
        "/usr/share/qemu-efi-aarch64/QEMU_EFI.fd",
        "/usr/share/edk2/aarch64/QEMU_EFI.fd",
        "/usr/share/AAVMF/AAVMF_CODE.fd",
    ) if pathlib.Path(p).is_file()), None)
    if firmware is None:
        raise RuntimeError("AArch64 UEFI firmware is missing")

    with tempfile.TemporaryDirectory(prefix="omarchy-boot-") as work:
        qmp_path = pathlib.Path(work) / "qmp.sock"
        with (evidence / "qemu.log").open("w") as log:
            vm = subprocess.Popen([
                "qemu-system-aarch64", "-machine", "virt,gic-version=3",
                "-accel", "tcg", "-cpu", "max", "-smp", "2", "-m", "4096",
                "-bios", str(firmware), "-snapshot",
                "-drive", f"if=none,file={image},format=qcow2,id=system",
                "-device", "virtio-blk-pci,drive=system",
                "-device", "virtio-gpu-pci", "-device", "qemu-xhci",
                "-device", "usb-kbd", "-device", "usb-tablet",
                "-device", "virtio-rng-pci",
                "-netdev", "user,id=network", "-device", "virtio-net-pci,netdev=network",
                "-display", "none", "-serial", f"file:{evidence / 'serial.log'}",
                "-qmp", f"unix:{qmp_path},server=on,wait=off",
            ], stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 600
                while not qmp_path.exists():
                    if vm.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError("QEMU did not start; inspect qemu.log")
                    time.sleep(1)
                with socket.socket(socket.AF_UNIX) as connection:
                    connection.settimeout(30)
                    connection.connect(str(qmp_path))
                    stream = connection.makefile("rwb")
                    json.loads(stream.readline())

                    def qmp(command, arguments=None):
                        request = {"execute": command}
                        if arguments is not None:
                            request["arguments"] = arguments
                        stream.write(json.dumps(request).encode() + b"\n")
                        stream.flush()
                        while True:
                            raw = stream.readline()
                            if not raw:
                                raise RuntimeError("QEMU closed the monitor")
                            response = json.loads(raw)
                            if "error" in response:
                                raise RuntimeError(str(response["error"]))
                            if "return" in response:
                                return response["return"]

                    qmp("qmp_capabilities")
                    stage = "greeter"
                    while time.monotonic() < deadline:
                        if vm.poll() is not None:
                            raise RuntimeError("QEMU exited before setup appeared")
                        screenshot = evidence / "latest.ppm"
                        qmp("screendump", {"filename": str(screenshot)})
                        result = subprocess.run(
                            ["tesseract", str(screenshot), "stdout", "--psm", "11"],
                            check=True, capture_output=True, text=True, timeout=30,
                        )
                        text = " ".join(result.stdout.lower().split())
                        (evidence / "latest-screen.txt").write_text(result.stdout)
                        if stage == "greeter" and "start setup" in text:
                            screenshot.rename(evidence / "success-greeter.ppm")
                            qmp("send-key", {"keys": [{"type": "qcode", "data": "ret"}]})
                            stage = "keyboard"
                            print("PASS: UEFI/Limine boot reached the owner setup greeter", flush=True)
                        elif stage == "keyboard" and "keyboard" in text:
                            screenshot.rename(evidence / "success-keyboard.ppm")
                            print("PASS: virtual keyboard opens the keyboard setup screen", flush=True)
                            return
                        time.sleep(10)
                    raise RuntimeError(f"Timed out waiting for {stage}; inspect boot evidence")
            finally:
                vm.terminate()
                try:
                    vm.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    vm.kill()
                    vm.wait()


if __name__ == "__main__":
    main()
