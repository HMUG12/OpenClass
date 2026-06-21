"""
AES-GCM 对称加密工具 — 用于 API Key 的安全存储
纯 Python 标准库实现（无需 cryptography 库）
"""
import base64
import hashlib
import os
import struct
from pathlib import Path

# 密钥文件路径
KEY_FILE = Path(__file__).resolve().parent.parent.parent / "data" / ".keyfile"

# AES S-Box
_SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
]

# Round constants
_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]


def _bytes_to_state(data: bytes) -> list:
    return [[data[i + 4 * j] for j in range(4)] for i in range(4)]


def _state_to_bytes(state: list) -> bytes:
    return bytes(state[i][j] for i in range(4) for j in range(4))


def _sub_bytes(state: list) -> list:
    return [[_SBOX[b] for b in row] for row in state]


def _shift_rows(state: list) -> list:
    return [state[r][r:] + state[r][:r] for r in range(4)]


def _xtime(a: int) -> int:
    return ((a << 1) ^ 0x1b) & 0xff if a & 0x80 else (a << 1) & 0xff


def _mix_column(col: list) -> list:
    t = col[0] ^ col[1] ^ col[2] ^ col[3]
    u = col[0]
    col[0] ^= t ^ _xtime(col[0] ^ col[1])
    col[1] ^= t ^ _xtime(col[1] ^ col[2])
    col[2] ^= t ^ _xtime(col[2] ^ col[3])
    col[3] ^= t ^ _xtime(col[3] ^ u)
    return col


def _mix_columns(state: list) -> list:
    return [_mix_column([state[0][j], state[1][j], state[2][j], state[3][j]])
            for j in range(4)]


def _add_round_key(state: list, key_schedule: list, round_idx: int) -> list:
    for i in range(4):
        for j in range(4):
            state[i][j] ^= key_schedule[round_idx * 4 + j][i]
    return state


