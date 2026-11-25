from __future__ import annotations

import re
from typing import Any

import httpx
import pytest
from helpers import Reply, cut_off, mock_fiz, raw

from fiz_sdk import (
    Fiz,
    FizApiError,
    FizAuthenticationError,
    FizBadRequestError,
    FizConflictError,
    FizConnectionError,
    FizError,
    FizNotFoundError,
    FizRateLimitError,
    FizResponseInfo,
    FizServerError,
    FizTimeoutError,
)
from fiz_sdk.types import CreateCustomerDto

customer: CreateCustomerDto = {"name": "Example customer", "country": "PT"}
UUID = re.compile(r"^[0-9a-f-]{36}$")


class TestCredentials:
    def test_sends_the_api_key_as_x_api_key(self) -> None:
        mock = mock_fiz([Reply(200, {})])
        mock.fiz.company.retrieve()
        assert mock.requests[0].headers["x-api-key"] == "fiz_live_key"
        assert "authorization" not in mock.requests[0].headers
        assert str(mock.requests[0].url) == "https://api.fiz.co/company"

    def test_sends_an_access_token_as_a_bearer_token(self) -> None:
        mock = mock_fiz([Reply(200, {})], api_key=None, access_token="fiz_oat_token")
        mock.fiz.company.retrieve()
        assert mock.requests[0].headers["authorization"] == "Bearer fiz_oat_token"
        assert "x-api-key" not in mock.requests[0].headers

    def test_reads_fiz_api_key_when_no_credential_is_passed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FIZ_API_KEY", "fiz_test_from_env")
        mock = mock_fiz([Reply(200, {})], api_key=None)
        mock.fiz.company.retrieve()
        assert mock.requests[0].headers["x-api-key"] == "fiz_test_from_env"
        assert mock.fiz.environment == "sandbox"

    def test_refuses_both_credentials_and_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FIZ_API_KEY", "")
        with pytest.raises(FizError):
            Fiz(api_key="a", access_token="b")
        with pytest.raises(FizError, match="FIZ_API_KEY"):
            Fiz()
        monkeypatch.delenv("FIZ_API_KEY")
        with pytest.raises(FizError, match="FIZ_API_KEY"):
            Fiz()

    def test_reports_the_environment_from_the_key_prefix(self) -> None:
        assert Fiz(api_key="fiz_test_x").environment == "sandbox"
        assert Fiz(api_key="fiz_live_x").environment == "production"
        assert Fiz(access_token="fiz_oat_x").environment == "production"

    def test_identifies_itself_and_the_integration_in_the_user_agent(self) -> None:
        mock = mock_fiz([Reply(200, {})], app_info={"name": "acme-shop", "version": "2.1.0"})
        mock.fiz.company.retrieve()
        assert re.match(
            r"^fiz-sdk-python/\d+\.\d+\.\d+ python/\S+ acme-shop/2\.1\.0$",
            mock.requests[0].headers["user-agent"],
        )


class TestRequests:
    def test_expands_path_parameters_and_encodes_them(self) -> None:
        mock = mock_fiz([Reply(200, {})])
        mock.fiz.invoices.retrieve("a/b")
        assert mock.requests[0].url.raw_path == b"/invoices/a%2Fb"

    def test_serialises_query_parameters_repeating_lists_and_skipping_none(self) -> None:
        mock = mock_fiz([Reply(200, [])])
        mock.fiz.bank.transactions(
            {"connectionId": "c1", "types": ["Purchase", "Transfer"], "searchString": None}
        )
        query = mock.requests[0].url.params
        assert query.get_list("types") == ["Purchase", "Transfer"]
        assert query.get("connectionId") == "c1"
        assert "searchString" not in query

    def test_serialises_booleans_as_the_api_expects(self) -> None:
        mock = mock_fiz([Reply(200, [])])
        mock.fiz.invoices.list({"includeATInvoices": True, "filterAllStatusesByDate": False})
        query = mock.requests[0].url.params
        assert query.get("includeATInvoices") == "true"
        assert query.get("filterAllStatusesByDate") == "false"

    def test_sends_a_json_body(self) -> None:
        mock = mock_fiz([Reply(201, {"id": "c1"})])
        created = mock.fiz.customers.create(customer)
        assert dict(created) == {"id": "c1"}
        assert mock.requests[0].method == "POST"
        assert mock.requests[0].headers["content-type"] == "application/json"
        assert mock.requests[0].body == customer

    def test_uses_another_base_url(self) -> None:
        mock = mock_fiz([Reply(200, {})], base_url="http://localhost:8080/")
        mock.fiz.company.retrieve()
        assert str(mock.requests[0].url) == "http://localhost:8080/company"

    def test_calls_any_operation_by_its_operation_id(self) -> None:
        mock = mock_fiz([Reply(200, [])])
        assert mock.fiz.call("SeriesController_getAll") == []
        assert mock.requests[0].url.path == "/series"
        with pytest.raises(FizError, match="Unknown operation"):
            mock.fiz.call("NoSuchController_x")  # type: ignore[call-overload]


