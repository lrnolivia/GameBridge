#!/usr/bin/env python3
"""Core scanning and update routines for GameBridge."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import os
import re
import shutil
import string
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

APP_NAME = "GameBridge"
VERSION = "2.4"
HOME = Path.home()
MAX_TEXT_BYTES = 2 * 1024 * 1024

SUPPORTED_VALUE_FINGERPRINTS = frozenset({
    "003e7515364bc91b9d26d85fc3ae5373a6570230852bd75a6d91dfa85e2a05dd",
    "017dad3327e9be8164c504fb0bac7502079bc54ffe971a716a51d90c17f8ac86",
    "0335186346fa7de287acec005277bce04ec2b8b1b0dcea316f0e175a06c8423e",
    "0b59a4dd5f6b516df4d6e95bfaea8aceb3c4a72e0ea2750049ce5d9cc5dd8d82",
    "0bdc1cc88e448a97a2f85f9c04f99a105da0caf11e9e21c0b0341f8f8e48d770",
    "0cbe453f3450d19001c6ec287d26d12393ccf5daee72241ccb8f5d149735e2bc",
    "12b4472567564dd48756ddcb98f06138236a7cec19a802d01733903dea71432a",
    "230902215364bad0da623613f342eac05dd74a4a3b7c9abf7a927ee03b2ec7b8",
    "3491f77c94f2a59e0893d4c4796e3f3fe0ed9700bcf6acbd45c4eb48c0fabd3c",
    "3597a99db783d140b958684d11e5c78ffbcebd9b54f12f732e8e8102bcd0fb5f",
    "387ac6fc8abe31efc70cc63a2047ce95e86b2e9c3ec477111832435b05ebebb9",
    "3b475d7264a40b3ec1398ba8bd79afbd4f72ac70344e50d60cecc6e48af27657",
    "3eed361bff47540b0da35d93687e19bd6c693e5b1f146c1c1d475f0b8443a64c",
    "3f65136b958d93f3b99fc8490fa9f7a221541a732bd909345374fd3059722e27",
    "55cb03288665019a084d0d5989a73d6c23eb912a15f80330d7c18cfa5de68767",
    "57c4991869b96345e62c3f9a886b2503ea942aa6e50c129f51c1e1a48d8430ea",
    "57de4cf40144bdf7d00010f2f5557a7d642c2b9705309bfade167dd313e2ca93",
    "5c3393edd37c2b1ab0c130aaf43c568728aeaf779d03ab2de404fa4f8561dc86",
    "641a9327e7155a3b6de667091a7fb8e911d81b25608383566e40cd675facccaf",
    "64646fbc4b7b5a8e31ba9f701573f34fe7f6f7fef0d1a76652c377ddcda8a1cb",
    "6bf5105f3e35eab6fd66720279f23c5d5bdb35752ddf810fe3c717d11f9ed918",
    "6fd289d79b5bbb121e28cc2db5c66124b9b3d6058aa39781dc4eacdf5ad3d08e",
    "706f58b0dd4f869c8ab03b324c97c81137fe615c068bf8299a654875cf13017b",
    "74d8b53ad96a31c96c71fb5852d9dddd8849b81c61a4f59a255926c81cdb5ab8",
    "75dfb6a037947d7cd18aa1e5b92ca50f6da3396839b404aa5fc507ddc642d233",
    "85c76dcae2299d2235c793fe3425bd88376f5c4721cfddc1c9a9c452c20c5d33",
    "8c4bc1c232019873e933120876973d5fe8dc3925c0b886c6419dd70afbc80c34",
    "966369b1419838f0a43e3066996be01e91f3fbbb7dc6bae87487c65ff29315fd",
    "9a9364c5f560ba348c7ac8f67e9e11aee607add7db141b2f51f8ee7bc062bf1b",
    "a30ae234246fd6bc63405d3bc6b4e629c5ed77f451e9533ac71b7d6222a70d67",
    "a772074884a581681061a28b40703248898c2e5818525ec018099d7d66189f41",
    "ab8121af325447c6a311199aa9b8d274017a9b5601fd95964a2d4795a4689448",
    "abe3b80273709a48477daaa1bbe4b5e044d97a6ca46e1b4cbcb2c69e6dd10497",
    "b2b2ca7dd9c7ea33ece95f7e635e9b9d567fe8b3f1263800f6a4fcac15154bf1",
    "b5fc788198a129cd38e49d220bfb4ea01a22347f15267d5016048fd03899e658",
    "c2e251a6dd1438276ef900451d9daa347db340d73b708c1ae9e0d36e7d51f440",
    "c4e793c81ee40370d827d0cbe748d246cffca2cbe959383edf0976d041ece9e5",
    "c98fdbce5145934dcb2e4a33113079c4fc28a2766c25f422e8dff5fdca7007d1",
    "d2e124a92a721f299e60db89f1023632c60ef973ce5c2b73f1523f93c6a31bdd",
    "d2f12d879e340cc4231317f481402557b6481b9cdf68747e6a87d1a0fd09defc",
    "dcd69bed70a827d5fdda1d28272d508c795fb32cebab243d5208ec9ef89f6453",
    "e21e41206b41ea58f0f6dda6e7a91f793bb1252c139409c8b638c2f2e3175161",
    "ef21b5592240dac8ae10469ea5d728b97ff59c1a7785c4f1a870513ee187e387",
    "faf6db92a268b49f94c5ff610d6eed88b0e2755663e7b126d53d5078e9dbe4ca",
    "fe3811fe21af748f53a05a169da84013d11253a53e3ef80355d20419fd89042e",
})

IDENTITY_KEYS = [
    "UserName","Username","User_Name",
    "AccountName","Account_Name",
    "PersonaName","Persona_Name",
    "PlayerName","Player_Name",
    "Nickname","NickName","Persona",
]

ALLOWED_EXTS = {".ini",".cfg",".conf",".txt",".json",".xml",".toml",".yaml",".yml"}
EXACT_IDENTITY_NAMES = {
    "account_name.txt","force_account_name.txt",
    "username.txt","user_name.txt",
    "persona_name.txt","personaname.txt",
    "player_name.txt","nickname.txt",
}
SKIP_DIRS = {
    "_DLSS5_Backup","_OptiScaler_MFG_Backups",
    "backup","backups","_backup","_backups",
    "_CommonRedist","__Installer",".git",
}
DOC_RE = re.compile(r"^(readme|changelog|changes|license|credits|nfo|install|instructions|release[_ -]?notes?)", re.I)
KEY_RE = "|".join(re.escape(x) for x in sorted(IDENTITY_KEYS, key=len, reverse=True))
NORMALIZE_KV_RE = re.compile(
    rf'^(?P<prefix>\s*["\']?(?P<key>{KEY_RE})["\']?\s*(?:=|:)\s*)'
    rf'(?P<q>["\']?)(?P<value>.*?)(?P=q)'
    rf'(?P<tail>\s*,?\s*(?:[;#].*)?)$',
    re.I | re.M,
)
NORMALIZE_XML_RE = re.compile(
    rf'(?P<open><\s*(?P<key>{KEY_RE})\b[^>]*>\s*)'
    rf'(?P<value>.*?)'
    rf'(?P<close>\s*</\s*(?P=key)\s*>)',
    re.I | re.S,
)

def _value_fingerprint(value: str) -> str:
    normalized = value.strip().casefold().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()

def is_supported_source_value(value: str) -> bool:
    return _value_fingerprint(value) in SUPPORTED_VALUE_FINGERPRINTS

AUDIT_KV_RE = re.compile(
    rf'^(?P<prefix>\s*["\']?(?P<key>{KEY_RE})["\']?\s*(?:=|:)\s*)'
    rf'(?P<q>["\']?)(?P<value>.*?)(?P=q)\s*,?\s*(?:[;#].*)?$',
    re.I | re.M,
)
AUDIT_XML_RE = re.compile(
    rf'<\s*(?P<key>{KEY_RE})\b[^>]*>\s*(?P<value>.*?)\s*</\s*(?P=key)\s*>',
    re.I | re.S,
)
AUDIT_JSON_RE = re.compile(
    rf'["\'](?P<key>{KEY_RE})["\']\s*:\s*["\'](?P<value>[^"\']*)["\']',
    re.I,
)
AUDIT_MAX_VALUE = 128

# ANSI -----------------------------------------------------------------------

def _enable_windows_vt() -> None:
    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass

_enable_windows_vt()
USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

def _ansi(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if USE_COLOR else s

def bold(s: str) -> str: return _ansi("1", s)
def cyan(s: str) -> str: return _ansi("38;2;93;220;232", s)
def green(s: str) -> str: return _ansi("38;2;118;185;0", s)
def yellow(s: str) -> str: return _ansi("38;2;255;200;87", s)
def red(s: str) -> str: return _ansi("38;2;255;111;105", s)
def dim(s: str) -> str: return _ansi("2", s)

def clear() -> None:
    if sys.stdout.isatty():
        print("\033[2J\033[H", end="")

def banner() -> None:
    print()
    print("  " + bold("GameBridge") + "  " + green("PLAYER NAME COMPATIBILITY"))
    print("  " + dim("REVIEW · BACK UP · UPDATE · VERIFY"))
    print("  " + green("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
    print("  Keep supported player-name settings consistent across a game library.")
    print()

def heading(s: str) -> None:
    print("\n  " + cyan(s))

def kv(k: str, v: object, width: int = 24) -> None:
    print("  " + dim(k.ljust(width)) + str(v))

def ok(s: str) -> None:
    print("  " + green("✓ ") + s)

def warn(s: str) -> None:
    print("  " + yellow("! ") + s)

def fail(s: str) -> None:
    print("  " + red("STOP  ") + s, file=sys.stderr)

def ask(prompt: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"  {prompt}{suffix}: ").strip()
    return value or (default or "")

def confirm(prompt: str, default: bool = False) -> bool:
    tail = " [Y/n]" if default else " [y/N]"
    raw = input(f"  {prompt}{tail}: ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes"}

class Stop(RuntimeError):
    pass

# Steam account discovery -----------------------------------------------------

@dataclass(frozen=True)
class SteamIdentity:
    steam_id: str
    account_name: str
    persona_name: str
    most_recent: bool
    timestamp: int
    source: Path


def _vdf_unescape(value: str) -> str:
    return value.replace(r'\\"', '"').replace(r'\\\\', '\\')


def parse_loginusers_vdf(path: Path) -> list[SteamIdentity]:
    """Read Steam account records from loginusers.vdf."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []

    identities: list[SteamIdentity] = []
    steam_id: Optional[str] = None
    fields: dict[str, str] = {}
    waiting_for_brace = False
    in_account = False

    account_line = re.compile(r'^\s*"(?P<id>\d{15,20})"\s*$')
    field_line = re.compile(r'^\s*"(?P<key>[^"]+)"\s*"(?P<value>(?:\\.|[^"])*)"\s*$')

    def finish() -> None:
        nonlocal steam_id, fields, waiting_for_brace, in_account
        if steam_id:
            player_name = _vdf_unescape(fields.get("PersonaName", "")).strip()
            account = _vdf_unescape(fields.get("AccountName", "")).strip()
            try:
                ts = int(fields.get("Timestamp", "0") or 0)
            except ValueError:
                ts = 0
            identities.append(
                SteamIdentity(
                    steam_id=steam_id,
                    account_name=account,
                    persona_name=player_name,
                    most_recent=fields.get("MostRecent", "0") == "1",
                    timestamp=ts,
                    source=path,
                )
            )
        steam_id = None
        fields = {}
        waiting_for_brace = False
        in_account = False

    for raw in text.splitlines():
        line = raw.strip()
        if not in_account and not waiting_for_brace:
            m = account_line.match(raw)
            if m:
                if steam_id:
                    finish()
                steam_id = m.group("id")
                waiting_for_brace = True
            continue
        if waiting_for_brace:
            if line == "{":
                waiting_for_brace = False
                in_account = True
            elif line:
                finish()
            continue
        if in_account:
            if line == "}":
                finish()
                continue
            m = field_line.match(raw)
            if m:
                fields[m.group("key")] = _vdf_unescape(m.group("value"))

    if steam_id:
        finish()
    return identities


