import httpx
from fathomark_sdk import FathomarkClient


def test_health_uses_root_health_endpoint():
    requests = []

    class Transport(httpx.BaseTransport):
        def handle_request(self, request):
            requests.append(request.url.path)
            return httpx.Response(200, json={"status": "ok"})

    with FathomarkClient(
        "http://test", httpx_client=httpx.Client(transport=Transport())
    ) as client:
        assert client.health() == {"status": "ok"}

    assert requests == ["/health"]