class TestIdempotencyKey:
    def test_is_generated_for_a_write(self) -> None:
        mock = mock_fiz([Reply(201, {})])
        mock.fiz.customers.create(customer)
        assert UUID.match(mock.requests[0].headers["idempotency-key"])

    def test_is_the_callers_when_given(self) -> None:
        mock = mock_fiz([Reply(201, {})])
        mock.fiz.customers.create(customer, idempotency_key="order-1042-customer")
        assert mock.requests[0].headers["idempotency-key"] == "order-1042-customer"

    def test_takes_a_callers_idempotency_key_header_in_any_case_as_the_key(self) -> None:
        mock = mock_fiz([Reply(201, {})])
        mock.fiz.customers.create(customer, headers={"Idempotency-Key": "order-7"})
        assert mock.requests[0].headers["idempotency-key"] == "order-7"

    @pytest.mark.parametrize(
        "options",
        [
            pytest.param({"idempotency_key": ""}, id="an empty option"),
            pytest.param({"headers": {"Idempotency-Key": "   "}}, id="a blank header"),
            pytest.param({"idempotency_key": "order 7"}, id="a key with a space"),
            pytest.param({"idempotency_key": "k" * 129}, id="a key over 128 characters"),
        ],
    )
    def test_refuses_an_invalid_key_before_sending_anything(self, options: Any) -> None:
        mock = mock_fiz([Reply(201, {})])
        with pytest.raises(FizError, match="idempotency_key"):
            mock.fiz.customers.create(customer, **options)
        assert mock.requests == []

    def test_is_not_sent_on_a_read_nor_on_an_operation_that_does_not_take_one(self) -> None:
        mock = mock_fiz([Reply(200, []), Reply(200, {})])
        mock.fiz.invoices.list(headers={"Idempotency-Key": "order-7"})
        mock.fiz.templates.validate({})  # type: ignore[typeddict-item]
        assert [r.headers.get("idempotency-key") for r in mock.requests] == [None, None]


class TestErrors:
    def test_carries_status_code_messages_and_the_request_id(self) -> None:
        mock = mock_fiz(
            [
                Reply(
                    404,
                    {"statusCode": 404, "message": "Invoice not found", "code": "ENTITY_NOT_FOUND"},
                    {"x-request-id": "req-1"},
                )
            ]
        )
        with pytest.raises(FizNotFoundError) as caught:
            mock.fiz.invoices.retrieve("x")
        error = caught.value
        assert isinstance(error, FizApiError)
        assert error.status == 404
        assert error.code == "ENTITY_NOT_FOUND"
        assert error.messages == ["Invoice not found"]
        assert error.request_id == "req-1"
        assert str(error) == "GET /invoices/x failed with 404: Invoice not found"

    def test_lists_every_validation_message(self) -> None:
        mock = mock_fiz(
            [
                Reply(
                    400,
                    {
                        "statusCode": 400,
                        "message": ["name must be a string", "property x should not exist"],
                        "error": "Bad Request",
                    },
                )
            ]
        )
        with pytest.raises(FizBadRequestError) as caught:
            mock.fiz.customers.create(customer)
        assert len(caught.value.messages) == 2
        assert caught.value.code is None
        assert UUID.match(caught.value.idempotency_key or "")

    def test_maps_401_and_5xx(self) -> None:
        mock = mock_fiz(
            [
                Reply(401, {"statusCode": 401, "message": "API key is missing"}),
                Reply(500, {"statusCode": 500, "message": "boom"}),
            ]
        )
        with pytest.raises(FizAuthenticationError):
            mock.fiz.company.retrieve()
        with pytest.raises(FizServerError):
            mock.fiz.customers.create(customer)