def _steam_roots_windows() -> list[Path]:
    roots: list[Path] = []
    env = os.environ.get("GAMEBRIDGE_STEAM_ROOT") or os.environ.get("STEAM_PATH")
    if env:
        roots.append(Path(env))

    try:
        import winreg  # type: ignore
        probes = [
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
        ]
        for hive, key_name, value_name in probes:
            try:
                with winreg.OpenKey(hive, key_name) as key:
                    value, _ = winreg.QueryValueEx(key, value_name)
                    if value:
                        roots.append(Path(value))
            except OSError:
                pass
    except Exception:
        pass

    for env_name in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env_name)
        if base:
            roots.append(Path(base) / "Steam")
    return roots


def _steam_roots_linux() -> list[Path]:
    env = os.environ.get("GAMEBRIDGE_STEAM_ROOT") or os.environ.get("STEAM_PATH")
    roots = [Path(env).expanduser()] if env else []
    roots.extend([
        HOME / ".local" / "share" / "Steam",
        HOME / ".steam" / "steam",
        HOME / ".steam" / "root",
        HOME / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
    ])
    return roots


def steam_roots() -> list[Path]:
    raw = _steam_roots_windows() if os.name == "nt" else _steam_roots_linux()
    result: list[Path] = []
    seen: set[str] = set()
    for root in raw:
        try:
            key = str(root.expanduser().resolve(strict=False)).casefold() if os.name == "nt" else str(root.expanduser().resolve(strict=False))
        except OSError:
            key = str(root).casefold() if os.name == "nt" else str(root)
        if key not in seen:
            seen.add(key)
            result.append(root.expanduser())
    return result


