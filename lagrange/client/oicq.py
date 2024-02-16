import os
import time

from lagrange.info import DeviceInfo, AppInfo, SigInfo
from lagrange.utils.binary.protobuf import proto_encode
from lagrange.utils.crypto.ecdh import ecdh
from lagrange.utils.crypto.tea import qqtea_encrypt
from .packet import PacketBuilder


def build_code2d_packet(
        uin: int,
        seq: int,
        cmd_id: int,
        app_info: AppInfo,
        device_info: DeviceInfo,
        sig_info: SigInfo,
        body: bytes
) -> bytes:
    return build_login_packet(
        uin,
        seq,
        "wtlogin.trans_emp",
        app_info,
        device_info,
        sig_info,
        (
            PacketBuilder()
            .write_u8(0)
            .write_u16(len(body) + 53)
            .write_u32(app_info.app_id)
            .write_u32(0x72)
            .write_bytes(bytes(3))
            .write_u32(int(time.time()))
            .write_u8(2)

            .write_u16(len(body) + 49)
            .write_u16(cmd_id)
            .write_bytes(bytes(21))
            .write_u8(3)
            .write_u32(50)
            .write_bytes(bytes(14))
            .write_u32(app_info.app_id)
            .write_bytes(body)
        ).pack()
    )


def build_login_packet(
        uin: int,
        seq: int,
        cmd: str,
        app_info: AppInfo,
        device_info: DeviceInfo,
        sig_info: SigInfo,
        body: bytes
) -> bytes:
    enc_body = qqtea_encrypt(body, ecdh["secp192k1"].share_key)

    frame_body = (
        PacketBuilder()
        .write_u16(8001)
        .write_u16(2064 if cmd == "wtlogin.login" else 2066)
        .write_u16(0)
        .write_u32(uin)
        .write_u8(3)
        .write_u8(135)
        .write_u32(0)
        .write_u8(19)
        .write_u16(0)
        .write_u16(app_info.app_client_version)
        .write_u32(0)
        .write_u8(1)
        .write_u8(1)
        .write_bytes(bytes(16))
        .write_u16(0x102)
        .write_u16(len(ecdh["secp192k1"].public_key))
        .write_bytes(ecdh["secp192k1"].public_key)
        .write_bytes(enc_body)
        .write_u8(3)
    ).pack()

    frame = (
        PacketBuilder()
        .write_u8(2)
        .write_u16(len(frame_body) + 3)  # + 2 + 1
        .write_bytes(frame_body)
    ).pack()

    return build_uni_packet(
        uin,
        seq,
        cmd,
        app_info,
        device_info,
        sig_info,
        frame
    )


def build_uni_packet(
        uin: int,
        seq: int,
        cmd: str,
        app_info: AppInfo,
        device_info: DeviceInfo,
        sig_info: SigInfo,
        body: bytes
) -> bytes:
    trace = f"00-{os.urandom(16).hex()}-{os.urandom(8).hex()}-01"
    head = proto_encode({
        15: trace,
        16: uin
    })

    sso_header = (
        PacketBuilder()
        .write_u32(seq)
        .write_u32(app_info.sub_app_id)
        .write_u32(2052)  # locale id
        .write_bytes(bytes.fromhex("020000000000000000000000"))
        .write_bytes(sig_info.tgt, "u32")
        .write_string(cmd, "u32")
        .write_bytes(b"", "u32")
        .write_string(device_info.guid, "u32")
        .write_bytes(b"", "u32")
        .write_string(app_info.current_version, "u16")
        .write_bytes(head, "u32")
    ).pack()

    sso_packet = (
        PacketBuilder()
        .write_bytes(sso_header, "u32")
        .write_bytes(body, "u32")
    ).pack()

    encrypted = qqtea_encrypt(sso_packet, sig_info.d2_key)

    service = (
        PacketBuilder()
        .write_u32(12)
        .write_u8(2 if len(sig_info.d2) == 0 else 1)
        .write_bytes(sig_info.d2, "u32")
        .write_u8(0)
        .write_string(str(uin), "u32")
        .write_bytes(encrypted)
    ).pack()

    return PacketBuilder().write_bytes(service, "u32").pack()
