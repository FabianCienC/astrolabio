"""Traefik labels are matched to routes and Services without ever being split or published."""

from astrolabio_api.assembly.traffic import rates, route_traffic, service_traffic


def _label(ns: str, route: str, service: str, rule: int = 1) -> str:
    return (
        f"httproute-{ns}-{route}-gw-traefik-public-ep-web-{rule}-ac029082208ed7b3fa05"
        f"-svc-{ns}-{service}-0@kubernetesgateway"
    )


SNAPSHOT = {
    "traffic": [
        {
            "metric": {"service": _label("astrolabio", "astrolabio", "astrolabio-web")},
            "value": [0, "2"],
        },
        {
            "metric": {"service": _label("astrolabio", "astrolabio", "astrolabio-api", 0)},
            "value": [0, "0.5"],
        },
        {"metric": {"service": _label("cv", "cv", "cv")}, "value": [0, "NaN"]},
        {"metric": {}, "value": [0, "3"]},
    ]
}


def test_route_sums_every_backend_of_the_route():
    r = rates(SNAPSHOT)
    assert route_traffic(r, "astrolabio", "astrolabio").requests_per_second == 2.5


def test_service_names_with_dashes_never_mix():
    r = rates(SNAPSHOT)
    assert service_traffic(r, "astrolabio", "astrolabio-web").requests_per_second == 2
    assert service_traffic(r, "astrolabio", "astrolabio-api").requests_per_second == 0.5
    # A Service named "astrolabio" must not take its siblings' traffic.
    assert service_traffic(r, "astrolabio", "astrolabio").requests_per_second is None


def test_no_samples_is_no_data_not_zero():
    r = rates(SNAPSHOT)
    assert route_traffic(r, "cv", "cv").requests_per_second is None  # only a NaN series
    assert route_traffic(r, "hola", "hola").requests_per_second is None