def detect_steam_identities() -> list[SteamIdentity]:
    all_rows: list[SteamIdentity] = []
    seen: set[tuple[str, str]] = set()
    for root in steam_roots():
        path = root / "config" / "loginusers.vdf"
        for row in parse_loginusers_vdf(path):
            stable_name = (row.account_name or row.persona_name).casefold()
            key = (row.steam_id, stable_name)
            if key not in seen:
                seen.add(key)
                all_rows.append(row)
    all_rows.sort(
        key=lambda r: (r.most_recent, r.timestamp, bool(r.account_name), bool(r.persona_name)),
        reverse=True,
    )
    return all_rows


def steam_login_name(identity: SteamIdentity) -> str:
    """Return the account login name."""
    return (identity.account_name or identity.persona_name).strip()


def detect_steam_username() -> Optional[SteamIdentity]:
    rows = [r for r in detect_steam_identities() if steam_login_name(r)]
    return rows[0] if rows else None

# Library discovery -----------------------------------------------------------

LIBRARY_NAMES = {"non-steam games", "non steam games", "nonsteam games"}


def _score_library(path: Path) -> tuple[int, int]:
    try:
        dirs = sum(1 for x in path.iterdir() if x.is_dir())
        files = sum(1 for x in path.iterdir() if x.is_file())
        return (dirs, files)
    except OSError:
        return (0, 0)


