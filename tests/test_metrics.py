def test_metrics_content_type(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain; version=0.0.4")


def test_request_counter_has_endpoint_and_code_labels(client):
    client.get("/health")
    resp = client.get("/metrics")
    text = resp.text
    assert 'http_requests_total{code="200",endpoint="/health"}' in text


def test_latency_histogram_exposed(client):
    client.get("/health")
    resp = client.get("/metrics")
    assert "http_request_duration_seconds_bucket" in resp.text
    assert 'route="/health"' in resp.text


def test_build_info_gauge_exposes_sha(client):
    resp = client.get("/metrics")
    assert "app_build_info" in resp.text