class TestRetries:
    def test_retries_a_429_after_retry_after(self, sleeps: list[float]) -> None:
        mock = mock_fiz(
            [
                Reply(429, {"statusCode": 429, "message": "slow down"}, {"retry-after": "2"}),
                Reply(201, {"id": "c1"}),
            ]
        )
        assert dict(mock.fiz.customers.create(customer)) == {"id": "c1"}
        assert sleeps == [2.0]
        assert (
            mock.requests[1].headers["idempotency-key"]
            == mock.requests[0].headers["idempotency-key"]
        )

    def test_does_not_wait_out_a_retry_after_longer_than_a_minute(self) -> None:
        mock = mock_fiz(
            [Reply(429, {"statusCode": 429, "message": "slow down"}, {"retry-after": "3600"})]
        )
        with pytest.raises(FizRateLimitError):
            mock.fiz.company.retrieve()
        assert len(mock.requests) == 1

    def test_reads_a_retry_after_given_as_an_http_date(self, sleeps: list[float]) -> None:
        mock = mock_fiz(
            [
                Reply(429, {}, {"retry-after": "Wed, 21 Oct 2015 07:28:00 GMT"}),
                Reply(200, {}),
            ]
        )
        mock.fiz.company.retrieve()
        assert sleeps == [0.0]

    def test_reports_a_timeout_after_retrying_it(self) -> None:
        mock = mock_fiz([httpx.ReadTimeout("timed out")] * 3)
        with pytest.raises(FizTimeoutError) as caught:
            mock.fiz.customers.create(customer, idempotency_key="k1")
        assert caught.value.idempotency_key == "k1"
        assert len(mock.requests) == 3

    def test_raises_the_conflict_when_a_write_is_still_in_progress_after_every_retry(
        self,
    ) -> None:
        busy = Reply(
            409, {"statusCode": 409, "message": "still being processed"}, {"retry-after": "1"}
        )
        mock = mock_fiz([busy, busy, busy])
        with pytest.raises(FizConflictError):
            mock.fiz.invoices.issue("inv1")
        assert len(mock.requests) == 3

    def test_gives_up_after_max_retries(self) -> None:
        limited = Reply(429, {"statusCode": 429, "message": "slow down"}, {"retry-after": "0"})
        mock = mock_fiz([limited, limited, limited])
        with pytest.raises(FizRateLimitError):
            mock.fiz.company.retrieve()
        assert len(mock.requests) == 3

    def test_repeats_a_write_that_got_no_response_with_the_same_key(self) -> None:
        mock = mock_fiz([httpx.ConnectError("connection failed"), Reply(201, {"id": "c1"})])
        assert dict(mock.fiz.customers.create(customer)) == {"id": "c1"}
        assert len(mock.requests) == 2
        assert (
            mock.requests[1].headers["idempotency-key"]
            == mock.requests[0].headers["idempotency-key"]
        )

    def test_waits_for_a_write_still_in_progress(self) -> None:
        mock = mock_fiz(
            [
                Reply(
                    409,
                    {"statusCode": 409, "message": "still being processed"},
                    {"retry-after": "1"},
                ),
                Reply(200, {"id": "inv1", "number": "FT 2026/1"}, {"idempotent-replayed": "true"}),
            ]
        )
        issued = mock.fiz.invoices.issue("inv1", {"expectedUpdatedAt": "2026-11-24T10:00:00.000Z"})
        assert issued["number"] == "FT 2026/1"
        assert len(mock.requests) == 2

    def test_repeats_a_write_whose_response_body_was_cut_off_with_the_same_key(self) -> None:
        mock = mock_fiz([cut_off(201), Reply(201, {"id": "c1"})])
        assert dict(mock.fiz.customers.create(customer, idempotency_key="order-9")) == {"id": "c1"}
        assert [r.headers["idempotency-key"] for r in mock.requests] == ["order-9", "order-9"]

    def test_repeats_an_issue_whose_json_body_arrived_broken_with_the_same_key(self) -> None:
        mock = mock_fiz([raw(200, '{"number":'), Reply(200, {"id": "inv1", "number": "FT 2026/1"})])
        issued = mock.fiz.invoices.issue("inv1", {}, idempotency_key="issue-1")
        assert issued["number"] == "FT 2026/1"
        assert [r.headers["idempotency-key"] for r in mock.requests] == ["issue-1", "issue-1"]

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param('{"number":', id="broken JSON"),
            pytest.param("", id="an empty body announced as JSON"),
            pytest.param('{"total":NaN}', id="NaN, which is not JSON"),
            pytest.param('{"total":Infinity}', id="Infinity, which is not JSON"),
        ],
    )
    def test_never_returns_a_success_with_a_broken_body_it_raises_with_the_key(
        self, text: str
    ) -> None:
        mock = mock_fiz([raw(200, text)], max_retries=0)
        with pytest.raises(FizConnectionError) as caught:
            mock.fiz.invoices.issue("inv1", {}, idempotency_key="issue-1")
        assert caught.value.idempotency_key == "issue-1"

    def test_parses_a_success_as_json_whatever_the_content_type_spelling(self) -> None:
        mock = mock_fiz(
            [raw(200, '{"id":"inv1","number":"FT 2026/1"}', "Application/JSON; charset=UTF-8")]
        )
        assert mock.fiz.invoices.issue("inv1")["number"] == "FT 2026/1"

    def test_never_returns_an_html_page_as_a_success(self) -> None:
        mock = mock_fiz([raw(200, "<html>maintenance</html>", "text/html")], max_retries=0)
        with pytest.raises(FizConnectionError) as caught:
            mock.fiz.invoices.issue("inv1", {}, idempotency_key="issue-1")
        assert caught.value.idempotency_key == "issue-1"

    def test_keeps_a_broken_error_body_as_text_and_lets_the_status_decide(self) -> None:
        mock = mock_fiz([raw(400, "upstream <html> error")])
        with pytest.raises(FizBadRequestError) as caught:
            mock.fiz.customers.create(customer)
        assert caught.value.messages == ["upstream <html> error"]
        assert len(mock.requests) == 1

    @pytest.mark.parametrize(
        ("status", "headers"),
        [
            pytest.param(503, {}, id="a 503 on a write"),
            pytest.param(429, {"retry-after": "120"}, id="a 429 with a Retry-After over a minute"),
        ],
    )
    def test_keeps_the_status_rules_when_the_body_is_cut_off(
        self, status: int, headers: dict[str, str]
    ) -> None:
        mock = mock_fiz([cut_off(status, headers), Reply(201, {"id": "c1"})])
        with pytest.raises(FizApiError) as caught:
            mock.fiz.customers.create(customer)
        assert caught.value.status == status
        assert len(mock.requests) == 1

    def test_waits_out_the_retry_after_of_a_429_whose_body_is_cut_off(
        self, sleeps: list[float]
    ) -> None:
        mock = mock_fiz([cut_off(429, {"retry-after": "2"}), Reply(201, {"id": "c1"})])
        assert dict(mock.fiz.customers.create(customer)) == {"id": "c1"}
        assert sleeps == [2.0]

    def test_reports_a_cut_off_body_with_the_key_when_it_cannot_retry(self) -> None:
        mock = mock_fiz([cut_off(201)], max_retries=0)
        with pytest.raises(FizConnectionError) as caught:
            mock.fiz.customers.create(customer, idempotency_key="order-9")
        assert caught.value.idempotency_key == "order-9"

    def test_does_not_retry_a_409_whose_outcome_is_unknown(self) -> None:
        mock = mock_fiz([Reply(409, {"statusCode": 409, "message": "may have taken effect"})])
        with pytest.raises(FizConflictError):
            mock.fiz.invoices.issue("inv1")
        assert len(mock.requests) == 1

    def test_retries_a_503_on_a_read_but_not_on_a_write(self) -> None:
        unavailable = Reply(503, {"statusCode": 503, "message": "unavailable"})
        mock = mock_fiz([unavailable, Reply(200, {}), unavailable])
        assert dict(mock.fiz.company.retrieve()) == {}
        with pytest.raises(FizServerError):
            mock.fiz.customers.create(customer)
        assert len(mock.requests) == 3

    def test_does_not_repeat_a_non_idempotent_post_that_got_no_response(self) -> None:
        mock = mock_fiz([httpx.ConnectError("connection failed")])
        with pytest.raises(FizConnectionError):
            mock.fiz.vat.calculate({})  # type: ignore[typeddict-item]
        assert len(mock.requests) == 1

    def test_backs_off_exponentially_between_attempts(self, sleeps: list[float]) -> None:
        down = httpx.ConnectError("down")
        mock = mock_fiz([down, down, down, Reply(200, {})], max_retries=3)
        mock.fiz.company.retrieve()
        assert len(sleeps) == 3
        for pause, base in zip(sleeps, [0.5, 1.0, 2.0], strict=True):
            assert 0.75 * base <= pause <= 1.25 * base