def discover_libraries() -> list[Path]:
    override = os.environ.get("GAMEBRIDGE_LIBRARY") or os.environ.get("NON_STEAM_GAMES_ROOT")
    if override:
        p = Path(override).expanduser()
        return [p] if p.is_dir() else []

    found: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        if not p.is_dir():
            return
        try:
            rp = p.resolve()
        except OSError:
            rp = p
        key = str(rp).casefold() if os.name == "nt" else str(rp)
        if key not in seen:
            seen.add(key)
            found.append(rp)

    if os.name == "nt":
        for letter in string.ascii_uppercase:
            root = Path(f"{letter}:\\")
            if not root.exists():
                continue
            for name in ("Non-Steam Games", "Non Steam Games", "NonSteam Games"):
                add(root / name)
        for base in (HOME / "Games", HOME / "Documents"):
            if base.is_dir() and base.name.casefold() in LIBRARY_NAMES:
                add(base)
    else:
        user = os.environ.get("USER", "")
        bases = [
            Path("/var/mnt"),
            Path("/mnt"),
            Path("/run/media") / user if user else Path("/run/media"),
            Path("/media") / user if user else Path("/media"),
            HOME,
        ]
        for base in bases:
            if not base.is_dir():
                continue
            base_depth = len(base.parts)
            try:
                for dirpath, dirnames, _ in os.walk(base):
                    p = Path(dirpath)
                    depth = len(p.parts) - base_depth
                    if depth > 5:
                        dirnames[:] = []
                        continue
                    dirnames[:] = [d for d in dirnames if d not in {".cache", ".local", ".steam", ".var", "node_modules", ".git"}]
                    if p.name.casefold() in LIBRARY_NAMES:
                        add(p)
                        dirnames[:] = []
            except (PermissionError, OSError):
                pass

    found.sort(key=_score_library, reverse=True)
    return found

# Game configuration updates --------------------------------------------------

@dataclass
class Change:
    game: str
    path: Path
    original_text: str
    updated_text: str
    encoding: str
    reasons: list[str]


