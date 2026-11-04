import ipaddress
import os
import socket
import threading

from zeroconf import (
    Error as ZeroconfError,
    IPVersion,
    ServiceBrowser,
    ServiceInfo,
    ServiceListener,
    Zeroconf,
)


API_SERVICE_TYPE = "_totem-api._tcp.local."
ECG_SERVICE_TYPE = "_ecg._tcp.local."
ECG_SERVICE_CODE = "ECG-001"


def _api_port() -> int:
    value = os.getenv("ECG_API_PORT", "8000")
    try:
        port = int(value)
    except ValueError as error:
        raise RuntimeError("ECG_API_PORT debe ser un puerto TCP válido") from error
    if not 1 <= port <= 65535:
        raise RuntimeError("ECG_API_PORT debe estar entre 1 y 65535")
    return port


def _local_ipv4() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
            connection.connect(("224.0.0.251", 5353))
            address = connection.getsockname()[0]
            if address and not address.startswith("127."):
                return address
    except OSError:
        pass

    addresses = {
        result[4][0]
        for result in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        if result[4][0] and not result[4][0].startswith(("127.", "169.254."))
    }
    if not addresses:
        raise RuntimeError("No se encontró una dirección IPv4 de red para anunciar FastAPI")
    return sorted(addresses)[0]


class _EcgServiceListener(ServiceListener):
    def __init__(self, zeroconf: Zeroconf) -> None:
        self._zeroconf = zeroconf
        self._lock = threading.Lock()
        self._services: dict[str, dict[str, str]] = {}

    def add_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        self._update_service(service_type, name)

    def update_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        self._update_service(service_type, name)

    def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        with self._lock:
            self._services.pop(name, None)

    def _update_service(self, service_type: str, name: str) -> None:
        info = self._zeroconf.get_service_info(service_type, name, timeout=1000)
        if info is None or info.properties.get(b"codigo", b"").decode(
            "utf-8", errors="replace"
        ) != ECG_SERVICE_CODE:
            return

        addresses = [
            address
            for address in info.parsed_addresses(IPVersion.V4Only)
            if not address.startswith(("127.", "169.254."))
        ]
        if not addresses or not 1 <= info.port <= 65535:
            return

        service = {
            "codigo": ECG_SERVICE_CODE,
            "base_url": f"http://{addresses[0]}:{info.port}",
        }
        with self._lock:
            self._services[name] = service

    def snapshot(self) -> list[dict[str, str]]:
        with self._lock:
            return [service.copy() for service in self._services.values()]


class EcgMdnsDiscovery:
    def __init__(self) -> None:
        address = _local_ipv4()
        port = _api_port()
        hostname = socket.gethostname()[:40]
        host = f"totem-api-{hostname}.local."
        service_name = f"Totem ECG {hostname}.{API_SERVICE_TYPE}"
        service = ServiceInfo(
            API_SERVICE_TYPE,
            service_name,
            addresses=[ipaddress.IPv4Address(address).packed],
            port=port,
            properties={b"protocolo": b"1"},
            server=host,
        )
        zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        browser = None
        try:
            listener = _EcgServiceListener(zeroconf)
            browser = ServiceBrowser(zeroconf, ECG_SERVICE_TYPE, listener)
            zeroconf.register_service(service)
        except Exception:
            if browser is not None:
                browser.cancel()
            zeroconf.close()
            raise

        assert browser is not None
        self._zeroconf = zeroconf
        self._listener = listener
        self._browser = browser
        self._service = service

    def dispositivos(self) -> list[dict[str, str]]:
        return self._listener.snapshot()

    def close(self) -> None:
        self._browser.cancel()
        self._zeroconf.unregister_service(self._service)
        self._zeroconf.close()


_discovery: EcgMdnsDiscovery | None = None
_discovery_lock = threading.Lock()


def get_ecg_discovery() -> EcgMdnsDiscovery:
    global _discovery
    with _discovery_lock:
        if _discovery is None:
            _discovery = EcgMdnsDiscovery()
        return _discovery
