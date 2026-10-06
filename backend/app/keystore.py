"""API key storage in the OS keychain (Windows Credential Manager / macOS Keychain)."""

from __future__ import annotations

from typing import Protocol

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

SERVICE = "ResumeATS"
ACCOUNT = "llm-api-key"


class SecretStoreError(RuntimeError):
    pass


class SecretStore(Protocol):
    def get(self) -> str | None: ...
    def set(self, value: str) -> None: ...
    def delete(self) -> None: ...


class KeychainStore:
    def get(self) -> str | None:
        try:
            return keyring.get_password(SERVICE, ACCOUNT)
        except KeyringError as exc:
            raise SecretStoreError(f"Could not read the OS keychain: {exc}") from exc

    def set(self, value: str) -> None:
        try:
            keyring.set_password(SERVICE, ACCOUNT, value)
        except KeyringError as exc:
            raise SecretStoreError(f"Could not write to the OS keychain: {exc}") from exc

    def delete(self) -> None:
        try:
            keyring.delete_password(SERVICE, ACCOUNT)
        except PasswordDeleteError:
            pass  # nothing stored
        except KeyringError as exc:
            raise SecretStoreError(f"Could not delete from the OS keychain: {exc}") from exc