def detect_text(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8"), "utf-8-sig"
    if data.startswith(b"\xff\xfe"):
        return data[2:].decode("utf-16-le"), "utf-16-le-bom"
    if data.startswith(b"\xfe\xff"):
        return data[2:].decode("utf-16-be"), "utf-16-be-bom"
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("cp1252"), "cp1252"


def encode_text(text: str, kind: str) -> bytes:
    if kind == "utf-8-sig":
        return b"\xef\xbb\xbf" + text.encode("utf-8")
    if kind == "utf-16-le-bom":
        return b"\xff\xfe" + text.encode("utf-16-le")
    if kind == "utf-16-be-bom":
        return b"\xfe\xff" + text.encode("utf-16-be")
    if kind == "cp1252":
        return text.encode("cp1252", errors="replace")
    return text.encode("utf-8")


def game_name(root: Path, path: Path) -> str:
    rel = path.relative_to(root)
    return rel.parts[0] if len(rel.parts) > 1 else "_ROOT"


def should_skip(root: Path, path: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    skip_lower = {x.casefold() for x in SKIP_DIRS}
    return any(part.casefold() in skip_lower for part in parts[:-1])


def normalize_text(path: Path, text: str, new_name: str) -> tuple[str, list[str]]:
    updated = text
    reasons: list[str] = []

    if path.name.casefold() in EXACT_IDENTITY_NAMES:
        old = updated.strip()
        if old and "\n" not in old and "\r" not in old and is_supported_source_value(old):
            lead = updated[: len(updated) - len(updated.lstrip())]
            tail = updated[len(updated.rstrip()):]
            updated = lead + new_name + tail
            reasons.append(f"player-name file: {old} → {new_name}")

    def kv_repl(m: re.Match[str]) -> str:
        old = m.group("value").strip()
        if not is_supported_source_value(old):
            return m.group(0)
        reasons.append(f'{m.group("key")}={old} → {new_name}')
        return m.group("prefix") + m.group("q") + new_name + m.group("q") + m.group("tail")

    updated = NORMALIZE_KV_RE.sub(kv_repl, updated)

    def xml_repl(m: re.Match[str]) -> str:
        old = m.group("value").strip()
        if not is_supported_source_value(old):
            return m.group(0)
        reasons.append(f'{m.group("key")}={old} → {new_name}')
        return m.group("open") + new_name + m.group("close")

    updated = NORMALIZE_XML_RE.sub(xml_repl, updated)
    return updated, list(dict.fromkeys(reasons))


@dataclass
class PlayerNameEvidence:
    value: str
    path: Path
    key: str


@dataclass
class GameAudit:
    game: str
    path: Path
    player_names: list[str]
    evidence: list[PlayerNameEvidence]
    files_checked: int


def _clean_audit_value(value: str) -> Optional[str]:
    value = value.strip().strip('"\'').strip()
    if not value or len(value) > AUDIT_MAX_VALUE:
        return None
    if "\n" in value or "\r" in value or "\x00" in value:
        return None
    if value in {"{}", "[]", "null", "None"}:
        return None
    return value


def extract_player_name_evidence(path: Path, text: str) -> list[tuple[str, str]]:
    """Return recognized identity values from a config without modifying it."""
    found: list[tuple[str, str]] = []
    if path.name.casefold() in EXACT_IDENTITY_NAMES:
        value = _clean_audit_value(text)
        if value:
            found.append(("identity file", value))

    for m in AUDIT_KV_RE.finditer(text):
        value = _clean_audit_value(m.group("value"))
        if value:
            found.append((m.group("key"), value))

    for m in AUDIT_XML_RE.finditer(text):
        value = _clean_audit_value(m.group("value"))
        if value:
            found.append((m.group("key"), value))

    for m in AUDIT_JSON_RE.finditer(text):
        value = _clean_audit_value(m.group("value"))
        if value:
            found.append((m.group("key"), value))

    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for key, value in found:
        sig = (key.casefold(), value.casefold())
        if sig not in seen:
            seen.add(sig)
            out.append((key, value))
    return out


def _library_games(root: Path) -> list[Path]:
    if not root.is_dir():
        raise Stop(f"Games folder does not exist: {root}")
    skip_lower = {x.casefold() for x in SKIP_DIRS}
    games: list[Path] = []
    try:
        for entry in root.iterdir():
            if entry.is_dir() and entry.name.casefold() not in skip_lower and not entry.name.startswith("."):
                games.append(entry)
    except OSError as exc:
        raise Stop(f"Could not read game library: {exc}")
    games.sort(key=lambda x: x.name.casefold())
    return games


def audit_library(root: Path, verbose: bool = True) -> list[GameAudit]:
    """Read recognized player-name settings without modifying files."""
    games = _library_games(root)
    results: list[GameAudit] = []
    skip_lower = {x.casefold() for x in SKIP_DIRS}

    if verbose:
        heading("Auditing game library")
        kv("Library", root)
        kv("Mode", "read-only · no files changed")
        kv("Inspection", "known identity fields in text/config files · max 2 MiB")
        print()

    for game_dir in games:
        evidence: list[PlayerNameEvidence] = []
        files_checked = 0
        for dirpath, dirnames, filenames in os.walk(game_dir):
            dirpath_p = Path(dirpath)
            dirnames[:] = [d for d in dirnames if d.casefold() not in skip_lower]
            for filename in filenames:
                path = dirpath_p / filename
                if should_skip(root, path):
                    continue
                if path.suffix.casefold() not in ALLOWED_EXTS:
                    continue
                if DOC_RE.match(path.name):
                    continue
                try:
                    if path.stat().st_size > MAX_TEXT_BYTES:
                        continue
                    files_checked += 1
                    text, _ = detect_text(path.read_bytes())
                    for key, value in extract_player_name_evidence(path, text):
                        evidence.append(PlayerNameEvidence(value=value, path=path, key=key))
                except (OSError, UnicodeError):
                    continue

        player_names: list[str] = []
        seen_values: set[str] = set()
        for item in evidence:
            sig = item.value.casefold()
            if sig not in seen_values:
                seen_values.add(sig)
                player_names.append(item.value)
        results.append(GameAudit(game=game_dir.name, path=game_dir, player_names=player_names, evidence=evidence, files_checked=files_checked))

    if verbose:
        kv("Games found", len(results))
        kv("Games with a name", sum(1 for x in results if x.player_names))
    return results


def _audit_status(row: GameAudit, desired: Optional[str]) -> str:
    if not row.player_names:
        return dim("NOT FOUND")
    if len(row.player_names) > 1:
        return yellow("MIXED")
    value = row.player_names[0]
    if desired and value.casefold() == desired.casefold():
        return green("LOCAL")
    if is_supported_source_value(value):
        return yellow("SUPPORTED")
    return cyan("CUSTOM")


def print_audit(results: list[GameAudit], desired: Optional[str] = None) -> None:
    heading("Library audit")
    if not results:
        warn("No top-level game folders found")
        return

    term_width = max(70, shutil.get_terminal_size((110, 30)).columns - 4)
    game_w = min(42, max(24, term_width // 3))
    name_w = min(38, max(22, term_width - game_w - 18))
    print("  " + dim(f"{'GAME':<{game_w}}{'CURRENT NAME':<{name_w}}STATUS"))
    print("  " + dim("─" * min(term_width, game_w + name_w + 14)))

    for row in results:
        if not row.player_names:
            player_name = "—"
        elif len(row.player_names) == 1:
            player_name = row.player_names[0]
        else:
            shown = " · ".join(row.player_names[:3])
            player_name = shown + (f" · +{len(row.player_names)-3}" if len(row.player_names) > 3 else "")
        if len(player_name) > name_w - 2:
            player_name = player_name[: max(1, name_w - 3)] + "…"
        game = row.game
        if len(game) > game_w - 2:
            game = game[: max(1, game_w - 3)] + "…"
        print("  " + game.ljust(game_w) + player_name.ljust(name_w) + _audit_status(row, desired))

    print()
    kv("Games found", len(results))
    kv("Name found", sum(1 for x in results if x.player_names))
    kv("No name found", sum(1 for x in results if not x.player_names))
    kv("Multiple names found", sum(1 for x in results if len(x.player_names) > 1))
    if desired:
        kv("Name to use", desired)
        kv("Already local", sum(1 for x in results if len(x.player_names) == 1 and x.player_names[0].casefold() == desired.casefold()))
    print()
    print("  " + dim("Audit is read-only. NOT FOUND means GameBridge did not find a recognized identity field;"))
    print("  " + dim("it does not prove the game has no player name."))


def scan_library(root: Path, new_name: str, verbose: bool = True) -> list[Change]:
    if not root.is_dir():
        raise Stop(f"Games folder does not exist: {root}")
    if not new_name.strip():
        raise Stop("Name to use is empty")

    if verbose:
        heading("Scanning game library")
        kv("Library", root)
        kv("Name to use", green(new_name))
        kv("Inspection", "small text/config files only · max 2 MiB")
        print()

    changes: list[Change] = []
    skip_lower = {x.casefold() for x in SKIP_DIRS}
    candidate_count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirpath_p = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d.casefold() not in skip_lower]
        for filename in filenames:
            path = dirpath_p / filename
            if should_skip(root, path):
                continue
            if path.suffix.casefold() not in ALLOWED_EXTS:
                continue
            if DOC_RE.match(path.name):
                continue
            try:
                if path.stat().st_size > MAX_TEXT_BYTES:
                    continue
                candidate_count += 1
                text, enc = detect_text(path.read_bytes())
                updated, reasons = normalize_text(path, text, new_name)
                if updated != text:
                    changes.append(Change(game_name(root, path), path, text, updated, enc, reasons))
            except (OSError, UnicodeError):
                continue

    if verbose:
        kv("Text/config candidates", candidate_count)
        kv("Configs with matches", len(changes))
    return changes


def print_changes(root: Path, changes: list[Change], new_name: str) -> None:
    heading("Compatibility summary")
    if not changes:
        ok("No player-name updates found")
        kv("Result", "nothing would be changed")
        return

    grouped: dict[str, list[Change]] = {}
    for change in changes:
        grouped.setdefault(change.game, []).append(change)

    header = f"{'GAME':<42}{'FILES':>7}  STATUS"
    print("  " + dim(header))
    print("  " + dim("─" * min(78, shutil.get_terminal_size((100, 30)).columns - 4)))
    for game in sorted(grouped, key=str.casefold):
        print("  " + game[:40].ljust(42) + str(len(grouped[game])).rjust(7) + "  " + yellow("MATCH"))
    print()
    kv("Games affected", len(grouped))
    kv("Files affected", len(changes))
    kv("Replacement", new_name)

    heading("Supported configs")
    for change in changes:
        try:
            rel = change.path.relative_to(root)
        except ValueError:
            rel = change.path
        print("  " + yellow("• ") + str(rel))
        for reason in change.reasons:
            print("    " + dim(reason))


def default_backup_root() -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if os.name == "nt":
        base = HOME / "Saved Games" / "GameBridge_Backups"
    else:
        docs = HOME / "Documents"
        base = docs / "GameBridge_Backups" if docs.exists() else HOME / "GameBridge_Backups"
    return base / f"ALL_GAMES_{stamp}"


def apply_changes(root: Path, changes: list[Change], new_name: str) -> tuple[int, int, Path]:
    if not changes:
        return (0, 0, default_backup_root())

    backup_root = default_backup_root()
    changed: list[Path] = []
    failed: list[Path] = []

    heading("Backup + apply")
    kv("Backup", backup_root)
    print()

    for change in changes:
        try:
            rel = change.path.relative_to(root)
            backup = backup_root / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(change.path, backup)
            change.path.write_bytes(encode_text(change.updated_text, change.encoding))
            changed.append(change.path)
            print("  " + green("✓ ") + change.game + "  " + dim(str(rel)))
        except OSError as exc:
            failed.append(change.path)
            warn(f"Could not update {change.path}: {exc}")

    heading("Verification")
    verified: list[Path] = []
    for path in changed:
        try:
            text, _ = detect_text(path.read_bytes())
            if new_name.casefold() in text.casefold():
                verified.append(path)
            else:
                failed.append(path)
                warn(f"Verification failed: {path}")
        except (OSError, UnicodeError):
            failed.append(path)
            warn(f"Verification failed: {path}")

    print()
    if not failed:
        ok("Player-name update complete")
    else:
        warn("Update completed with warnings")
    kv("Configs changed", len(changed))
    kv("Configs verified", len(verified))
    kv("Verification failures", len(set(failed)))
    kv("Backup", backup_root)
    return (len(verified), len(set(failed)), backup_root)


def print_safety() -> None:
    heading("Safety boundary")
    kv("Edits", "recognized player-name fields only")
    kv("Backups", "every modified config is copied first")
    kv("SteamID / AccountID", "NOT MODIFIED")
    kv("UserID / AppID", "NOT MODIFIED")
    kv("Save files", "NOT MODIFIED")
    kv("Executables / DLLs", "NOT MODIFIED")
    kv("Game assets", "NOT MODIFIED")
    kv("Documentation", "NOT MODIFIED")

# Interactive shell -----------------------------------------------------------

@dataclass
class Session:
    root: Optional[Path]
    player_name: Optional[str]
    identity: Optional[SteamIdentity]
    player_name_source: str


def initial_session(root_override: Optional[str], player_name_override: Optional[str]) -> Session:
    root = Path(root_override).expanduser() if root_override else None
    if root is None:
        libs = discover_libraries()
        root = libs[0] if libs else None

    manual = (
        player_name_override
        or os.environ.get("GAMEBRIDGE_USERNAME")
        or os.environ.get("GAMEBRIDGE_PLAYER_NAME")
    )
    if manual:
        return Session(root, manual.strip(), None, "manual override")
    ident = detect_steam_username()
    if ident:
        return Session(root, steam_login_name(ident), ident, "Steam AccountName · loginusers.vdf")
    return Session(root, None, None, "not detected")


def describe_session(session: Session) -> None:
    kv("Name to use", green(session.player_name) if session.player_name else yellow("not set"))
    kv("Detected from", session.player_name_source)
    if session.identity:
        kv("Steam username", green(steam_login_name(session.identity)))
        if session.identity.persona_name:
            kv("Friendly name", session.identity.persona_name)
        kv("Steam selection", "MostRecent" if session.identity.most_recent else "newest timestamp")
    kv("Games folder", session.root if session.root else yellow("not detected"))
    kv("Safety", "IDs · saves · binaries untouched")


def require_root(session: Session) -> Path:
    if not session.root or not session.root.is_dir():
        value = ask("Games folder path")
        p = Path(value).expanduser()
        if not p.is_dir():
            raise Stop(f"Games folder does not exist: {p}")
        session.root = p
    return session.root


def require_session(session: Session) -> tuple[Path, str]:
    if not session.player_name:
        value = ask("Name to use")
        if not value:
            raise Stop("A name is required")
        session.player_name = value
        session.player_name_source = "manual override"
        session.identity = None
    root = require_root(session)
    return root, session.player_name


def _apply_steam_identity(session: Session, row: SteamIdentity) -> None:
    username = steam_login_name(row)
    if not username:
        raise Stop("Selected Steam account has no usable AccountName")
    session.player_name = username
    session.identity = row
    session.player_name_source = "Steam AccountName · loginusers.vdf"
    ok(f"Name to use → {username}")
    if row.persona_name and row.persona_name != username:
        kv("Friendly name", row.persona_name)


def set_manual_profile_name(session: Session) -> None:
    """Set a manual player name."""
    heading("Choose a name")
    current = session.player_name or ""
    if current:
        kv("Current", current)
    value = input("  Enter name: ").strip()
    if not value:
        if current:
            warn("No change made")
            return
        raise Stop("Name cannot be empty")
    session.player_name = value
    session.identity = None
    session.player_name_source = "manual override"
    ok(f"Name to use → {value}")


def choose_profile_name(session: Session) -> None:
    """Choose a detected Steam account or enter a player name."""
    rows = [r for r in detect_steam_identities() if steam_login_name(r)]

    heading("Choose a name")
    kv("Current", green(session.player_name) if session.player_name else yellow("not set"))
    print()

    for i, row in enumerate(rows, 1):
        flags = []
        if row.most_recent:
            flags.append("MostRecent")
        if i == 1:
            flags.append("recommended")
        username = steam_login_name(row)
        friendly = f" · {row.persona_name}" if row.persona_name and row.persona_name != username else ""
        flag_text = " · ".join(flags)
        suffix = ("  " + dim(flag_text)) if flag_text else ""
        kv(str(i), f"{username}{friendly}{suffix}")

    kv("M", "Enter a different name")
    kv("0", "Back")
    default = "1" if rows else "M"
    raw = ask("Choose", default).strip()
    if raw == "0":
        return
    if raw.lower() == "m":
        set_manual_profile_name(session)
        return
    try:
        idx = int(raw)
        row = rows[idx - 1]
    except (ValueError, IndexError):
        raise Stop("Invalid profile selection")
    _apply_steam_identity(session, row)


def choose_library(session: Session) -> None:
    libs = discover_libraries()
    heading("Choose your games folder")
    if libs:
        for i, path in enumerate(libs, 1):
            score = _score_library(path)[0]
            kv(str(i), f"{path}  " + dim(f"{score} folders"))
        kv("M", "Choose another folder")
        raw = ask("Choose", "1")
        if raw.strip().lower() != "m":
            try:
                session.root = libs[int(raw) - 1]
                ok(f"Games folder → {session.root}")
                return
            except (ValueError, IndexError):
                raise Stop("Invalid library selection")
    value = ask("Games folder path")
    p = Path(value).expanduser()
    if not p.is_dir():
        raise Stop(f"Games folder does not exist: {p}")
    session.root = p
    ok(f"Games folder → {session.root}")


def settings_menu(session: Session) -> None:
    """Open interactive settings."""
    while True:
        clear()
        banner()
        heading("Settings")
        kv("Name to use", green(session.player_name) if session.player_name else yellow("not set"))
        kv("Games folder", session.root if session.root else yellow("not detected"))
        print()
        kv("1", "Name to use")
        kv("2", "Games folder")
        kv("0", "Back")
        print()

        choice = ask("Choose", "1")
        if choice == "0":
            return
        try:
            if choice == "1":
                choose_profile_name(session)
            elif choice == "2":
                choose_library(session)
            else:
                warn("Unknown menu choice")
        except Stop as exc:
            fail(str(exc))
        except KeyboardInterrupt:
            print("\n  Cancelled.")
        except Exception as exc:
            fail(f"Unexpected error: {exc}")

        print()
        input("  Press ENTER to return to Settings…")


def interactive_main(root_override: Optional[str] = None, player_name_override: Optional[str] = None) -> int:
    session = initial_session(root_override, player_name_override)

    while True:
        clear()
        banner()
        describe_session(session)
        print()
        kv("1", "Review games")
        kv("2", "Sync player names")
        kv("3", "Settings")
        kv("0", "Exit")
        print()

        choice = ask("Choose", "1")
        try:
            if choice == "0":
                return 0
            if choice == "1":
                root = require_root(session)
                audit = audit_library(root)
                print_audit(audit, session.player_name)
            elif choice == "2":
                root, player_name = require_session(session)
                changes = scan_library(root, player_name)
                print_changes(root, changes, player_name)
                if changes:
                    print()
                    kv("Backup", "automatic before every write")
                    kv("Protected", "Steam IDs · saves · binaries · assets")
                    if confirm(f"Sync {len(changes)} config(s) to use '{player_name}'?"):
                        apply_changes(root, changes, player_name)
                    else:
                        warn("No files changed")
            elif choice == "3":
                settings_menu(session)
                continue
            else:
                warn("Unknown menu choice")
        except Stop as exc:
            fail(str(exc))
        except KeyboardInterrupt:
            print("\n  Cancelled.")
        except Exception as exc:
            fail(f"Unexpected error: {exc}")

        print()
        input("  Press ENTER to return to GameBridge…")

# Command line ---------------------------------------------------------------

def cli_main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="GameBridge player-name compatibility utility")
    action = p.add_mutually_exclusive_group()
    action.add_argument("--audit", action="store_true", help="read-only inventory of recognized player-name settings")
    action.add_argument("--scan", action="store_true", help="scan and preview only")
    action.add_argument("--apply", action="store_true", help="scan, back up, update, and verify")
    p.add_argument("--root", help="game library root")
    p.add_argument("--player-name", "--username", dest="player_name", help="player name to use")
    p.add_argument("--yes", action="store_true", help="do not ask for apply confirmation")
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args(argv)

    global USE_COLOR
    if args.no_color:
        USE_COLOR = False

    if not (args.audit or args.scan or args.apply):
        return interactive_main(args.root, args.player_name)

    session = initial_session(args.root, args.player_name)
    if args.audit:
        try:
            root = require_root(session)
        except (Stop, EOFError) as exc:
            fail(str(exc))
            return 2
        banner()
        describe_session(session)
        results = audit_library(root)
        print_audit(results, session.player_name)
        return 0

    try:
        root, player_name = require_session(session)
    except (Stop, EOFError) as exc:
        fail(str(exc))
        return 2

    banner()
    describe_session(session)
    changes = scan_library(root, player_name)
    print_changes(root, changes, player_name)
    if args.scan or not changes:
        return 0
    if not args.yes and sys.stdin.isatty() and not confirm(f"Fix {len(changes)} config(s) to use '{player_name}'?"):
        warn("No files changed")
        return 0
    _, failed_count, _ = apply_changes(root, changes, player_name)
    return 1 if failed_count else 0


if __name__ == "__main__":
    raise SystemExit(cli_main())