class TestPagination:
    def test_walks_the_pages_until_an_empty_one(self) -> None:
        mock = mock_fiz(
            [Reply(200, [{"id": "1"}, {"id": "2"}]), Reply(200, [{"id": "3"}]), Reply(200, [])]
        )
        ids = [
            invoice["id"]
            for invoice in mock.fiz.invoices.list_all({"status": "ISSUED"}, page_size=2)
        ]
        assert ids == ["1", "2", "3"]
        assert [(r.url.params.get("offset"), r.url.params.get("limit")) for r in mock.requests] == [
            ("0", "2"),
            ("2", "2"),
            ("3", "2"),
        ]
        assert all(r.url.params.get("status") == "ISSUED" for r in mock.requests)

    def test_walks_numbered_pages_for_bank_transactions(self) -> None:
        mock = mock_fiz([Reply(200, [{"id": "t1"}]), Reply(200, [])])
        found = list(mock.fiz.bank.transactions_all({"connectionId": "c1"}, page_size=1))
        assert len(found) == 1
        assert [r.url.params.get("page") for r in mock.requests] == ["1", "2"]

    def test_defaults_to_pages_of_100(self) -> None:
        mock = mock_fiz([Reply(200, [])])
        assert list(mock.fiz.customers.list_all()) == []
        assert mock.requests[0].url.params.get("limit") == "100"