def _key_expansion(key: bytes) -> list:
    nk, nb, nr = 4, 4, 10
    w = []
    for i in range(nk):
        w.append(list(key[4 * i:4 * i + 4]))

    for i in range(nk, nb * (nr + 1)):
        temp = w[i - 1][:]
        if i % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [_SBOX[b] for b in temp]
            temp[0] ^= _RCON[i // nk - 1]
        w.append([w[i - nk][j] ^ temp[j] for j in range(4)])

    return w


def _aes_encrypt_block(plain: bytes, key_schedule: list) -> bytes:
    state = _bytes_to_state(plain)
    state = _add_round_key(state, key_schedule, 0)
    for rnd in range(1, 10):
        state = _sub_bytes(state)
        state = _shift_rows(state)
        state = _mix_columns(state)
        state = _add_round_key(state, key_schedule, rnd)
    state = _sub_bytes(state)
    state = _shift_rows(state)
    state = _add_round_key(state, key_schedule, 10)
    return _state_to_bytes(state)


def _xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def _inc_counter(counter: bytearray) -> None:
    for i in range(15, -1, -1):
        counter[i] = (counter[i] + 1) & 0xff
        if counter[i] != 0:
            break


def _aes_ctr_encrypt(key_schedule: list, nonce: bytes, data: bytes) -> bytes:
    """AES-CTR mode encryption"""
    counter = bytearray(nonce + b'\x00\x00\x00\x00')
    result = bytearray()
    for i in range(0, len(data), 16):
        keystream = _aes_encrypt_block(bytes(counter), key_schedule)
        block = data[i:i + 16]
        result.extend(_xor_bytes(block, keystream[:len(block)]))
        _inc_counter(counter)
    return bytes(result)


def _ghash_mult(H: bytes, X: bytes) -> bytes:
    """GF(2^128) multiplication for GCM auth"""
    def gf_mult(a_int, b_int):
        r = 0
        for i in range(128):
            if (a_int >> (127 - i)) & 1:
                r ^= b_int
            if b_int & 1:
                b_int = (b_int >> 1) ^ 0xE1000000000000000000000000000000
            else:
                b_int >>= 1
        return r
    return struct.pack('>QQ', *divmod(gf_mult(
        struct.unpack('>QQ', H)[0] << 64 | struct.unpack('>QQ', H)[1],
        struct.unpack('>QQ', X)[0] << 64 | struct.unpack('>QQ', X)[1],
    ), 1 << 64))


def _gcm_ghash(H: bytes, aad: bytes, ciphertext: bytes) -> bytes:
    """GCM GHASH computation"""
    def pad(b):
        return b + b'\x00' * ((16 - len(b) % 16) % 16)

    Y = b'\x00' * 16
    for i in range(0, len(aad), 16):
        Y = _ghash_mult(H, _xor_bytes(Y, aad[i:i + 16].ljust(16, b'\x00')))
    for i in range(0, len(ciphertext), 16):
        Y = _ghash_mult(H, _xor_bytes(Y, ciphertext[i:i + 16].ljust(16, b'\x00')))
    len_block = struct.pack('>QQ', len(aad) * 8, len(ciphertext) * 8)
    return _ghash_mult(H, _xor_bytes(Y, len_block))


def _aes_gcm_encrypt(key: bytes, plaintext: bytes, aad: bytes = b'') -> bytes:
    """AES-128-GCM encrypt: returns nonce(12) + ciphertext + tag(16)"""
    nonce = os.urandom(12)
    key_schedule = _key_expansion(key)

    # Encrypt
    ciphertext = _aes_ctr_encrypt(key_schedule, nonce, plaintext)

    # Auth tag: H = AES_K(0^128), then GHASH
    H = _aes_encrypt_block(b'\x00' * 16, key_schedule)
    auth_input = aad + ciphertext
    tag = _gcm_ghash(H, aad, ciphertext)

    # XOR tag with encrypted counter=0
    J0 = nonce + b'\x00\x00\x00\x01'
    tag_mask = _aes_encrypt_block(J0, key_schedule)
    final_tag = _xor_bytes(tag, tag_mask)

    return nonce + ciphertext + final_tag


def _aes_gcm_decrypt(key: bytes, data: bytes, aad: bytes = b'') -> bytes:
    """AES-128-GCM decrypt: input = nonce(12) + ciphertext + tag(16)"""
    nonce = data[:12]
    ciphertext = data[12:-16]
    tag = data[-16:]
    key_schedule = _key_expansion(key)

    # Verify tag
    H = _aes_encrypt_block(b'\x00' * 16, key_schedule)
    computed = _gcm_ghash(H, aad, ciphertext)
    J0 = nonce + b'\x00\x00\x00\x01'
    tag_mask = _aes_encrypt_block(J0, key_schedule)
    computed_tag = _xor_bytes(computed, tag_mask)

    if computed_tag != tag:
        raise ValueError("AES-GCM authentication failed!")

    return _aes_ctr_encrypt(key_schedule, nonce, ciphertext)


# ── 对外接口 ────────────────────────────────────────────

def _derive_key(password: str, salt: bytes) -> bytes:
    """PBKDF2-SHA256 密钥派生 → 16 字节 AES-128 密钥"""
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 240000, dklen=16)
    return dk


def _get_or_create_key() -> bytes:
    """获取或创建本地 AES 密钥"""
    if KEY_FILE.exists():
        data = KEY_FILE.read_bytes()
        salt, key = data[:16], data[16:]
        # 验证密钥：用存储的 salt 重新派生，校验一致性
        derived = _derive_key("OpenClass@2026_TeacherToolbox", salt)
        if derived != key:
            raise RuntimeError("密钥文件损坏!")
        return key

    # 生成新密钥
    salt = os.urandom(16)
    key = _derive_key("OpenClass@2026_TeacherToolbox", salt)
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_bytes(salt + key)
    return key


def encrypt(plain_text: str) -> str:
    """加密明文 → Base64 密文 (nonce + ciphertext + tag)"""
    if not plain_text:
        return ""
    key = _get_or_create_key()
    cipher = _aes_gcm_encrypt(key, plain_text.encode())
    return base64.urlsafe_b64encode(cipher).decode()


def decrypt(cipher_text: str) -> str:
    """解密 Base64 密文 → 明文"""
    if not cipher_text:
        return ""
    key = _get_or_create_key()
    data = base64.urlsafe_b64decode(cipher_text.encode())
    plain = _aes_gcm_decrypt(key, data)
    return plain.decode()