class TestOnResponse:
    def test_reports_every_response_retries_included(self) -> None:
        seen: list[FizResponseInfo] = []
        mock = mock_fiz(
            [
                Reply(
                    429,
                    {"statusCode": 429, "message": "slow"},
                    {"retry-after": "1", "x-request-id": "r1"},
                ),
                Reply(200, {"id": "inv1"}, {"x-request-id": "r2", "idempotent-replayed": "true"}),
            ],
            on_response=seen.append,
        )
        mock.fiz.invoices.issue("inv1", {}, idempotency_key="issue-1")
        assert len(seen) == 2
        first, second = seen
        assert (
            first.operation_id,
            first.method,
            first.path,
            first.status,
            first.request_id,
            first.idempotency_key,
            first.replayed,
            first.attempt,
        ) == (
            "InvoicesController_issue",
            "POST",
            "/invoices/{id}/issue",
            429,
            "r1",
            "issue-1",
            False,
            1,
        )
        assert (second.status, second.request_id, second.replayed, second.attempt) == (
            200,
            "r2",
            True,
            2,
        )
        assert first.duration_ms >= 0

    def test_never_fails_the_call_when_the_hook_raises(self) -> None:
        def hook(info: FizResponseInfo) -> None:
            raise RuntimeError("logger down")

        mock = mock_fiz([Reply(200, {})], on_response=hook)
        assert dict(mock.fiz.company.retrieve()) == {}


class TestRedirects:
    def test_are_never_followed_on_an_api_call(self) -> None:
        mock = mock_fiz([Reply(302, None, {"location": "https://elsewhere.example.com/company"})])
        with pytest.raises(FizError, match=r"redirect to https://elsewhere"):
            mock.fiz.company.retrieve()
        assert len(mock.requests) == 1


class TestPdfDownload:
    def test_sends_credentials_to_a_link_on_the_api_origin_only(self) -> None:
        mock = mock_fiz(
            [
                Reply(
                    200, {"id": "f1", "name": "FT.pdf", "url": "https://api.fiz.co/files/FT.pdf"}
                ),
                Reply(200, "pdf-bytes"),
            ]
        )
        mock.fiz.invoices.download_pdf("inv1")
        assert mock.requests[1].headers["x-api-key"] == "fiz_live_key"

    def test_drops_the_credentials_when_a_redirect_leaves_the_api_origin(self) -> None:
        mock = mock_fiz(
            [
                Reply(
                    200, {"id": "f1", "name": "FT.pdf", "url": "https://api.fiz.co/files/FT.pdf"}
                ),
                Reply(302, None, {"location": "https://storage.example.com/FT.pdf?sig=1"}),
                Reply(200, "pdf-bytes"),
            ]
        )
        mock.fiz.invoices.download_pdf("inv1")
        assert [(r.url.host, r.headers.get("x-api-key")) for r in mock.requests] == [
            ("api.fiz.co", "fiz_live_key"),
            ("api.fiz.co", "fiz_live_key"),
            ("storage.example.com", None),
        ]

    def test_stops_after_five_redirects(self) -> None:
        hop = Reply(302, None, {"location": "https://storage.example.com/next"})
        mock = mock_fiz(
            [
                Reply(
                    200, {"id": "f1", "name": "FT.pdf", "url": "https://storage.example.com/FT.pdf"}
                ),
                *[hop] * 6,
            ]
        )
        with pytest.raises(FizError, match="more than 5 redirects"):
            mock.fiz.invoices.download_pdf("inv1")
        assert len(mock.requests) == 7

    def test_raises_a_fiz_error_when_the_api_gives_no_link(self) -> None:
        mock = mock_fiz([Reply(200, {"id": "f1", "name": None, "url": None})])
        with pytest.raises(FizError):
            mock.fiz.invoices.download_pdf("inv1")

    def test_fetches_a_foreign_link_without_credentials(self) -> None:
        mock = mock_fiz(
            [
                Reply(
                    200,
                    {"id": "f1", "name": "FT.pdf", "url": "https://files.example.com/FT.pdf?sig=1"},
                ),
                Reply(200, "pdf-bytes"),
            ]
        )
        content = mock.fiz.invoices.download_pdf("inv1")
        assert len(content) > 0
        assert mock.requests[1].url.host == "files.example.com"
        assert "x-api-key" not in mock.requests[1].headers

    def test_never_sends_a_foreign_link_through_the_callers_http_client(self) -> None:
        # An integration may put its credential anywhere on its httpx.Client: default
        # headers, cookies, auth, or an event hook that adds it to every request. None of
        # it may reach the host that stores the file, so that request never goes through
        # the caller's client at all.
        hooked: list[str] = []

        def add_token(request: httpx.Request) -> None:
            hooked.append(request.url.host)
            request.headers["authorization"] = "Bearer from-a-hook"

        def api(request: httpx.Request) -> httpx.Response:
            assert request.url.host == "api.fiz.co", "a foreign link reached http_client"
            body = {"id": "f1", "name": "FT.pdf", "url": "https://files.example.com/FT.pdf"}
            return httpx.Response(200, json=body)

        files: list[httpx.Request] = []

        def storage(request: httpx.Request) -> httpx.Response:
            files.append(request)
            return httpx.Response(200, content=b"%PDF")

        http_client = httpx.Client(
            transport=httpx.MockTransport(api),
            headers={"authorization": "Bearer client-default", "x-api-key": "client-default"},
            cookies={"session": "client-cookie"},
            auth=("user", "secret"),
            event_hooks={"request": [add_token]},
        )
        fiz = Fiz(api_key="fiz_live_key", http_client=http_client)
        fiz._client._file_http = httpx.Client(transport=httpx.MockTransport(storage))
        assert fiz.invoices.download_pdf("inv1") == b"%PDF"
        assert hooked == ["api.fiz.co"]
        assert [r.url.host for r in files] == ["files.example.com"]
        for header in ("authorization", "x-api-key", "cookie"):
            assert header not in files[0].headers

    def test_closes_its_own_file_client_but_not_the_callers(self) -> None:
        mock = mock_fiz([])
        file_http = mock.fiz._client._file_http
        assert file_http is not None
        mock.fiz.close()
        assert file_http.is_closed
        assert not mock.fiz._client._http.is_closed
